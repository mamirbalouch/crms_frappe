"""
Crystal-Reports-style printable PDFs for the core CDR reports, plus a batch
"print all reports" that bundles them into a single ZIP.
"""
import io
import json
import zipfile

import frappe
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

# Reports offered in the batch pack
PACK_REPORTS = ["CDR", "Frequency", "RBS", "Common Numbers"]


# ──────────────────────────────────────────────────────────────────────────────
# Public endpoints
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def render_report_pdf(report, filters=None):
	"""Render one report to a PDF File and return its URL."""
	filters = _load(filters)
	html = _build_html(report, filters)
	pdf = get_pdf(html, options=_pdf_options())
	title = f"{report} - {filters.get('working_number') or filters.get('case_project') or 'All'}"
	return _save_pdf(pdf, title)


@frappe.whitelist()
def print_all_reports(filters=None):
	"""
	Generate every pack report for the selected scope and return a ZIP File URL.
	If a Working Number is given → one folder of reports for it.
	If only a Case Project is given → a folder per working number in the case.
	"""
	filters = _load(filters)
	targets = _resolve_working_numbers(filters)
	if not targets:
		frappe.throw(frappe._("No working numbers found for this selection."))

	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
		for wn in targets:
			wf = dict(filters)
			wf["working_number"] = wn
			folder = _safe(wn)
			for report in PACK_REPORTS:
				html = _build_html(report, wf)
				pdf = get_pdf(html, options=_pdf_options())
				zf.writestr(f"{folder}/{_safe(report)}.pdf", pdf)

	label = filters.get("working_number") or filters.get("case_project") or "All"
	_file = frappe.get_doc({
		"doctype": "File",
		"file_name": f"CDR Reports - {_safe(label)}.zip",
		"is_private": 1,
		"content": buf.getvalue(),
	}).insert(ignore_permissions=True)
	return {"file_url": _file.file_url, "count": len(targets), "reports": len(PACK_REPORTS)}


# ──────────────────────────────────────────────────────────────────────────────
# HTML builders
# ──────────────────────────────────────────────────────────────────────────────

def _build_html(report, filters):
	builders = {
		"CDR": _cdr_html,
		"Frequency": _frequency_html,
		"RBS": _rbs_html,
		"Common Numbers": _common_html,
	}
	fn = builders.get(report)
	if not fn:
		frappe.throw(frappe._("Unknown report: {0}").format(report))
	title, subtitle, table = fn(filters)
	return _wrap(title, subtitle, table, filters)


def _cdr_html(filters):
	where, values = _detail_conditions(filters)
	rows = frappe.db.sql(
		f"""
		SELECT dcr.second_party_number, dcr.call_type, dcr.date_of_communication,
			dcr.duration, dcr.imei, dcr.rbs, dcr.latitude, dcr.longitude
		FROM `tabDetail Call Record` dcr
		INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
		INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
		{where}
		ORDER BY dcr.date_of_communication
		""",
		values, as_dict=True,
	)
	head = ["B Number", "Call Type", "Date / Time", "Duration", "IMEI", "RBS / Location"]
	body = []
	for r in rows:
		loc = r.rbs or ""
		if r.latitude and r.longitude:
			loc = f"{loc} {r.latitude} {r.longitude}".strip()
		body.append([r.second_party_number, r.call_type or "", _dt(r.date_of_communication),
		             _num(r.duration), r.imei or "", loc])
	return "Call Detail Record (CDR)", f"{len(rows)} records", _table(head, body, align_right=[3])


