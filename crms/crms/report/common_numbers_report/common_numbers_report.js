frappe.query_reports["Common Numbers Report"] = {
	filters: [
		{
			fieldname: "case_project",
			label: __("Case Project"),
			fieldtype: "Link",
			options: "Case Project",
			reqd: 1,
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
