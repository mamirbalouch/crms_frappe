frappe.ui.form.on("CDR Bulk Import", {
	refresh(frm) {
		render_file_picker(frm);
		render_results(frm, []);

		frm.disable_save();
		frm.page.set_primary_action(__("Import All Files"), () => start_bulk_import(frm));
	},
});

// ─── File picker ─────────────────────────────────────────────────────────────
function render_file_picker(frm) {
	let $wrap = frm.get_field("files_html").$wrapper;
	$wrap.html(`
		<div class="form-group">
			<input type="file" id="cdr_bulk_files" multiple accept=".csv,.xlsx,.xlsm,.txt"
				class="form-control" style="padding:5px;">
			<p class="help-block">${__("Select up to ~100 CSV / Excel (.xlsx) files at once.")}</p>
			<div id="cdr_bulk_selected" class="text-muted" style="font-size:12px;"></div>
		</div>
	`);
	$wrap.find("#cdr_bulk_files").on("change", function () {
		let n = this.files ? this.files.length : 0;
		$wrap.find("#cdr_bulk_selected").text(
			n ? __("{0} file(s) selected", [n]) : ""
		);
	});
}

// ─── Results table ───────────────────────────────────────────────────────────
function render_results(frm, rows, summary) {
	let $wrap = frm.get_field("results_html").$wrapper;
	let body = rows
		.map((r) => {
			let color =
				r.status === "ok" ? "green" : r.status === "running" ? "blue" : "red";
			let icon = r.status === "ok" ? "✓" : r.status === "running" ? "…" : "✗";
			let detail =
				r.status === "ok"
					? __("{0} rows → {1}", [r.rows, r.call_record || ""]) +
					  (r.working_number_created ? " " + __("(new number)") : "")
					: r.message || "";
			return `<tr>
				<td style="font-size:12px;word-break:break-all;">${frappe.utils.escape_html(r.filename)}</td>
				<td class="text-${color}" style="font-size:12px;white-space:nowrap;">${icon} ${__(r.status)}</td>
				<td style="font-size:12px;">${frappe.utils.escape_html(detail)}</td>
			</tr>`;
		})
		.join("");

	$wrap.html(`
		${summary ? `<div style="margin-bottom:8px;font-weight:600;">${summary}</div>` : ""}
		<div style="overflow-x:auto;">
		<table class="table table-bordered table-condensed" style="margin-bottom:0;">
			<thead><tr>
				<th>${__("File")}</th>
				<th>${__("Status")}</th>
				<th>${__("Detail")}</th>
			</tr></thead>
			<tbody>${body || `<tr><td colspan="3" class="text-muted">${__("No files processed yet.")}</td></tr>`}</tbody>
		</table>
		</div>
	`);
}

// ─── Orchestration ───────────────────────────────────────────────────────────
async function start_bulk_import(frm) {
	if (!frm.doc.case_project) {
		frappe.msgprint({ message: __("Select a Case Project first."), indicator: "red" });
		return;
	}
	let input = document.getElementById("cdr_bulk_files");
	if (!input || !input.files.length) {
		frappe.msgprint({ message: __("Select at least one file."), indicator: "red" });
		return;
	}

	let files = Array.from(input.files);
	let results = files.map((f) => ({ filename: f.name, status: "pending" }));
	let ok = 0,
		failed = 0;

	frm.page.clear_primary_action();
	render_results(frm, results, __("Starting… 0 / {0}", [files.length]));

	for (let i = 0; i < files.length; i++) {
		results[i].status = "running";
		render_results(frm, results, __("Processing {0} / {1}…", [i + 1, files.length]));

		try {
			let file_url = await upload_file(files[i]);
			let res = await frappe.xcall(
				"crms.crms.api.cdr_import.bulk_import_file",
				{
					case_project: frm.doc.case_project,
					file_url,
					filename: files[i].name,
					default_operator: frm.doc.default_mobile_operator || null,
					default_case_phase: frm.doc.default_case_phase || null,
				}
			);
			results[i] = res;
			res.status === "ok" ? ok++ : failed++;
		} catch (err) {
			results[i] = {
				filename: files[i].name,
				status: "error",
				message: err.message || String(err),
			};
			failed++;
		}

		render_results(
			frm,
			results,
			__("Processing {0} / {1}… ({2} ok, {3} failed)", [i + 1, files.length, ok, failed])
		);
	}

	render_results(frm, results, __("Done — {0} imported, {1} failed.", [ok, failed]));
	frm.page.set_primary_action(__("Import All Files"), () => start_bulk_import(frm));
	frappe.show_alert({
		message: __("Bulk import finished: {0} ok, {1} failed.", [ok, failed]),
		indicator: failed ? "orange" : "green",
	});
}

// ─── Upload helper ───────────────────────────────────────────────────────────
async function upload_file(file) {
	let form_data = new FormData();
	form_data.append("file", file);
	form_data.append("is_private", 1);
	form_data.append("folder", "Home/Attachments");

	let resp = await fetch("/api/method/upload_file", {
		method: "POST",
		headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
		body: form_data,
	});
	if (!resp.ok) throw new Error(__("File upload failed (HTTP {0})", [resp.status]));
	let data = await resp.json();
	if (data.exc) throw new Error(data.exc);
	return data.message.file_url;
}
