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

# Maximum plausible length of a phone number; anything longer is treated as junk
_MAX_NUM_LEN = 15

# Fallback Call Type used when a raw value can't be classified
_DEFAULT_CALL_TYPE = "Data / Other"

# Maps a lower-cased raw call-type value to a Call Type record name.
# Ported from the switch blocks in the original C# AutoSave_* methods.
_CALL_TYPE_MAP = {
	"outgoing call": "Outgoing Call", "outgoing": "Outgoing Call", "outgoing gsm": "Outgoing Call",
	"outgoing voice": "Outgoing Call", "call - outgoing": "Outgoing Call", "mo": "Outgoing Call", "0": "Outgoing Call",
	"incoming call": "Incoming Call", "incoming": "Incoming Call", "incoming gsm": "Incoming Call",
	"incoming voice": "Incoming Call", "call - incoming": "Incoming Call", "mt": "Incoming Call", "1": "Incoming Call",
	"outgoing sms": "Outgoing SMS", "sms - outgoing": "Outgoing SMS", "smo": "Outgoing SMS", "2": "Outgoing SMS",
	"incoming sms": "Incoming SMS", "sms - incoming": "Incoming SMS", "smt": "Incoming SMS", "3": "Incoming SMS",
}


def _normalize_number(raw):
	"""
	Strip a phone number down to a canonical local form, mirroring the C#
	Exclude92FromNumber logic: drop 0092 / 92 country codes and a leading 0.
	Returns "" for empty or implausibly long (junk) values.
	"""
	if raw is None:
		return ""
	s = re.sub(r"\D", "", str(raw))
	if not s or len(s) > _MAX_NUM_LEN:
		return ""
	if s.startswith("0092"):
		s = s[4:]
	elif s.startswith("92") and len(s) > 10:
		s = s[2:]
	if s.startswith("0"):
		s = s[1:]
	return s


def _valid_call_types():
	"""Set of existing Call Type record names (cached per request)."""
	if not hasattr(frappe.local, "_cdr_call_types"):
		frappe.local._cdr_call_types = set(frappe.get_all("Call Type", pluck="name"))
	return frappe.local._cdr_call_types


