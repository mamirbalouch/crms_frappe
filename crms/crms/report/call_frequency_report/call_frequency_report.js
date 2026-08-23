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
	onload(report) {
		report.page.add_inner_button(__("Download PDF"), () => {
			frappe.call({
				method: "crms.crms.api.report_pdf.render_report_pdf",
				args: { report: "Frequency", filters: JSON.stringify(report.get_values()) },
				freeze: true, freeze_message: __("Generating PDF…"),
			}).then((r) => { if (r.message) window.open(r.message, "_blank"); });
		});
	},
};
