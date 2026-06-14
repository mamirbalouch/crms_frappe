frappe.ui.form.on("Working Number", {
	refresh(frm) {
		frm.add_custom_button(__("Call Records"), function () {
			frappe.set_route("List", "Call Record", { working_number: frm.doc.name });
		}, __("View"));
	},
});
