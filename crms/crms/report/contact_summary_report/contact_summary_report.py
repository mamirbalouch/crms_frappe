import frappe

from crms.crms.report.cdr_report_utils import BASE_JOIN, build_conditions


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": "Second Party Number", "fieldname": "second_party_number", "fieldtype": "Data", "width": 160},
		{"label": "Total Events", "fieldname": "total_events", "fieldtype": "Int", "width": 110},
		{"label": "Out Calls", "fieldname": "out_calls", "fieldtype": "Int", "width": 100},
		{"label": "In Calls", "fieldname": "in_calls", "fieldtype": "Int", "width": 100},
		{"label": "SMS", "fieldname": "sms", "fieldtype": "Int", "width": 80},
		{"label": "Duration (s)", "fieldname": "total_duration", "fieldtype": "Float", "width": 110},
		{"label": "First Contact", "fieldname": "first_contact", "fieldtype": "Datetime", "width": 160},
		{"label": "Last Contact", "fieldname": "last_contact", "fieldtype": "Datetime", "width": 160},
	]


def get_data(filters):
	where, values = build_conditions(filters)
	# Ignore the "1" sentinel used for blank/unparseable numbers
	extra = "dcr.second_party_number IS NOT NULL AND dcr.second_party_number NOT IN ('', '1')"
	where = (where + " AND " + extra) if where else ("WHERE " + extra)
	return frappe.db.sql(
		f"""
		SELECT
			dcr.second_party_number,
			COUNT(*) AS total_events,
			SUM(dcr.call_type = 'Outgoing Call') AS out_calls,
			SUM(dcr.call_type = 'Incoming Call') AS in_calls,
			SUM(dcr.call_type IN ('Outgoing SMS', 'Incoming SMS')) AS sms,
			SUM(dcr.duration) AS total_duration,
			MIN(dcr.date_of_communication) AS first_contact,
			MAX(dcr.date_of_communication) AS last_contact
		{BASE_JOIN}
		{where}
		GROUP BY dcr.second_party_number
		ORDER BY total_events DESC
		""",
		values,
		as_dict=True,
	)
