frappe.pages["cdr-report-pack"].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("CDR Report Pack"),
		single_column: true,
	});

	let $body = $(page.body);
	$body.html(`
		<div style="max-width:720px;">
			<p class="text-muted">${__("Generate CDR, Frequency, RBS and Common Numbers reports as PDFs, bundled in one ZIP (a folder per working number). Pick a Working Number for a single set, or just a Case Project to produce a set for every number in the case.")}</p>
			<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin:10px 0;">
				<div class="ff ff-case" style="min-width:220px;"></div>
				<div class="ff ff-wn" style="min-width:220px;"></div>
				<div class="ff ff-from" style="min-width:180px;"></div>
				<div class="ff ff-to" style="min-width:180px;"></div>
			</div>
			<button class="btn btn-primary" id="rp_go">${__("Generate All Reports (ZIP)")}</button>
			<div id="rp_status" style="margin-top:12px;min-height:22px;"></div>
		</div>
	`);

	function mk(sel, df) {
		let c = frappe.ui.form.make_control({ df: df, parent: $body.find(sel)[0], render_input: true });
		c.refresh();
		return c;
	}
	let f_case = mk(".ff-case", { fieldtype: "Link", options: "Case Project", label: __("Case Project"), fieldname: "case_project" });
	let f_wn = mk(".ff-wn", {
		fieldtype: "Link", options: "Working Number", label: __("Working Number (optional)"), fieldname: "working_number",
		get_query: () => ({ filters: f_case.get_value() ? { case_project: f_case.get_value() } : {} }),
	});
	let f_from = mk(".ff-from", { fieldtype: "Datetime", label: __("From Date"), fieldname: "from_date" });
	let f_to = mk(".ff-to", { fieldtype: "Datetime", label: __("To Date"), fieldname: "to_date" });

	function status(msg, color) {
		$body.find("#rp_status").html(color ? `<span class="text-${color}">${msg}</span>` : msg);
	}

	$body.find("#rp_go").on("click", () => {
		if (!f_case.get_value() && !f_wn.get_value()) {
			frappe.msgprint({ message: __("Select a Case Project or a Working Number."), indicator: "red" });
			return;
		}
		let filters = {
			case_project: f_case.get_value() || null,
			working_number: f_wn.get_value() || null,
			from_date: f_from.get_value() || null,
			to_date: f_to.get_value() || null,
		};
		status(__("Generating reports… this can take a while for a whole case."), "blue");
		frappe.call({
			method: "crms.crms.api.report_pdf.print_all_reports",
			args: { filters: JSON.stringify(filters) },
			freeze: true,
			freeze_message: __("Building report pack…"),
		}).then((r) => {
			if (r.message && r.message.file_url) {
				let m = r.message;
				status(__("Done — {0} working number(s) × {1} reports.", [m.count, m.reports]) +
					` <a href="${m.file_url}" target="_blank"><b>${__("Download ZIP")}</b></a>`, "green");
				window.open(m.message ? m.message : m.file_url, "_blank");
			} else {
				status(__("No reports were generated."), "orange");
			}
		}).catch((e) => status(__("Failed: ") + (e.message || String(e)), "red"));
	});
};
