frappe.ui.form.on("Case Project", {
	refresh(frm) {
		frm.add_custom_button(__("Working Numbers"), function () {
			frappe.set_route("List", "Working Number", { case_project: frm.doc.name });
		}, __("View"));

		frm.add_custom_button(__("Geo Locations"), function () {
			frappe.set_route("List", "Geo Location", { case_project: frm.doc.name });
		}, __("View"));
	},
});
