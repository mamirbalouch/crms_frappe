frappe.query_reports["Call Detail Record Report"] = {
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
			get_query: function () {
				let case_project = frappe.query_report.get_filter_value("case_project");
				return { filters: case_project ? { case_project: case_project } : {} };
			},
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
			fieldname: "call_type",
			label: __("Call Type"),
			fieldtype: "Link",
			options: "Call Type",
		},
	],
	onload(report) {
		report.page.add_inner_button(__("Download PDF"), () => {
			frappe.call({
				method: "crms.crms.api.report_pdf.render_report_pdf",
				args: { report: "CDR", filters: JSON.stringify(report.get_values()) },
				freeze: true, freeze_message: __("Generating PDF…"),
			}).then((r) => { if (r.message) window.open(r.message, "_blank"); });
		});
	},
};
