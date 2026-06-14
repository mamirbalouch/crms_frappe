frappe.query_reports["Call Frequency Report"] = {
	filters: [
		{
			fieldname: "case_project",
			label: __("Case Project"),
			fieldtype: "Link",
			options: "Case Project",
		},
		{
			fieldname: "working_number",
			label: __("Working Number"),
			fieldtype: "Link",
			options: "Working Number",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Datetime",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Datetime",
		},
	],
};
