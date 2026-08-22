from collections import defaultdict

import frappe

from crms.crms.report.cdr_report_utils import BASE_JOIN, build_conditions, fmt_hhmm, trimmed_window

# DAYOFWEEK(): 1=Sunday … 7=Saturday
_DAYS = [
	(1, "sunday", "Sunday"),
	(2, "monday", "Monday"),
	(3, "tuesday", "Tuesday"),
	(4, "wednesday", "Wednesday"),
	(5, "thursday", "Thursday"),
	(6, "friday", "Friday"),
	(7, "saturday", "Saturday"),
]


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	cols = [
		{"label": "RBS (Site / Location)", "fieldname": "rbs", "fieldtype": "Data", "width": 260},
		{"label": "Usual (All Days)", "fieldname": "usual", "fieldtype": "Data", "width": 130},
	]
	for _, fn, lbl in _DAYS:
		cols.append({"label": lbl, "fieldname": fn, "fieldtype": "Data", "width": 120})
	cols.append({"label": "Total Hits", "fieldname": "total", "fieldtype": "Int", "width": 90})
	return cols


def get_data(filters):
	where, values = build_conditions(filters, require_datetime=True)
	where = (where + " AND " if where else "WHERE ") + "dcr.rbs IS NOT NULL AND dcr.rbs != ''"
	raw = frappe.db.sql(
		f"""
		SELECT
			dcr.rbs,
			DAYOFWEEK(dcr.date_of_communication) AS dow,
			dcr.date_of_communication AS ts
		{BASE_JOIN}
		{where}
		""",
		values,
		as_dict=True,
	)

	dow_field = {d: fn for d, fn, _ in _DAYS}
	# per RBS: all secs/hours (for the usual window) + per-weekday secs
	agg = defaultdict(lambda: {"secs": [], "hours": [], "days": defaultdict(list)})
	for r in raw:
		ts = r["ts"]
		s = ts.hour * 3600 + ts.minute * 60 + ts.second
		g = agg[r["rbs"]]
		g["secs"].append(s)
		g["hours"].append(ts.hour)
		fn = dow_field.get(int(r["dow"]))
		if fn:
			g["days"][fn].append(s)

	rows = []
	for rbs, g in agg.items():
		first_s, last_s = trimmed_window(g["secs"], g["hours"])
		row = {"rbs": rbs, "usual": f"{fmt_hhmm(first_s)}–{fmt_hhmm(last_s)}", "total": len(g["secs"])}
		for _, fn, _lbl in _DAYS:
			day_secs = g["days"].get(fn)
			row[fn] = f"{fmt_hhmm(min(day_secs))}–{fmt_hhmm(max(day_secs))}" if day_secs else ""
		rows.append(row)
	rows.sort(key=lambda r: r["total"], reverse=True)
	return rows