def _frequency_html(filters):
	where, values = _detail_conditions(filters, exclude_junk=True)
	rows = frappe.db.sql(
		f"""
		SELECT dcr.second_party_number,
			COUNT(*) AS total_calls, SUM(dcr.duration) AS total_duration,
			MAX(mud.name_of_mobile_user) AS name, MAX(mud.nic_no) AS nic,
			MAX(mud.address_of_mobile_user) AS address
		FROM `tabDetail Call Record` dcr
		INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
		INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
		LEFT JOIN `tabMobile User Data` mud ON mud.mobile_number = dcr.second_party_number
		{where}
		GROUP BY dcr.second_party_number
		ORDER BY total_calls DESC
		""",
		values, as_dict=True,
	)
	head = ["S.No", "Dialed Number", "Name", "Address", "NIC", "Total Duration", "Total Calls"]
	body = [[i + 1, r.second_party_number, r.name or "", r.address or "", r.nic or "",
	         _num(r.total_duration), _num(r.total_calls)] for i, r in enumerate(rows)]
	return "Call Frequency", f"{len(rows)} contacts", _table(head, body, align_right=[0, 5, 6])


def _rbs_html(filters):
	from crms.crms.report.rbs_wise_report.rbs_wise_report import get_data
	rows = get_data(filters)
	head = ["S.No", "Location / RBS", "Latitude", "Longitude", "First Time", "Last Time", "Total Hits"]
	body = [[i + 1, r["rbs"], r.get("latitude") or "", r.get("longitude") or "",
	         r.get("first_time") or "", r.get("last_time") or "", _num(r.get("total_hits"))]
	        for i, r in enumerate(rows)]
	return "RBS / Location Wise", f"{len(rows)} locations", _table(head, body, align_right=[0, 6])


def _common_html(filters):
	from crms.crms.report.common_numbers_report.common_numbers_report import get_data
	rows = get_data(filters)
	head = ["Common Number", "Working No. A", "Case A", "Calls A", "Working No. B", "Case B", "Calls B", "Relationship"]
	body = [[r["common_number"], r["wn1"], r.get("case1") or "", _num(r.get("calls1")),
	         r["wn2"], r.get("case2") or "", _num(r.get("calls2")), r.get("relationship") or ""]
	        for r in rows]
	return "Common Numbers", f"{len(rows)} links", _table(head, body, align_right=[3, 6])


# ──────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────────────

