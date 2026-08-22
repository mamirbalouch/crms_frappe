import frappe

from crms.crms.report.cdr_report_utils import BASE_JOIN, build_conditions


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": "IMEI", "fieldname": "imei", "fieldtype": "Data", "width": 170},
		{"label": "Working Number", "fieldname": "working_mobile_number", "fieldtype": "Data", "width": 140},
		{"label": "Total Events", "fieldname": "total_events", "fieldtype": "Int", "width": 110},
		{"label": "Distinct Contacts", "fieldname": "contacts", "fieldtype": "Int", "width": 140},
		{"label": "First Seen", "fieldname": "first_seen", "fieldtype": "Datetime", "width": 160},
		{"label": "Last Seen", "fieldname": "last_seen", "fieldtype": "Datetime", "width": 160},
	]


def get_data(filters):
	where, values = build_conditions(filters)
	# Exclude blank / placeholder IMEIs
	extra = "dcr.imei IS NOT NULL AND dcr.imei NOT IN ('', 'NIL')"
	where = (where + " AND " + extra) if where else ("WHERE " + extra)
	return frappe.db.sql(
		f"""
		SELECT
			dcr.imei,
			wn.working_mobile_number,
			COUNT(*) AS total_events,
			COUNT(DISTINCT dcr.second_party_number) AS contacts,
			MIN(dcr.date_of_communication) AS first_seen,
			MAX(dcr.date_of_communication) AS last_seen
		{BASE_JOIN}
		{where}
		GROUP BY dcr.imei, wn.working_mobile_number
		ORDER BY total_events DESC
		""",
		values,
		as_dict=True,
	)
