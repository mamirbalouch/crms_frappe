import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "RBS (Cell Tower)", "fieldname": "rbs", "fieldtype": "Data", "width": 150},
		{"label": "Working Number", "fieldname": "working_number", "fieldtype": "Link", "options": "Working Number", "width": 140},
		{"label": "Case Project", "fieldname": "case_project", "fieldtype": "Link", "options": "Case Project", "width": 140},
		{"label": "Total Hits", "fieldname": "total_hits", "fieldtype": "Int", "width": 100},
		{"label": "Unique Numbers", "fieldname": "unique_numbers", "fieldtype": "Int", "width": 120},
		{"label": "First Seen", "fieldname": "first_seen", "fieldtype": "Datetime", "width": 150},
		{"label": "Last Seen", "fieldname": "last_seen", "fieldtype": "Datetime", "width": 150},
		{"label": "Latitude", "fieldname": "latitude", "fieldtype": "Data", "width": 100},
		{"label": "Longitude", "fieldname": "longitude", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	conditions = []
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

	conditions.append("dcr.rbs IS NOT NULL AND dcr.rbs != ''")

	where_clause = "WHERE " + " AND ".join(conditions)

	return frappe.db.sql(
		f"""
		SELECT
			dcr.rbs,
			cr.working_number,
			wn.case_project,
			COUNT(dcr.name) AS total_hits,
			COUNT(DISTINCT dcr.second_party_number) AS unique_numbers,
			MIN(dcr.date_of_communication) AS first_seen,
			MAX(dcr.date_of_communication) AS last_seen,
			MAX(dcr.latitude) AS latitude,
			MAX(dcr.longitude) AS longitude
		FROM
			`tabDetail Call Record` dcr
			INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
			INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
		{where_clause}
		GROUP BY dcr.rbs, cr.working_number, wn.case_project
		ORDER BY total_hits DESC
		""",
		values,
		as_dict=True,
	)
