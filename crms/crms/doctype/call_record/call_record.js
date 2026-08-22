// ─── Target field display labels ─────────────────────────────────────────────
const CDR_FIELDS = {
	second_party_number: "Second Party Number",
	date_of_communication: "Date of Communication",
	duration: "Duration (seconds)",
	duration_minutes: "Duration (minutes — added to seconds)",
	imei: "IMEI",
	rbs: "RBS / Site Name",
	rbs_with_coords: "RBS + Coordinates (auto-extract lat/lon)",
	latitude: "Latitude",
	longitude: "Longitude",
	call_type: "Call Type",
	case_phase: "Case Phase",
};

frappe.ui.form.on("Call Record", {
	refresh(frm) {
		frm.add_custom_button(__("Import CDR (CSV / Excel)"), () => show_import_step1(frm));
	},

	working_number(frm) {
		if (frm.doc.working_number) {
			frappe.db.get_value("Working Number", frm.doc.working_number, "case_phase", (r) => {
				if (r && r.case_phase) frm.set_value("case_phase", r.case_phase);
			});
		}
	},
});

// ─── Step 1: file selection + auto-detect ────────────────────────────────────
function show_import_step1(frm) {
	let d = new frappe.ui.Dialog({
		title: __("Import CDR — Step 1: Select File"),
		fields: [
			{
				fieldname: "file_html",
				fieldtype: "HTML",
				options: `
				<div class="form-group">
					<label class="control-label">${__("CDR File")} <span class="req-star">*</span></label>
					<input type="file" id="cdr_file_input" accept=".csv,.xlsx,.xls,.txt"
						class="form-control" style="padding:5px;">
					<p class="help-block">${__("CSV or Excel (.xlsx / .xls) — any format")}</p>
				</div>`,
			},
			{ fieldname: "cb", fieldtype: "Column Break" },
			{
				fieldname: "header_row",
				fieldtype: "Int",
				label: __("Header Row Number"),
				default: 1,
				description: __("Row that contains column names (usually 1)"),
			},
			{ fieldname: "sec", fieldtype: "Section Break" },
			{
				fieldname: "status_html",
				fieldtype: "HTML",
				options: `<div id="cdr_step1_status" style="min-height:20px;"></div>`,
			},
		],
		primary_action_label: __("Detect & Continue →"),
		primary_action: async (vals) => {
			let input = document.getElementById("cdr_file_input");
			if (!input || !input.files.length) {
				frappe.msgprint({ message: __("Please select a file."), indicator: "red" });
				return;
			}
			let file = input.files[0];
			set_status("blue", __("Uploading file…"));
			d.disable_primary_action();

			try {
				let file_url = await upload_file(file);
				set_status("blue", __("Reading headers…"));

				let result = await frappe.xcall(
					"crms.crms.api.cdr_import.get_file_headers",
					{ file_url, header_row: vals.header_row || 1 }
				);

				set_status("blue", __("Detecting profile…"));
				let detected = await frappe.xcall(
					"crms.crms.api.cdr_import.detect_profile",
					{ headers_json: JSON.stringify(result.headers) }
				);

				d.hide();
				show_import_step2(frm, {
					file_url,
					headers: result.headers,
					preview: result.preview,
					total_rows: result.total_rows,
					header_row: vals.header_row || 1,
					detected_profile: detected.profile,
					detected_operator: detected.operator,
					detected_score: detected.score,
					detected_mapping: detected.mapping || {},
				});
			} catch (err) {
				set_status("red", __("Error: ") + (err.message || String(err)));
				d.enable_primary_action();
			}
		},
	});

	function set_status(color, msg) {
		let el = document.getElementById("cdr_step1_status");
		if (el) el.innerHTML = `<p class="text-${color}">${msg}</p>`;
	}

	d.show();
}

// ─── Step 2: mapping confirmation + import ───────────────────────────────────
function show_import_step2(frm, ctx) {
	let {
		file_url, headers, preview, total_rows,
		header_row, detected_profile, detected_operator, detected_score,
	} = ctx;

	// current mapping: source_column → target_field
	let mapping = {};

	// Pre-fill from the detected profile's mapping (resolved server-side in
	// detect_profile — the browser must not query the CDR Profile Column child
	// table directly, it has no read permission on it).
	Object.assign(mapping, ctx.detected_mapping || {});

	// Also apply common auto-aliases for unmapped headers
	headers.forEach((h) => {
		if (!mapping[h]) mapping[h] = guess_field(h);
	});

	render_step2(frm, ctx, mapping);
}

