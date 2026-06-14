import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "CDR#", "fieldname": "call_record", "fieldtype": "Link", "options": "Call Record", "width": 120},
		{"label": "Working Number", "fieldname": "working_number", "fieldtype": "Link", "options": "Working Number", "width": 140},
		{"label": "Case Project", "fieldname": "case_project", "fieldtype": "Link", "options": "Case Project", "width": 140},
		{"label": "Second Party", "fieldname": "second_party_number", "fieldtype": "Data", "width": 130},
		{"label": "Call Type", "fieldname": "call_type", "fieldtype": "Link", "options": "Call Type", "width": 100},
		{"label": "Date & Time", "fieldname": "date_of_communication", "fieldtype": "Datetime", "width": 150},
		{"label": "Duration (s)", "fieldname": "duration", "fieldtype": "Float", "width": 100},
		{"label": "IMEI", "fieldname": "imei", "fieldtype": "Data", "width": 150},
		{"label": "RBS", "fieldname": "rbs", "fieldtype": "Data", "width": 120},
		{"label": "Latitude", "fieldname": "latitude", "fieldtype": "Data", "width": 100},
		{"label": "Longitude", "fieldname": "longitude", "fieldtype": "Data", "width": 100},
		{"label": "Case Phase", "fieldname": "case_phase", "fieldtype": "Link", "options": "Case Phase", "width": 110},
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

	if filters.get("call_type"):
		conditions.append("dcr.call_type = %(call_type)s")
		values["call_type"] = filters["call_type"]

	where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

	return frappe.db.sql(
		f"""
		SELECT
			cr.name AS call_record,
			cr.working_number,
			wn.case_project,
			dcr.second_party_number,
			dcr.call_type,
			dcr.date_of_communication,
			dcr.duration,
			dcr.imei,
			dcr.rbs,
			dcr.latitude,
			dcr.longitude,
			dcr.case_phase
		FROM
			`tabDetail Call Record` dcr
			INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
			INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
		{where_clause}
		ORDER BY dcr.date_of_communication DESC
		""",
		values,
		as_dict=True,
	)
