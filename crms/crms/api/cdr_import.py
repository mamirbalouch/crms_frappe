import csv
import io
import json
import os
import re
from datetime import datetime

import frappe
from frappe import _

# Matches a decimal number that could be a geographic coordinate
_COORD_RE = re.compile(r"[-+]?\d{1,3}\.\d+")

# ──────────────────────────────────────────────────────────────────────────────
# Public API endpoints
# ──────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_file_headers(file_url, header_row=1):
	"""
	Read the first rows of a CDR file (CSV or Excel) and return:
	  - headers: list of column names from the header row
	  - preview:  first 5 data rows (list of lists)
	  - total_rows: total data row count
	"""
	headers, rows = _read_file(file_url, int(header_row))
	return {
		"headers": headers,
		"preview": [list(r) for r in rows[:5]],
		"total_rows": len(rows),
	}


@frappe.whitelist()
def detect_profile(headers_json):
	"""
	Given the file's header list (JSON-encoded), find the best matching
	CDR Import Profile using overlap scoring.
	Returns {profile, operator, score} or {profile: null}.
	"""
	headers = {h.strip() for h in json.loads(headers_json) if h and h.strip()}
	if not headers:
		return {"profile": None, "score": 0}

	profiles = frappe.get_all("CDR Import Profile", fields=["name", "mobile_operator"])
	best, best_score = None, 0.0

	for p in profiles:
		mappings = frappe.get_all(
			"CDR Profile Column",
			filters={"parent": p.name},
			fields=["source_column"],
			order_by=None,
		)
		if not mappings:
			continue
		profile_cols = {m.source_column.strip() for m in mappings}
		matched = len(headers & profile_cols)
		# Score: fraction of profile columns found in file
		score = matched / len(profile_cols)
		if score > best_score:
			best_score = score
			best = p

	if best_score >= 0.6:
		return {"profile": best.name, "operator": best.mobile_operator, "score": round(best_score, 2)}
	return {"profile": None, "score": round(best_score, 2)}


@frappe.whitelist()
def import_cdr(call_record, file_url, profile_name=None, mapping_json=None, header_row=1, date_format=None):
	"""
	Import CDR rows from file_url into the given Call Record.
	Provide either:
	  - profile_name: a saved CDR Import Profile
	  - mapping_json: a JSON dict of {source_column: target_field}
	The call_record must already exist (save the form first).
	"""
	if not frappe.db.exists("Call Record", call_record):
		frappe.throw(_("Call Record {0} not found. Save the form before importing.").format(call_record))

	# Resolve mapping + settings
	rbs_coord_separator = "|"  # default
	if profile_name:
		profile = frappe.get_doc("CDR Import Profile", profile_name)
		mapping = {m.source_column.strip(): m.target_field for m in profile.column_mappings}
		header_row = profile.header_row or 1
		date_format = profile.date_format or None
		rbs_coord_separator = profile.rbs_coord_separator if profile.rbs_coord_separator is not None else "|"
	elif mapping_json:
		mapping = json.loads(mapping_json)
	else:
		frappe.throw(_("Provide either profile_name or mapping_json."))

	headers, rows = _read_file(file_url, int(header_row))

	# Build header → index lookup using the mapping
	col_idx = {}
	for i, h in enumerate(headers):
		h = h.strip()
		if h in mapping:
			col_idx[mapping[h]] = i

	cr = frappe.get_doc("Call Record", call_record)
	dates = []
	count = 0

	for row in rows:
		row = [str(c).strip() if c is not None else "" for c in row]
		if not any(row):
			continue

		def get(field):
			i = col_idx.get(field)
			return row[i] if i is not None and i < len(row) else ""

		date_str = get("date_of_communication")
		parsed_date = _parse_date(date_str, date_format)
		if date_str:
			dates.append(date_str)

		# Resolve RBS and coordinates —————————————————————————————————————
		rbs_raw = get("rbs_with_coords") or get("rbs")
		lat_raw = get("latitude")
		lon_raw = get("longitude")

		if rbs_raw:
			rbs_clean, extracted_lat, extracted_lon = _parse_location(rbs_raw, rbs_coord_separator)
		else:
			rbs_clean, extracted_lat, extracted_lon = rbs_raw, "", ""

		# Explicit lat/lon columns always win; extracted values fill gaps
		lat_final = lat_raw or extracted_lat
		lon_final = lon_raw or extracted_lon
		# ——————————————————————————————————————————————————————————————————

		cr.append("cdr_details", {
			"second_party_number": get("second_party_number"),
			"date_of_communication": parsed_date,
			"duration": frappe.utils.flt(get("duration")),
			"imei": get("imei"),
			"rbs": rbs_clean,
			"latitude": lat_final,
			"longitude": lon_final,
			"call_type": get("call_type"),
			"case_phase": get("case_phase") or cr.case_phase,
		})
		count += 1

	# Auto-fill date range
	if dates:
		sorted_dates = sorted(dates)
		cr.start_date_record = _parse_date(sorted_dates[0], date_format, date_only=True)
		cr.end_date_record = _parse_date(sorted_dates[-1], date_format, date_only=True)

	cr.save()
	frappe.db.commit()

	return {"rows_imported": count, "call_record": call_record}


