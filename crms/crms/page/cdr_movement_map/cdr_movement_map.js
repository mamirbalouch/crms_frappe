frappe.pages["cdr-movement-map"].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("CDR Movement Map"),
		single_column: true,
	});

	let $body = $(page.body);
	$body.html(`
		<div class="cdr-filter-bar" style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px;">
			<div class="ff ff-case" style="min-width:200px;"></div>
			<div class="ff ff-wn" style="min-width:200px;"></div>
			<div class="ff ff-from" style="min-width:180px;"></div>
			<div class="ff ff-to" style="min-width:180px;"></div>
			<div><button class="btn btn-primary btn-sm" id="cdr_show">${__("Show Movement")}</button></div>
		</div>
		<div id="cdr_map_status" class="text-muted" style="margin:6px 0;"></div>
		<div id="cdr_map" style="height:70vh;width:100%;border:1px solid var(--border-color,#d1d8dd);border-radius:6px;"></div>
	`);

	function mk(sel, df) {
		let c = frappe.ui.form.make_control({ df: df, parent: $body.find(sel)[0], render_input: true });
		c.refresh();
		return c;
	}
	let f_case = mk(".ff-case", { fieldtype: "Link", options: "Case Project", label: __("Case Project"), fieldname: "case_project" });
	let f_wn = mk(".ff-wn", {
		fieldtype: "Link", options: "Working Number", label: __("Working Number"), fieldname: "working_number",
		get_query: () => ({ filters: f_case.get_value() ? { case_project: f_case.get_value() } : {} }),
	});
	let f_from = mk(".ff-from", { fieldtype: "Datetime", label: __("From Date"), fieldname: "from_date" });
	let f_to = mk(".ff-to", { fieldtype: "Datetime", label: __("To Date"), fieldname: "to_date" });

	let state = { map: null, layer: null };

	$body.find("#cdr_show").on("click", () => {
		let wn = f_wn.get_value();
		if (!wn) {
			frappe.msgprint({ message: __("Select a Working Number."), indicator: "red" });
			return;
		}
		load_and_render(page, state, {
			working_number: wn,
			from_date: f_from.get_value(),
			to_date: f_to.get_value(),
		});
	});

	// Preload Leaflet so the first click is instant
	ensure_leaflet();
};

function ensure_leaflet() {
	return new Promise((resolve) => {
		if (window.L) return resolve();
		frappe.require(
			["/assets/frappe/js/lib/leaflet/leaflet.css", "/assets/frappe/js/lib/leaflet/leaflet.js"],
			resolve
		);
	});
}

function set_status(msg, color) {
	let el = document.getElementById("cdr_map_status");
	if (el) el.innerHTML = color ? `<span class="text-${color}">${msg}</span>` : msg;
}

async function load_and_render(page, state, args) {
	await ensure_leaflet();
	set_status(__("Loading points…"), "blue");

	let points;
	try {
		points = await frappe.xcall("crms.crms.api.cdr_map.get_movement_points", args);
	} catch (e) {
		set_status(__("Error: ") + (e.message || String(e)), "red");
		return;
	}

	if (!state.map) {
		state.map = L.map("cdr_map").setView([30.3753, 69.3451], 6); // Pakistan
		L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
			maxZoom: 19,
			attribution: "© OpenStreetMap contributors",
		}).addTo(state.map);
	}
	if (state.layer) {
		state.map.removeLayer(state.layer);
		state.layer = null;
	}

	if (!points.length) {
		set_status(__("No geo-tagged records found for this selection."), "orange");
		return;
	}

	let group = L.featureGroup();
	let path = [];
	points.forEach((p, i) => {
		path.push([p.lat, p.lon]);
		let is_out = (p.call_type || "").toLowerCase().indexOf("out") !== -1;
		let marker = L.circleMarker([p.lat, p.lon], {
			radius: 5,
			color: i === 0 ? "#2e7d32" : i === points.length - 1 ? "#c62828" : "#1565c0",
			fillColor: is_out ? "#1565c0" : "#8e24aa",
			fillOpacity: 0.8,
			weight: 2,
		});
		marker.bindPopup(
			`<b>#${i + 1}</b> ${frappe.utils.escape_html(p.ts || "")}<br>` +
			`${frappe.utils.escape_html(p.call_type || "")} — ${frappe.utils.escape_html(p.number || "")}<br>` +
			`<small>${frappe.utils.escape_html(p.rbs || "")}</small>`
		);
		group.addLayer(marker);
	});
	// Movement path in time order
	group.addLayer(L.polyline(path, { color: "#1565c0", weight: 2, opacity: 0.5 }));

	group.addTo(state.map);
	state.layer = group;
	state.map.fitBounds(group.getBounds().pad(0.2));
	setTimeout(() => state.map.invalidateSize(), 200);

	set_status(
		__("{0} geo-tagged points plotted (green = first, red = last).", [points.length]),
		"green"
	);
}