def _normalize_call_type(raw, valid=None):
	"""
	Map a raw call-type string to a valid Call Type record name, or None.
	Never returns a value that isn't an existing Call Type (which would break
	the Link field on save).
	"""
	if valid is None:
		valid = _valid_call_types()
	if not raw:
		return None
	key = str(raw).strip().lower()
	name = _CALL_TYPE_MAP.get(key)
	if not name:
		# Loose classification for combined / unseen strings
		is_sms = "sms" in key
		if "out" in key or "mo" == key:
			name = "Outgoing SMS" if is_sms else "Outgoing Call"
		elif "in" in key or "mt" == key:
			name = "Incoming SMS" if is_sms else "Incoming Call"
		else:
			name = _DEFAULT_CALL_TYPE
	if name in valid:
		return name
	return _DEFAULT_CALL_TYPE if _DEFAULT_CALL_TYPE in valid else None

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
	Returns {profile, operator, score, mapping} or {profile: null}.

	`mapping` is the best profile's {source_column: target_field} dict, resolved
	server-side so the browser never has to query the CDR Profile Column child
	table directly (which it has no read permission on).
	"""
	headers = [h for h in json.loads(headers_json) if h and h.strip()]
	name, operator, mapping, score = _best_profile_for_headers(headers)
	if name:
		return {"profile": name, "operator": operator, "score": round(score, 2), "mapping": mapping}
	return {"profile": None, "score": round(score, 2), "mapping": {}}


def _best_profile_for_headers(headers, min_score=0.6):
	"""
	Score every CDR Import Profile against a file's header list and return
	(profile_name, mobile_operator, mapping, score) for the best match, or
	(None, None, {}, best_score) if nothing clears min_score.
	"""
	header_set = {h.strip() for h in headers if h and h.strip()}
	if not header_set:
		return None, None, {}, 0.0

	profiles = frappe.get_all("CDR Import Profile", fields=["name", "mobile_operator"])
	best, best_op, best_mapping, best_score = None, None, {}, 0.0

	for p in profiles:
		mappings = frappe.get_all(
			"CDR Profile Column",
			filters={"parent": p.name},
			fields=["source_column", "target_field"],
			order_by=None,
		)
		if not mappings:
			continue
		profile_cols = {m.source_column.strip() for m in mappings}
		score = len(header_set & profile_cols) / len(profile_cols)
		if score > best_score:
			best_score = score
			best = p.name
			best_op = p.mobile_operator
			best_mapping = {m.source_column.strip(): m.target_field for m in mappings}

	if best_score >= min_score:
		return best, best_op, best_mapping, best_score
	return None, None, {}, best_score


@frappe.whitelist()
def get_profile_mapping(profile_name):
	"""
	Return {source_column: target_field} for a saved CDR Import Profile.
	Server-side so callers avoid querying the CDR Profile Column child table
	(which has no direct read permission). Read permission on the parent
	CDR Import Profile is enforced.
	"""
	profile = frappe.get_doc("CDR Import Profile", profile_name)
	profile.check_permission("read")
	return {m.source_column.strip(): m.target_field for m in profile.column_mappings}


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
	cr = frappe.get_doc("Call Record", call_record)
	count = _import_rows(cr, headers, rows, mapping, date_format, rbs_coord_separator)
	cr.save()
	frappe.db.commit()

	return {"rows_imported": count, "call_record": call_record}


def _import_rows(cr, headers, rows, mapping, date_format=None, rbs_coord_separator="|"):
	"""
	Append CDR detail rows to a Call Record document (does NOT save).

	Shared by single-file and bulk import. Applies the hardening the raw C#
	logic relied on: phone-number normalization, call-type normalization to a
	valid Call Type link, a sentinel for blank second-party numbers, and a
	chronological (parsed) date range.
	Returns the number of rows appended.
	"""
	# Build target_field → column index lookup
	col_idx = {}
	for i, h in enumerate(headers):
		h = h.strip()
		if h in mapping:
			col_idx[mapping[h]] = i

	valid_call_types = _valid_call_types()
	parsed_dates = []
	count = 0

	for row in rows:
		row = [str(c).strip() if c is not None else "" for c in row]
		if not any(row):
			continue

		def get(field):
			i = col_idx.get(field)
			return row[i] if i is not None and i < len(row) else ""

		parsed_date = _parse_date(get("date_of_communication"), date_format)
		if parsed_date:
			parsed_dates.append(parsed_date)

		# Second party number — normalize; blank/junk falls back to "1" (mandatory field)
		number = _normalize_number(get("second_party_number")) or "1"

		# Duration — total seconds, combining a separate minutes column when the
		# format splits it (e.g. Zong MINS + SECS).
		duration = frappe.utils.flt(get("duration")) + frappe.utils.flt(get("duration_minutes")) * 60

		# Resolve RBS and coordinates
		rbs_raw = get("rbs_with_coords") or get("rbs")
		lat_raw = get("latitude")
		lon_raw = get("longitude")
		if rbs_raw:
			rbs_clean, extracted_lat, extracted_lon = _parse_location(rbs_raw, rbs_coord_separator)
		else:
			rbs_clean, extracted_lat, extracted_lon = rbs_raw, "", ""
		lat_final = lat_raw or extracted_lat
		lon_final = lon_raw or extracted_lon

		cr.append("cdr_details", {
			"second_party_number": number,
			"date_of_communication": parsed_date,
			"duration": duration,
			"imei": get("imei"),
			"rbs": (rbs_clean or "")[:500],
			"latitude": lat_final,
			"longitude": lon_final,
			"call_type": _normalize_call_type(get("call_type"), valid_call_types),
			"case_phase": get("case_phase") or cr.case_phase,
		})
		count += 1

	# Auto-fill date range (parsed strings are YYYY-MM-DD… so lexical sort == chronological)
	if parsed_dates:
		parsed_dates.sort()
		cr.start_date_record = parsed_dates[0][:10]
		cr.end_date_record = parsed_dates[-1][:10]

	return count


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


@frappe.whitelist()
def bulk_import_file(case_project, file_url, filename, default_operator=None, default_case_phase=None):
	"""
	Process ONE CDR file end-to-end for the batch uploader:

	  1. Parse <number> - <description> out of the filename.
	  2. Find or create the Working Number (by normalized number + Case Project).
	  3. Auto-detect the header row (skipping blank/preamble rows) and the profile.
	  4. Create a Call Record for that Working Number.
	  5. Import the detail rows.

	Returns a per-file result dict; it catches its own errors so the caller can
	keep going through the rest of the batch.
	"""
	result = {"filename": filename, "status": "error", "message": "", "rows": 0}
	try:
		if not frappe.db.exists("Case Project", case_project):
			frappe.throw(_("Case Project {0} not found.").format(case_project))

		number, description = _parse_filename(filename)
		number = _normalize_number(number)
		if not number:
			frappe.throw(_("Could not read a mobile number from the file name."))

		# Read + auto-detect header row, then detect profile
		all_rows = _read_all_rows(file_url)
		if not all_rows:
			frappe.throw(_("File is empty."))
		header_row = _detect_header_row(all_rows)
		headers, rows = _split_at_header(all_rows, header_row)

		profile_name, profile_op, mapping, score = _best_profile_for_headers(headers)
		if not mapping:
			frappe.throw(_("No import profile matched this file's columns."))

		operator = profile_op or default_operator
		profile = frappe.get_doc("CDR Import Profile", profile_name)
		rbs_sep = profile.rbs_coord_separator if profile.rbs_coord_separator is not None else "|"
		date_format = profile.date_format or None

		# Upsert Working Number
		wn, wn_created = _upsert_working_number(
			number, case_project, description, operator, default_case_phase
		)

		# Create the Call Record
		cr = frappe.get_doc({
			"doctype": "Call Record",
			"working_number": wn.name,
			"case_phase": wn.case_phase,
		})
		cr.insert()

		count = _import_rows(cr, headers, rows, mapping, date_format, rbs_sep)
		cr.save()
		frappe.db.commit()

		result.update({
			"status": "ok",
			"rows": count,
			"number": number,
			"working_number": wn.name,
			"working_number_created": wn_created,
			"call_record": cr.name,
			"profile": profile_name,
			"header_row": header_row,
		})
	except Exception as e:
		frappe.db.rollback()
		result["message"] = str(e)
		frappe.log_error(frappe.get_traceback(), f"Bulk CDR import failed: {filename}")
	return result


def _parse_filename(filename):
	"""
	Split "<number> - <description>" from a file name into (digits, description).

	The number and description are separated by " - " (a dash with surrounding
	spaces). The number itself may contain dashes or spaces, which are stripped:
	  "0324-8878036 - LHR CARD LOAD - BY KHALIL" -> ("03248878036", "LHR CARD LOAD - BY KHALIL")
	  "0324 8878036 - LHR CARD LOAD"             -> ("03248878036", "LHR CARD LOAD")
	  "923322290119 - rm gv - new case"          -> ("923322290119", "rm gv - new case")
	Returns ("", "") if no leading number is present.
	"""
	base = os.path.splitext(os.path.basename(filename))[0]

	# Primary: split on the first spaced dash " - " (the number/description delimiter)
	parts = re.split(r"\s+[-–]\s+", base, maxsplit=1)
	if len(parts) == 2:
		left, desc = parts[0], parts[1].strip()
	else:
		# No spaced delimiter: take the leading number-ish run, rest is description
		m = re.match(r"^[\s+\d\-–]+", base)
		if m:
			left, desc = m.group(0), base[m.end():].strip(" -–")
		else:
			left, desc = base, ""

	return re.sub(r"\D", "", left), desc


def _upsert_working_number(number, case_project, description, operator, default_case_phase):
	"""
	Return (working_number_doc, created_bool). Reuses an existing Working Number
	for the same number + Case Project; otherwise creates one.
	"""
	existing = frappe.db.get_value(
		"Working Number",
		{"working_mobile_number": number, "case_project": case_project},
		"name",
	)
	if existing:
		wn = frappe.get_doc("Working Number", existing)
		if description and not wn.owner_name:
			wn.owner_name = description
			wn.save()
		return wn, False

	if not operator:
		frappe.throw(_("Mobile Operator is required but could not be detected — set a default operator for the batch."))

	case_phase = default_case_phase or frappe.db.get_value("Case Project", case_project, "case_phase")
	wn = frappe.get_doc({
		"doctype": "Working Number",
		"working_mobile_number": number,
		"case_project": case_project,
		"mobile_operator": operator,
		"case_phase": case_phase,
		"owner_name": description,
		"date_of_entry": frappe.utils.today(),
	})
	wn.insert()
	return wn, True


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
	"""Return (headers, data_rows) from a CSV or Excel file at a fixed header row."""
	all_rows = _read_all_rows(file_url)
	if not all_rows:
		return [], []
	return _split_at_header(all_rows, int(header_row))


def _read_all_rows(file_url):
	"""Return every row of a CSV/Excel file as a list of lists of stripped strings."""
	path = _resolve_path(file_url)
	ext = os.path.splitext(path)[1].lower()
	if ext in (".xlsx", ".xlsm"):
		return _read_excel_rows(path)
	if ext == ".xls":
		frappe.throw(_("Legacy .xls files aren't supported — please save as .xlsx or CSV."))
	return _read_csv_rows(path)


def _read_csv_rows(path):
	with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
		content = f.read()
	reader = csv.reader(content.splitlines())
	return [[(c or "").strip() for c in row] for row in reader]


def _read_excel_rows(path):
	try:
		import openpyxl
	except ImportError:
		frappe.throw(_("Install openpyxl to import Excel files: pip install openpyxl"))

	wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
	ws = wb.active
	rows = [
		[str(c).strip() if c is not None else "" for c in row]
		for row in ws.iter_rows(values_only=True)
	]
	wb.close()
	return rows


def _split_at_header(all_rows, header_row):
	"""Split a full row list into (headers, data_rows) at a 1-based header row."""
	hi = max(header_row - 1, 0)
	if hi >= len(all_rows):
		return [], []
	headers = [str(c).strip() if c is not None else "" for c in all_rows[hi]]
	return headers, all_rows[hi + 1:]


def _detect_header_row(all_rows, max_scan=15):
	"""
	Return the 1-based row number that best matches known profile columns, so
	files with blank/preamble rows above the header import without hand-cleaning.
	Falls back to the first non-empty row when nothing matches.
	"""
	profile_cols = {
		m.source_column.strip().lower()
		for m in frappe.get_all("CDR Profile Column", fields=["source_column"])
		if m.source_column
	}

	best_i, best_score, first_non_empty = None, 0, None
	for i, row in enumerate(all_rows[:max_scan]):
		cells = {str(c).strip().lower() for c in row if c is not None and str(c).strip()}
		if not cells:
			continue
		if first_non_empty is None:
			first_non_empty = i
		score = len(cells & profile_cols)
		if score > best_score:
			best_score = score
			best_i = i

	chosen = best_i if best_i is not None else (first_non_empty or 0)
	return chosen + 1


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
