frappe.query_reports["Short Call Frequency Report"] = {
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
		{
			fieldname: "max_duration",
			label: __("Max Duration (seconds)"),
			fieldtype: "Int",
			default: 10,
		},
	],
};