function render_step2(frm, ctx, mapping) {
	let { file_url, headers, preview, total_rows, header_row, detected_profile, detected_operator } = ctx;
	let is_detected = !!detected_profile;

	let badge = is_detected
		? `<span class="badge badge-success" style="font-size:13px;padding:5px 10px;">
				✓ ${__(detected_profile)} ${detected_operator ? "(" + detected_operator + ")" : ""}
			</span>`
		: `<span class="badge badge-warning" style="font-size:13px;padding:5px 10px;">
				⚠ ${__("No profile matched — please map columns below")}
			</span>`;

	let mapping_rows = headers
		.map((h) => {
			let sel = Object.entries(CDR_FIELDS)
				.map(([val, lbl]) =>
					`<option value="${val}" ${mapping[h] === val ? "selected" : ""}>${lbl}</option>`
				)
				.join("");
			return `<tr>
				<td style="padding:4px 8px;vertical-align:middle;max-width:220px;word-break:break-all;">${h}</td>
				<td style="padding:4px 8px;">
					<select class="form-control input-xs cdr-map-sel" data-col="${frappe.utils.escape_html(h)}" style="min-width:190px;">
						<option value="">— ${__("Skip")} —</option>
						${sel}
					</select>
				</td>
			</tr>`;
		})
		.join("");

	let preview_header = headers.map((h) => `<th style="font-size:11px;">${h}</th>`).join("");
	let preview_rows = (preview || [])
		.map(
			(row) =>
				`<tr>${row.map((c) => `<td style="font-size:11px;">${frappe.utils.escape_html(String(c ?? ""))}</td>`).join("")}</tr>`
		)
		.join("");

	let d = new frappe.ui.Dialog({
		title: __("Import CDR — Step 2: Confirm Mapping"),
		size: "large",
		fields: [
			{
				fieldname: "content",
				fieldtype: "HTML",
				options: `
				<div style="margin-bottom:12px;">${badge}
					<span class="text-muted" style="margin-left:10px;">${total_rows} ${__("data rows found")}</span>
				</div>

				<div class="row">
				  <div class="col-sm-5">
					<h6 style="border-bottom:1px solid #ddd;padding-bottom:6px;">${__("Column Mapping")}</h6>
					<table class="table table-condensed" style="margin-bottom:0;">
						<thead><tr>
							<th>${__("File Column")}</th>
							<th>${__("Maps To")}</th>
						</tr></thead>
						<tbody>${mapping_rows}</tbody>
					</table>
				  </div>
				  <div class="col-sm-7">
					<h6 style="border-bottom:1px solid #ddd;padding-bottom:6px;">${__("File Preview (first 5 rows)")}</h6>
					<div style="overflow-x:auto;">
					<table class="table table-bordered table-condensed" style="font-size:11px;">
						<thead><tr>${preview_header}</tr></thead>
						<tbody>${preview_rows}</tbody>
					</table>
					</div>
				  </div>
				</div>

				<hr>
				<div class="row">
				  <div class="col-sm-6">
					<div class="checkbox">
						<label>
							<input type="checkbox" id="cdr_save_profile_chk">
							${__("Save mapping as a new profile")}
						</label>
					</div>
				  </div>
				  <div class="col-sm-6" id="cdr_profile_name_wrap" style="display:none;">
					<input type="text" id="cdr_new_profile_name" class="form-control input-sm"
						placeholder="${__("Profile name, e.g. Jazz CDR 2024")}">
				  </div>
				</div>
				<div id="cdr_import_status" style="min-height:20px;margin-top:8px;"></div>
				`,
			},
		],
		primary_action_label: __("Import"),
		secondary_action_label: __("← Back"),
		secondary_action() {
			d.hide();
			show_import_step1(frm);
		},
		primary_action: async () => {
			// Collect current mapping from selects
			let current_mapping = {};
			document.querySelectorAll(".cdr-map-sel").forEach((sel) => {
				if (sel.value) current_mapping[sel.dataset.col] = sel.value;
			});

			let required_mapped = Object.values(current_mapping).includes("second_party_number")
				|| Object.values(current_mapping).includes("date_of_communication");

			if (!required_mapped) {
				frappe.msgprint({
					message: __("Map at least Second Party Number or Date of Communication."),
					indicator: "red",
				});
				return;
			}

			// Save the form first if it's new
			if (frm.is_new()) {
				set_import_status("blue", __("Saving Call Record…"));
				try {
					await frm.save_or_update();
				} catch (e) {
					set_import_status("red", __("Failed to save. Fill required fields first."));
					return;
				}
			}

			// Optionally save profile
			let save_profile = document.getElementById("cdr_save_profile_chk")?.checked;
			let new_profile_name = document.getElementById("cdr_new_profile_name")?.value?.trim();
			if (save_profile && new_profile_name) {
				try {
					await frappe.xcall("crms.crms.api.cdr_import.save_profile", {
						profile_name: new_profile_name,
						mobile_operator: frm.doc.working_number
							? (await frappe.db.get_value("Working Number", frm.doc.working_number, "mobile_operator")).message?.mobile_operator
							: null,
						header_row,
						mapping_json: JSON.stringify(current_mapping),
					});
					frappe.show_alert({ message: __('Profile "{0}" saved.', [new_profile_name]), indicator: "green" });
				} catch (e) {
					frappe.show_alert({ message: __("Could not save profile: ") + e.message, indicator: "orange" });
				}
			}

			// Import
			d.disable_primary_action();
			set_import_status("blue", __("Importing {0} rows…", [total_rows]));

			try {
				let result = await frappe.xcall("crms.crms.api.cdr_import.import_cdr", {
					call_record: frm.doc.name,
					file_url,
					profile_name: detected_profile || null,
					mapping_json: detected_profile ? null : JSON.stringify(current_mapping),
					header_row,
				});

				d.hide();
				await frm.reload_doc();
				frappe.show_alert({
					message: __("{0} CDR rows imported successfully.", [result.rows_imported]),
					indicator: "green",
				});
			} catch (err) {
				set_import_status("red", __("Import failed: ") + (err.message || String(err)));
				d.enable_primary_action();
			}
		},
	});

	// Toggle profile name input
	d.$wrapper.on("change", "#cdr_save_profile_chk", function () {
		document.getElementById("cdr_profile_name_wrap").style.display = this.checked ? "" : "none";
	});

	// Update mapping object live (so back→forward preserves changes)
	d.$wrapper.on("change", ".cdr-map-sel", function () {
		mapping[this.dataset.col] = this.value;
	});

	function set_import_status(color, msg) {
		let el = document.getElementById("cdr_import_status");
		if (el) el.innerHTML = `<p class="text-${color}">${msg}</p>`;
	}

	d.show();
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

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

// Common column name aliases for auto-guessing
const _ALIASES = {
	second_party_number: [
		"b_number","bnumber","b number","called","called_number","other_party",
		"party_b","destination","dialed","msisdn_b","msisdn b","second party",
	],
	date_of_communication: [
		"date","datetime","call_date","call_datetime","call date","call time",
		"call_time","timestamp","start_time","start time","date_time",
	],
	duration: [
		"dur","call_duration","call duration","duration_sec","duration_secs",
		"billsec","talk_time","talk time","seconds","secs",
	],
	imei: ["device_id","device id","handset"],
	rbs: ["cell","cell_id","cell id","cell_tower","cell tower","bts","site_id","site id","lac"],
	rbs_with_coords: [
		"location","site_name","site name","sitename","site_location","site location",
		"sitelocation","rbs","rbs_name","tower","base_station","base station",
		"cell_name","cell name","lac_cell","tower_info","tower info",
	],
	latitude: ["lat","y_coord","y coord"],
	longitude: ["lon","long","lng","x_coord","x coord"],
	call_type: ["type","call_type","service_type","service type","record_type","record type"],
};

function guess_field(header) {
	let h = header.toLowerCase().trim().replace(/[\s\-]/g, "_");
	for (let [field, aliases] of Object.entries(_ALIASES)) {
		if (aliases.includes(h) || h === field) return field;
	}
	return "";
}
