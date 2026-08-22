frappe.query_reports["Common Numbers Report"] = {
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
		{ fieldname: "min_digits", label: __("Min Digits"), fieldtype: "Int", default: 10 },
		{ fieldname: "max_digits", label: __("Max Digits"), fieldtype: "Int", default: 14 },
	],

	// Row coloring by how the two working numbers relate:
	//   Same Case & Phase   → normal
	//   Same Case, Diff Phase → amber
	//   Different Case      → red (most prominent)
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.relationship) {
			let bg = null;
			if (data.relationship === "Different Case") bg = "#f5c2c7";
			else if (data.relationship === "Same Case, Diff Phase") bg = "#ffe69c";
			if (bg) {
				value = `<div style="background-color:${bg};margin:-5px -8px;padding:5px 8px;">${value}</div>`;
			}
		}
		return value;
	},
};
