import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Common Number", "fieldname": "second_party_number", "fieldtype": "Data", "width": 150},
		{"label": "Working Numbers Count", "fieldname": "working_number_count", "fieldtype": "Int", "width": 160},
		{"label": "Working Numbers", "fieldname": "working_numbers", "fieldtype": "Data", "width": 300},
		{"label": "Total Calls", "fieldname": "total_calls", "fieldtype": "Int", "width": 100},
		{"label": "Total Duration (s)", "fieldname": "total_duration", "fieldtype": "Float", "width": 130},
	]


def get_data(filters):
	conditions = []
	values = {}

	if filters.get("case_project"):
		conditions.append("wn.case_project = %(case_project)s")
		values["case_project"] = filters["case_project"]

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
			COUNT(DISTINCT cr.working_number) AS working_number_count,
			GROUP_CONCAT(DISTINCT cr.working_number ORDER BY cr.working_number SEPARATOR ', ') AS working_numbers,
			COUNT(dcr.name) AS total_calls,
			SUM(dcr.duration) AS total_duration
		FROM
			`tabDetail Call Record` dcr
			INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
			INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
		{where_clause}
		GROUP BY dcr.second_party_number
		HAVING COUNT(DISTINCT cr.working_number) > 1
		ORDER BY working_number_count DESC, total_calls DESC
		""",
		values,
		as_dict=True,
	)
