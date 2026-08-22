import frappe


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": "Common Number", "fieldname": "common_number", "fieldtype": "Data", "width": 130},
		{"label": "Working Number A", "fieldname": "wn1", "fieldtype": "Data", "width": 130},
		{"label": "Case A", "fieldname": "case1", "fieldtype": "Data", "width": 130},
		{"label": "Phase A", "fieldname": "phase1", "fieldtype": "Data", "width": 100},
		{"label": "Calls A↔Common", "fieldname": "calls1", "fieldtype": "Int", "width": 120},
		{"label": "Working Number B", "fieldname": "wn2", "fieldtype": "Data", "width": 130},
		{"label": "Case B", "fieldname": "case2", "fieldtype": "Data", "width": 130},
		{"label": "Phase B", "fieldname": "phase2", "fieldtype": "Data", "width": 100},
		{"label": "Calls B↔Common", "fieldname": "calls2", "fieldtype": "Int", "width": 120},
		{"label": "Relationship", "fieldname": "relationship", "fieldtype": "Data", "width": 160},
	]


def get_data(filters):
	# Filters that constrain which CDR rows form the contact set
	# Keep only real mobile / foreign numbers by digit length:
	#   ~10 = local mobile (3332182838), 11–14 = foreign with country code.
	#   Shorter = short codes / partials, longer = junk (IMEI-like).
	min_len = int(filters.get("min_digits") or 10)
	max_len = int(filters.get("max_digits") or 14)
	contact_conditions = [
		"dcr.second_party_number IS NOT NULL",
		"dcr.second_party_number NOT IN ('', '1')",
		"LENGTH(dcr.second_party_number) BETWEEN %(min_len)s AND %(max_len)s",
	]
	values = {"min_len": min_len, "max_len": max_len}
	if filters.get("from_date"):
		contact_conditions.append("dcr.date_of_communication >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		contact_conditions.append("dcr.date_of_communication <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	contact_where = "WHERE " + " AND ".join(contact_conditions)

	# Filters that scope which pairs to show (at least one side must match)
	outer = []
	if filters.get("case_project"):
		outer.append("(c1.case_project = %(case_project)s OR c2.case_project = %(case_project)s)")
		values["case_project"] = filters["case_project"]
	if filters.get("working_number"):
		outer.append("(c1.wn = %(working_number)s OR c2.wn = %(working_number)s)")
		values["working_number"] = filters["working_number"]
	outer_where = ("WHERE " + " AND ".join(outer)) if outer else ""

	rows = frappe.db.sql(
		f"""
		WITH contacts AS (
			SELECT
				wn.name AS wn,
				wn.working_mobile_number AS wnum,
				wn.case_project AS case_project,
				wn.case_phase AS case_phase,
				dcr.second_party_number AS bnum,
				COUNT(*) AS calls
			FROM `tabDetail Call Record` dcr
			INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
			INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
			{contact_where}
			GROUP BY wn.name, dcr.second_party_number
		)
		SELECT
			c1.bnum  AS common_number,
			c1.wnum  AS wn1, c1.case_project AS cp1, c1.case_phase AS phase1, c1.calls AS calls1,
			cpt1.case_title AS case1,
			c2.wnum  AS wn2, c2.case_project AS cp2, c2.case_phase AS phase2, c2.calls AS calls2,
			cpt2.case_title AS case2
		FROM contacts c1
		INNER JOIN contacts c2 ON c1.bnum = c2.bnum AND c1.wn < c2.wn
		LEFT JOIN `tabCase Project` cpt1 ON c1.case_project = cpt1.name
		LEFT JOIN `tabCase Project` cpt2 ON c2.case_project = cpt2.name
		{outer_where}
		ORDER BY c1.bnum, c1.wnum, c2.wnum
		""",
		values,
		as_dict=True,
	)

	for r in rows:
		same_case = r["cp1"] == r["cp2"]
		same_phase = (r.get("phase1") or "") == (r.get("phase2") or "")
		if same_case and same_phase:
			r["relationship"] = "Same Case & Phase"
		elif same_case:
			r["relationship"] = "Same Case, Diff Phase"
		else:
			r["relationship"] = "Different Case"
	return rows
