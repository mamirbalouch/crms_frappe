import frappe


@frappe.whitelist()
def export_network_pdf(svg, width=None, height=None, filename="Common Numbers Network"):
	"""
	Render a standalone SVG (the network graph) to a single-page PDF whose page
	size matches the graph's own dimensions — no fixed page limit, colours kept.
	Returns the private File URL to open/download.
	"""
	from frappe.utils.pdf import get_pdf

	try:
		w = float(width)
		h = float(height)
	except (TypeError, ValueError):
		w, h = 1600.0, 1200.0
	# px → mm at 96 dpi, so the page fits the SVG 1:1
	w_mm = round(w / 96.0 * 25.4, 1)
	h_mm = round(h / 96.0 * 25.4, 1)

	html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
	@page {{ size: {w_mm}mm {h_mm}mm; margin: 0; }}
	html, body {{ margin: 0; padding: 0; }}
	</style></head><body>{svg}</body></html>"""

	options = {
		"page-width": f"{w_mm}mm",
		"page-height": f"{h_mm}mm",
		"margin-top": "0", "margin-bottom": "0", "margin-left": "0", "margin-right": "0",
		"disable-smart-shrinking": "",
	}
	pdf = get_pdf(html, options=options)

	safe = "".join(c for c in str(filename) if c.isalnum() or c in " -_") or "network"
	_file = frappe.get_doc({
		"doctype": "File",
		"file_name": f"{safe}.pdf",
		"is_private": 1,
		"content": pdf,
	}).insert(ignore_permissions=True)
	return _file.file_url


@frappe.whitelist()
def export_network_image_pdf(image, width=None, height=None, filename="Common Numbers Network"):
	"""
	Render a graph raster (PNG data URL from Cytoscape) to a single-page PDF whose
	page size matches the image — no fixed page limit, colours preserved.
	"""
	from frappe.utils.pdf import get_pdf

	try:
		w = float(width)
		h = float(height)
	except (TypeError, ValueError):
		w, h = 1600.0, 1200.0
	w_mm = round(w / 96.0 * 25.4, 1)
	h_mm = round(h / 96.0 * 25.4, 1)

	html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
	@page {{ size: {w_mm}mm {h_mm}mm; margin: 0; }}
	html, body {{ margin: 0; padding: 0; }}
	img {{ width: {w_mm}mm; height: {h_mm}mm; display: block; }}
	</style></head><body><img src="{image}"></body></html>"""

	options = {
		"page-width": f"{w_mm}mm", "page-height": f"{h_mm}mm",
		"margin-top": "0", "margin-bottom": "0", "margin-left": "0", "margin-right": "0",
		"disable-smart-shrinking": "", "enable-local-file-access": "",
	}
	pdf = get_pdf(html, options=options)

	safe = "".join(c for c in str(filename) if c.isalnum() or c in " -_") or "network"
	_file = frappe.get_doc({
		"doctype": "File", "file_name": f"{safe}.pdf", "is_private": 1, "content": pdf,
	}).insert(ignore_permissions=True)
	return _file.file_url


