from collections import defaultdict

import frappe

from crms.crms.report.cdr_report_utils import BASE_JOIN, build_conditions

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
	cols = [{"label": "B-Number", "fieldname": "b_number", "fieldtype": "Data", "width": 150}]
	for _, fn, lbl in _DAYS:
		cols.append({"label": lbl, "fieldname": fn, "fieldtype": "Int", "width": 90})
	cols.append({"label": "Total", "fieldname": "total", "fieldtype": "Int", "width": 90})
	return cols


def get_data(filters):
	where, values = build_conditions(filters, require_datetime=True)
	where = (where + " AND " if where else "WHERE ") + "dcr.second_party_number NOT IN ('', '1')"
	raw = frappe.db.sql(
		f"""
		SELECT
			dcr.second_party_number AS bnum,
			DAYOFWEEK(dcr.date_of_communication) AS dow,
			COUNT(*) AS cnt
		{BASE_JOIN}
		{where}
		GROUP BY dcr.second_party_number, dow
		""",
		values,
		as_dict=True,
	)

	dow_field = {d: fn for d, fn, _ in _DAYS}
	pivot = defaultdict(lambda: {fn: 0 for _, fn, _ in _DAYS} | {"total": 0})
	for r in raw:
		row = pivot[r["bnum"]]
		fn = dow_field.get(int(r["dow"]))
		if fn:
			row[fn] += r["cnt"]
			row["total"] += r["cnt"]

	rows = [{"b_number": bnum, **vals} for bnum, vals in pivot.items()]
	rows.sort(key=lambda r: r["total"], reverse=True)
	return rows
