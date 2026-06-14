import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Second Party Number", "fieldname": "second_party_number", "fieldtype": "Data", "width": 150},
		{"label": "Working Number", "fieldname": "working_number", "fieldtype": "Link", "options": "Working Number", "width": 140},
		{"label": "Case Project", "fieldname": "case_project", "fieldtype": "Link", "options": "Case Project", "width": 140},
		{"label": "Total Calls", "fieldname": "total_calls", "fieldtype": "Int", "width": 100},
		{"label": "Total Duration (s)", "fieldname": "total_duration", "fieldtype": "Float", "width": 130},
		{"label": "First Contact", "fieldname": "first_contact", "fieldtype": "Datetime", "width": 150},
		{"label": "Last Contact", "fieldname": "last_contact", "fieldtype": "Datetime", "width": 150},
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

	where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

	return frappe.db.sql(
		f"""
		SELECT
			dcr.second_party_number,
			cr.working_number,
			wn.case_project,
			COUNT(dcr.name) AS total_calls,
			SUM(dcr.duration) AS total_duration,
			MIN(dcr.date_of_communication) AS first_contact,
			MAX(dcr.date_of_communication) AS last_contact
		FROM
			`tabDetail Call Record` dcr
			INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
			INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
		{where_clause}
		GROUP BY dcr.second_party_number, cr.working_number, wn.case_project
		ORDER BY total_calls DESC
		""",
		values,
		as_dict=True,
	)