def _detail_conditions(filters, exclude_junk=False):
	conditions, values = [], {}
	if filters.get("working_number"):
		conditions.append("cr.working_number = %(working_number)s")
		values["working_number"] = filters["working_number"]
	if filters.get("case_project"):
		conditions.append("wn.case_project = %(case_project)s")
		values["case_project"] = filters["case_project"]
	if filters.get("from_date"):
		conditions.append("dcr.date_of_communication >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("dcr.date_of_communication <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if exclude_junk:
		conditions.append("dcr.second_party_number NOT IN ('', '1')")

	from crms.permissions import scope_condition
	sc, sv = scope_condition("wn")
	if sc:
		conditions.append(sc)
		values.update(sv)

	where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
	return where, values


def _resolve_working_numbers(filters):
	if filters.get("working_number"):
		return [filters["working_number"]]
	wn_filters = {}
	if filters.get("case_project"):
		wn_filters["case_project"] = filters["case_project"]
	# get_list applies the user's permission scope (Department/Unit/Section)
	return frappe.get_list("Working Number", filters=wn_filters, pluck="name", order_by="name", limit_page_length=0)


def _wrap(title, subtitle, table_html, filters):
	header = _report_header(title, subtitle, filters)
	return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
		* {{ box-sizing: border-box; }}
		body {{ font-family: Helvetica, Arial, sans-serif; color: #222; margin: 0; }}
		.hdr {{ border-bottom: 2px solid #1565c0; padding-bottom: 6px; margin-bottom: 8px; }}
		.hdr h2 {{ margin: 0 0 2px 0; font-size: 16px; color: #1565c0; }}
		.hdr .sub {{ font-size: 10px; color: #666; }}
		.meta {{ width: 100%; font-size: 10px; margin: 6px 0 10px 0; border-collapse: collapse; }}
		.meta td {{ padding: 1px 6px; }}
		.meta .k {{ color: #666; font-weight: bold; white-space: nowrap; }}
		table.data {{ width: 100%; border-collapse: collapse; font-size: 9px; }}
		table.data th {{ background: #1565c0; color: #fff; padding: 4px 5px; text-align: left; }}
		table.data td {{ padding: 3px 5px; border-bottom: 1px solid #e2e6ea; vertical-align: top; }}
		table.data tr:nth-child(even) td {{ background: #f5f8fb; }}
		.r {{ text-align: right; }}
	</style></head><body>
		<div class="hdr"><h2>{frappe.utils.escape_html(title)}</h2><div class="sub">{frappe.utils.escape_html(subtitle)}</div></div>
		{header}
		{table_html}
	</body></html>"""


def _report_header(title, subtitle, filters):
	wn = filters.get("working_number")
	rows = []
	if wn and frappe.db.exists("Working Number", wn):
		doc = frappe.get_doc("Working Number", wn)
		case_title = frappe.db.get_value("Case Project", doc.case_project, "case_title") or doc.case_project
		dr = frappe.db.sql(
			"""SELECT MIN(dcr.date_of_communication), MAX(dcr.date_of_communication)
			   FROM `tabDetail Call Record` dcr INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
			   WHERE cr.working_number = %s""", wn)
		frm = _dt(dr[0][0], date_only=True) if dr and dr[0][0] else ""
		to = _dt(dr[0][1], date_only=True) if dr and dr[0][1] else ""
		rows = [
			("Working Number", doc.working_mobile_number, "Case", case_title),
			("Owner Name", doc.owner_name or "", "Owner NIC", doc.owner_nic_no or ""),
			("IMEI", doc.imei or "", "CDR Period", f"{frm} — {to}"),
		]
	elif filters.get("case_project"):
		case_title = frappe.db.get_value("Case Project", filters["case_project"], "case_title") or filters["case_project"]
		rows = [("Case", case_title, "Scope", "All working numbers")]

	if not rows:
		return ""
	cells = "".join(
		f"<tr><td class='k'>{frappe.utils.escape_html(str(a))}</td><td>{frappe.utils.escape_html(str(b))}</td>"
		f"<td class='k'>{frappe.utils.escape_html(str(c))}</td><td>{frappe.utils.escape_html(str(d))}</td></tr>"
		for a, b, c, d in rows
	)
	return f"<table class='meta'>{cells}</table>"


def _table(head, body, align_right=None):
	align_right = set(align_right or [])
	th = "".join(f"<th class='{'r' if i in align_right else ''}'>{frappe.utils.escape_html(h)}</th>" for i, h in enumerate(head))
	if not body:
		return f"<table class='data'><thead><tr>{th}</tr></thead><tbody><tr><td colspan='{len(head)}'>No data.</td></tr></tbody></table>"
	trs = []
	for row in body:
		tds = "".join(f"<td class='{'r' if i in align_right else ''}'>{frappe.utils.escape_html(str(v if v is not None else ''))}</td>" for i, v in enumerate(row))
		trs.append(f"<tr>{tds}</tr>")
	return f"<table class='data'><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"


def _pdf_options():
	return {
		"orientation": "Landscape", "page-size": "A4",
		"margin-top": "10mm", "margin-bottom": "12mm", "margin-left": "8mm", "margin-right": "8mm",
		"footer-right": "Page [page] of [topage]", "footer-font-size": "7", "footer-spacing": "3",
	}


def _save_pdf(pdf, title):
	_file = frappe.get_doc({
		"doctype": "File", "file_name": f"{_safe(title)}.pdf", "is_private": 1, "content": pdf,
	}).insert(ignore_permissions=True)
	return _file.file_url


def _load(filters):
	if isinstance(filters, str):
		return json.loads(filters) if filters else {}
	return filters or {}


def _safe(s):
	return "".join(c for c in str(s) if c.isalnum() or c in " -_") or "report"


def _dt(value, date_only=False):
	if not value:
		return ""
	s = str(value)
	return s[:10] if date_only else s[:19]


def _num(v):
	try:
		f = flt(v)
		return str(int(f)) if f == int(f) else f"{f:.2f}"
	except (TypeError, ValueError):
		return str(v or "")