@frappe.whitelist()
def save_profile(profile_name, mobile_operator=None, header_row=1, date_format=None, mapping_json=None):
	"""Create or overwrite a CDR Import Profile."""
	mapping = json.loads(mapping_json) if mapping_json else {}

	if frappe.db.exists("CDR Import Profile", profile_name):
		doc = frappe.get_doc("CDR Import Profile", profile_name)
		doc.column_mappings = []
	else:
		doc = frappe.new_doc("CDR Import Profile")
		doc.profile_name = profile_name

	doc.mobile_operator = mobile_operator or None
	doc.header_row = int(header_row)
	doc.date_format = date_format or None

	for source, target in mapping.items():
		if source.strip() and target:
			doc.append("column_mappings", {"source_column": source.strip(), "target_field": target})

	doc.save()
	return doc.name


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_path(file_url):
	"""Convert a Frappe file URL to an absolute filesystem path."""
	site = frappe.local.site
	if file_url.startswith("/private/"):
		return os.path.join(frappe.get_site_path(), file_url.lstrip("/"))
	else:
		return os.path.join(frappe.get_site_path("public"), file_url.lstrip("/"))


def _read_file(file_url, header_row=1):
	"""Return (headers, data_rows) from a CSV or Excel file."""
	path = _resolve_path(file_url)
	ext = os.path.splitext(path)[1].lower()
	if ext in (".xlsx", ".xls", ".xlsm"):
		return _read_excel(path, header_row)
	return _read_csv(path, header_row)


def _read_csv(path, header_row=1):
	with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
		content = f.read()

	lines = content.splitlines()
	hi = header_row - 1  # 0-based index of header line

	reader = csv.reader(lines[hi:])
	all_rows = list(reader)
	if not all_rows:
		return [], []

	headers = [h.strip() for h in all_rows[0]]
	data_rows = all_rows[1:]
	return headers, data_rows


def _read_excel(path, header_row=1):
	try:
		import openpyxl
	except ImportError:
		frappe.throw(_("Install openpyxl to import Excel files: pip install openpyxl"))

	wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
	ws = wb.active
	all_rows = list(ws.iter_rows(values_only=True))
	wb.close()

	hi = header_row - 1
	headers = [str(c).strip() if c is not None else "" for c in all_rows[hi]]
	data_rows = [
		[str(c).strip() if c is not None else "" for c in row]
		for row in all_rows[hi + 1:]
	]
	return headers, data_rows


# ──────────────────────────────────────────────────────────────────────────────
# Location / coordinate extraction
# ──────────────────────────────────────────────────────────────────────────────