@frappe.whitelist()
def get_common_number_network(case_project=None, working_number=None, from_date=None, to_date=None,
                              min_digits=10, max_digits=14, only_cross_case=0, max_nodes=60):
	"""
	Build a link graph: working numbers (A-numbers) connected through the common
	B-numbers they share. Returns {nodes, edges} for a force-directed chart.
	Only B-numbers linking >= 2 working numbers are included; only real
	mobile/foreign numbers (by digit length) are considered.
	"""
	max_nodes = int(max_nodes or 60)
	min_len = int(min_digits or 10)
	max_len = int(max_digits or 14)
	conditions = [
		"dcr.second_party_number IS NOT NULL",
		"dcr.second_party_number NOT IN ('', '1')",
		"LENGTH(dcr.second_party_number) BETWEEN %(min_len)s AND %(max_len)s",
	]
	values = {"min_len": min_len, "max_len": max_len}
	if from_date:
		conditions.append("dcr.date_of_communication >= %(from_date)s")
		values["from_date"] = from_date
	if to_date:
		conditions.append("dcr.date_of_communication <= %(to_date)s")
		values["to_date"] = to_date
	if working_number:
		# center on one working number: only its common numbers and their other links
		values["wn"] = working_number

	where = "WHERE " + " AND ".join(conditions)

	# HAVING clause for the "common" set (>=2 working numbers; optional case scope)
	having = "COUNT(DISTINCT c.wn) >= 2"
	if case_project:
		having += " AND SUM(c.case_project = %(cp)s) > 0"
		values["cp"] = case_project

	rows = frappe.db.sql(
		f"""
		WITH contacts AS (
			SELECT
				wn.name AS wn,
				wn.working_mobile_number AS wnum,
				wn.owner_name AS owner,
				wn.case_project AS case_project,
				dcr.second_party_number AS bnum,
				COUNT(*) AS calls
			FROM `tabDetail Call Record` dcr
			INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
			INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
			{where}
			GROUP BY wn.name, dcr.second_party_number
		),
		common AS (
			SELECT c.bnum
			FROM contacts c
			GROUP BY c.bnum
			HAVING {having}
		)
		SELECT c.wn, c.wnum, c.owner, c.case_project, cp.case_title, c.bnum, c.calls
		FROM contacts c
		INNER JOIN common ON c.bnum = common.bnum
		LEFT JOIN `tabCase Project` cp ON c.case_project = cp.name
		ORDER BY c.bnum
		""",
		values,
		as_dict=True,
	)

	# Optionally narrow to the neighbourhood of a chosen working number
	if working_number:
		bnums_of_wn = {r["bnum"] for r in rows if r["wn"] == working_number}
		rows = [r for r in rows if r["bnum"] in bnums_of_wn]

	from collections import defaultdict

	# A common number is a "cross-case bridge" when the working numbers it links
	# span more than one Case Project — that's the finding worth highlighting.
	bnum_cases = defaultdict(set)
	for r in rows:
		bnum_cases[r["bnum"]].add(r["case_project"])
	cross = {b: len(cs) > 1 for b, cs in bnum_cases.items()}

	if int(only_cross_case or 0):
		rows = [r for r in rows if cross.get(r["bnum"])]

	# Cap graph size: keep the highest-degree common numbers (cross-case first)
	degree = defaultdict(set)
	for r in rows:
		degree[r["bnum"]].add(r["wn"])
	ranked = sorted(degree.items(), key=lambda kv: (cross.get(kv[0], False), len(kv[1])), reverse=True)
	keep_bnums = {b for b, _ in ranked[:max_nodes]}
	rows = [r for r in rows if r["bnum"] in keep_bnums]

	nodes = {}
	edges = []
	for r in rows:
		wn_id = "wn:" + r["wn"]
		cn_id = "cn:" + r["bnum"]
		is_cross = cross.get(r["bnum"], False)
		if wn_id not in nodes:
			nodes[wn_id] = {
				"id": wn_id, "label": r["wnum"], "type": "working",
				"owner": r.get("owner") or "",
				"case": r.get("case_title") or r["case_project"],
			}
		if cn_id not in nodes:
			nodes[cn_id] = {"id": cn_id, "label": r["bnum"], "type": "common", "cross_case": is_cross}
		edges.append({"source": wn_id, "target": cn_id, "weight": r["calls"], "cross_case": is_cross})

	return {"nodes": list(nodes.values()), "edges": edges}


@frappe.whitelist()
def get_movement_points(working_number, from_date=None, to_date=None):
	"""
	Return time-ordered geo points for a Working Number's CDR, for plotting
	movement on a map. Only rows with valid numeric lat/lon are returned.
	"""
	if not working_number:
		frappe.throw(frappe._("Select a Working Number."))

	conditions = [
		"cr.working_number = %(wn)s",
		"dcr.latitude IS NOT NULL AND dcr.latitude != ''",
		"dcr.longitude IS NOT NULL AND dcr.longitude != ''",
		"dcr.date_of_communication IS NOT NULL",
	]
	values = {"wn": working_number}
	if from_date:
		conditions.append("dcr.date_of_communication >= %(fd)s")
		values["fd"] = from_date
	if to_date:
		conditions.append("dcr.date_of_communication <= %(td)s")
		values["td"] = to_date

	rows = frappe.db.sql(
		f"""
		SELECT
			dcr.date_of_communication AS ts,
			dcr.second_party_number,
			dcr.call_type,
			dcr.duration,
			dcr.rbs,
			dcr.latitude,
			dcr.longitude
		FROM `tabDetail Call Record` dcr
		INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
		WHERE {" AND ".join(conditions)}
		ORDER BY dcr.date_of_communication
		""",
		values,
		as_dict=True,
	)

	points = []
	for r in rows:
		try:
			lat = float(r.latitude)
			lon = float(r.longitude)
		except (TypeError, ValueError):
			continue
		if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
			continue
		points.append({
			"ts": str(r.ts),
			"lat": lat,
			"lon": lon,
			"number": r.second_party_number,
			"call_type": r.call_type,
			"duration": r.duration,
			"rbs": r.rbs,
		})
	return points
