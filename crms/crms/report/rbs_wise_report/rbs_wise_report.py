from collections import defaultdict

import frappe

from crms.crms.report.cdr_report_utils import fmt_hhmm, trimmed_window


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": "Working Number", "fieldname": "working_mobile_number", "fieldtype": "Data", "width": 140},
		{"label": "RBS (Site / Location)", "fieldname": "rbs", "fieldtype": "Data", "width": 240},
		{"label": "Case", "fieldname": "case_title", "fieldtype": "Data", "width": 140},
		{"label": "Total Hits", "fieldname": "total_hits", "fieldtype": "Int", "width": 90},
		{"label": "Unique Numbers", "fieldname": "unique_numbers", "fieldtype": "Int", "width": 120},
		{"label": "First Time", "fieldname": "first_time", "fieldtype": "Data", "width": 90},
		{"label": "Last Time", "fieldname": "last_time", "fieldtype": "Data", "width": 90},
		{"label": "Latitude", "fieldname": "latitude", "fieldtype": "Data", "width": 100},
		{"label": "Longitude", "fieldname": "longitude", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	conditions = ["dcr.rbs IS NOT NULL", "dcr.rbs != ''", "dcr.date_of_communication IS NOT NULL"]
	values = {}
	if filters.get("case_project"):
		conditions.append("wn.case_project = %(case_project)s")
		values["case_project"] = filters["case_project"]
	if filters.get("working_number"):
		conditions.append("cr.working_number = %(working_number)s")
		values["working_number"] = filters["working_number"]
	if filters.get("from_date"):
		conditions.append("dcr.date_of_communication >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("dcr.date_of_communication <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	where = "WHERE " + " AND ".join(conditions)

	raw = frappe.db.sql(
		f"""
		SELECT
			wn.working_mobile_number,
			dcr.rbs,
			cp.case_title,
			dcr.second_party_number,
			dcr.date_of_communication AS ts,
			dcr.latitude,
			dcr.longitude
		FROM `tabDetail Call Record` dcr
		INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
		INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
		LEFT JOIN `tabCase Project` cp ON wn.case_project = cp.name
		{where}
		""",
		values,
		as_dict=True,
	)

	groups = defaultdict(lambda: {"secs": [], "hours": [], "numbers": set(), "lat": "", "lon": ""})
	for r in raw:
		key = (r["working_mobile_number"], r["rbs"], r["case_title"])
		g = groups[key]
		ts = r["ts"]
		g["secs"].append(ts.hour * 3600 + ts.minute * 60 + ts.second)
		g["hours"].append(ts.hour)
		if r["second_party_number"]:
			g["numbers"].add(r["second_party_number"])
		if r["latitude"]:
			g["lat"] = r["latitude"]
		if r["longitude"]:
			g["lon"] = r["longitude"]

	rows = []
	for (wnum, rbs, case_title), g in groups.items():
		first_s, last_s = trimmed_window(g["secs"], g["hours"])
		rows.append({
			"working_mobile_number": wnum,
			"rbs": rbs,
			"case_title": case_title,
			"total_hits": len(g["secs"]),
			"unique_numbers": len(g["numbers"]),
			"first_time": fmt_hhmm(first_s),
			"last_time": fmt_hhmm(last_s),
			"latitude": g["lat"],
			"longitude": g["lon"],
		})
	rows.sort(key=lambda r: r["total_hits"], reverse=True)
	return rows
