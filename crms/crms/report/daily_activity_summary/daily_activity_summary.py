import frappe

from crms.crms.report.cdr_report_utils import BASE_JOIN, build_conditions


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": "Day", "fieldname": "day", "fieldtype": "Date", "width": 110},
		{"label": "Total Events", "fieldname": "total_events", "fieldtype": "Int", "width": 110},
		{"label": "Out Calls", "fieldname": "out_calls", "fieldtype": "Int", "width": 100},
		{"label": "In Calls", "fieldname": "in_calls", "fieldtype": "Int", "width": 100},
		{"label": "SMS", "fieldname": "sms", "fieldtype": "Int", "width": 80},
		{"label": "Duration (s)", "fieldname": "total_duration", "fieldtype": "Float", "width": 110},
		{"label": "Distinct Contacts", "fieldname": "contacts", "fieldtype": "Int", "width": 140},
		{"label": "Distinct Locations", "fieldname": "locations", "fieldtype": "Int", "width": 150},
	]


def get_data(filters):
	where, values = build_conditions(filters, require_datetime=True)
	return frappe.db.sql(
		f"""
		SELECT
			DATE(dcr.date_of_communication) AS day,
			COUNT(*) AS total_events,
			SUM(dcr.call_type = 'Outgoing Call') AS out_calls,
			SUM(dcr.call_type = 'Incoming Call') AS in_calls,
			SUM(dcr.call_type IN ('Outgoing SMS', 'Incoming SMS')) AS sms,
			SUM(dcr.duration) AS total_duration,
			COUNT(DISTINCT dcr.second_party_number) AS contacts,
			COUNT(DISTINCT dcr.rbs) AS locations
		{BASE_JOIN}
		{where}
		GROUP BY DATE(dcr.date_of_communication)
		ORDER BY day
		""",
		values,
		as_dict=True,
	)
