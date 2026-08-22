frappe.query_reports["Weekday RBS Activity"] = {
	filters: [
		{ fieldname: "case_project", label: __("Case Project"), fieldtype: "Link", options: "Case Project" },
		{
			fieldname: "working_number",
			label: __("Working Number"),
			fieldtype: "Link",
			options: "Working Number",
			get_query: function () {
				let cp = frappe.query_report.get_filter_value("case_project");
				return { filters: cp ? { case_project: cp } : {} };
			},
		},
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Datetime" },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Datetime" },
	],
};
