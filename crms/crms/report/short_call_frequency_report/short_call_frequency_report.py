import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Working Number", "fieldname": "working_mobile_number", "fieldtype": "Data", "width": 140},
		{"label": "Second Party Number", "fieldname": "second_party_number", "fieldtype": "Data", "width": 150},
		{"label": "Case", "fieldname": "case_title", "fieldtype": "Data", "width": 140},
		{"label": "Short Calls (≤ threshold)", "fieldname": "short_calls", "fieldtype": "Int", "width": 150},
		{"label": "Total Calls", "fieldname": "total_calls", "fieldtype": "Int", "width": 100},
		{"label": "Short Call %", "fieldname": "short_call_pct", "fieldtype": "Percent", "width": 110},
	]


def get_data(filters):
	conditions = []
	values = {}

	max_duration = filters.get("max_duration") or 10

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

	from crms.permissions import scope_condition
	sc, sv = scope_condition("wn")
	if sc:
		conditions.append(sc)
		values.update(sv)

	where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
	values["max_duration"] = max_duration

	return frappe.db.sql(
		f"""
		SELECT
			dcr.second_party_number,
			wn.working_mobile_number,
			cp.case_title,
			SUM(CASE WHEN dcr.duration <= %(max_duration)s THEN 1 ELSE 0 END) AS short_calls,
			COUNT(dcr.name) AS total_calls,
			ROUND(
				SUM(CASE WHEN dcr.duration <= %(max_duration)s THEN 1 ELSE 0 END) * 100.0 / COUNT(dcr.name), 2
			) AS short_call_pct
		FROM
			`tabDetail Call Record` dcr
			INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
			INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
			LEFT JOIN `tabCase Project` cp ON wn.case_project = cp.name
		{where_clause}
		GROUP BY dcr.second_party_number, wn.working_mobile_number, cp.case_title
		HAVING short_calls > 0
		ORDER BY short_calls DESC
		""",
		values,
		as_dict=True,
	)