def _parse_location(raw, separator="|"):
	"""
	Extract (site_name, latitude, longitude) from a raw RBS / location string.

	Handles patterns like:
	  "ABBOTTABAD (4G)|34.2113|73.2281"   → name = "ABBOTTABAD (4G)", lat/lon extracted
	  "SiteName|73.2281|34.2113"          → swaps if values suggest lon-first ordering
	  "LTE_ABT0681__S_Potatoe_research"   → no coords, returns as-is
	  "34.2113,73.2281"                   → bare comma-separated coords

	Always tries separator-based splitting first, then regex-based extraction.
	"""
	if not raw:
		return raw, "", ""
	raw = raw.strip()

	# ── 1. Separator-based split ──────────────────────────────────────────
	if separator:
		parts = [p.strip() for p in raw.split(separator)]
		# Walk parts to find two consecutive coord-looking values
		for i in range(len(parts) - 1):
			a, b = parts[i], parts[i + 1]
			if _is_coord(a) and _is_coord(b):
				lat, lon = _orient_coords(float(a), float(b))
				site_name = separator.join(parts[:i]).strip() or parts[0]
				return site_name, _fmt_coord(lat), _fmt_coord(lon)

	# ── 2. Regex scan for embedded decimals ───────────────────────────────
	candidates = [float(m) for m in _COORD_RE.findall(raw) if _is_coord(m)]
	if len(candidates) >= 2:
		# Use the last two (most likely to be the actual coords)
		lat, lon = _orient_coords(candidates[-2], candidates[-1])
		# Strip coord-looking substrings to get a clean site name
		site_name = _COORD_RE.sub("", raw).strip("|, \t-")
		return site_name or raw, _fmt_coord(lat), _fmt_coord(lon)

	# ── 3. Nothing found — return unchanged ───────────────────────────────
	return raw, "", ""


def _is_coord(value):
	"""Return True if value looks like a geographic coordinate (−180 … 180)."""
	try:
		v = float(value)
		return -180.0 <= v <= 180.0
	except (TypeError, ValueError):
		return False


def _orient_coords(a, b):
	"""
	Return (latitude, longitude) given two candidate numbers.
	Uses Pakistan bounding box heuristic (lat 23–37, lon 60–78) to decide order;
	falls back to |value| ≤ 90 → latitude rule.
	"""
	# Pakistan bounding box
	def in_pk_lat(v): return 23.0 <= v <= 37.5
	def in_pk_lon(v): return 60.0 <= v <= 78.0

	if in_pk_lat(a) and in_pk_lon(b):
		return a, b
	if in_pk_lat(b) and in_pk_lon(a):
		return b, a
	# General rule: latitude is bounded by ±90
	if abs(a) <= 90.0 and abs(b) <= 180.0:
		return a, b
	if abs(b) <= 90.0 and abs(a) <= 180.0:
		return b, a
	return a, b


def _fmt_coord(v):
	"""Format a coordinate to 6 decimal places as a string."""
	return f"{v:.6f}"


_DATE_FORMATS = [
	"%Y-%m-%d %H:%M:%S",
	"%Y-%m-%dT%H:%M:%S",
	"%d/%m/%Y %H:%M:%S",
	"%d/%m/%Y %H:%M",
	"%m/%d/%Y %H:%M:%S",
	"%m/%d/%Y %H:%M",
	"%d-%m-%Y %H:%M:%S",
	"%d-%m-%Y %H:%M",
	"%Y%m%d%H%M%S",
	"%Y-%m-%d",
	"%d/%m/%Y",
	"%d-%m-%Y",
]


def _parse_date(date_str, fmt=None, date_only=False):
	if not date_str or date_str in ("None", "nan", ""):
		return None
	date_str = date_str.strip()

	formats = [fmt] + _DATE_FORMATS if fmt else _DATE_FORMATS
	for f in formats:
		try:
			dt = datetime.strptime(date_str, f)
			return dt.strftime("%Y-%m-%d") if date_only else dt.strftime("%Y-%m-%d %H:%M:%S")
		except (ValueError, TypeError):
			continue

	# Last resort: dateutil
	try:
		from dateutil import parser as du
		dt = du.parse(date_str)
		return dt.strftime("%Y-%m-%d") if date_only else dt.strftime("%Y-%m-%d %H:%M:%S")
	except Exception:
		return date_str
