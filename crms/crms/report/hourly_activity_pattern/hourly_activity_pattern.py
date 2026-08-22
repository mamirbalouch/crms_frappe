import frappe

from crms.crms.report.cdr_report_utils import BASE_JOIN, build_conditions

# Rows are grouped into day/night buckets to surface odd-hour activity.
_NIGHT_HOURS = set(range(0, 6))  # 00:00–05:59


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": "Hour", "fieldname": "hour_label", "fieldtype": "Data", "width": 110},
		{"label": "Part of Day", "fieldname": "part_of_day", "fieldtype": "Data", "width": 110},
		{"label": "Total Events", "fieldname": "total_events", "fieldtype": "Int", "width": 120},
		{"label": "Out Calls", "fieldname": "out_calls", "fieldtype": "Int", "width": 100},
		{"label": "In Calls", "fieldname": "in_calls", "fieldtype": "Int", "width": 100},
		{"label": "SMS", "fieldname": "sms", "fieldtype": "Int", "width": 80},
		{"label": "Duration (s)", "fieldname": "total_duration", "fieldtype": "Float", "width": 110},
	]


def get_data(filters):
	where, values = build_conditions(filters, require_datetime=True)
	rows = frappe.db.sql(
		f"""
		SELECT
			HOUR(dcr.date_of_communication) AS hour,
			COUNT(*) AS total_events,
			SUM(dcr.call_type = 'Outgoing Call') AS out_calls,
			SUM(dcr.call_type = 'Incoming Call') AS in_calls,
			SUM(dcr.call_type IN ('Outgoing SMS', 'Incoming SMS')) AS sms,
			SUM(dcr.duration) AS total_duration
		{BASE_JOIN}
		{where}
		GROUP BY HOUR(dcr.date_of_communication)
		ORDER BY hour
		""",
		values,
		as_dict=True,
	)
	for r in rows:
		h = int(r["hour"])
		r["hour_label"] = f"{h:02d}:00 – {h:02d}:59"
		r["part_of_day"] = "Night" if h in _NIGHT_HOURS else "Day"
	return rows
