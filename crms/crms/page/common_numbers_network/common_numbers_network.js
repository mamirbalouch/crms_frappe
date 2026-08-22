// Case-project palette (red is reserved for cross-case bridges, grey for common numbers)
const CNN_PALETTE = ["#1565c0", "#2e7d32", "#6a1b9a", "#00838f", "#ef6c00", "#4527a0", "#ad1457", "#558b2f", "#0277bd", "#8d6e63"];
let CNN_STATE = null; // { svg, nodes } for export

frappe.pages["common-numbers-network"].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Common Numbers Network"),
		single_column: true,
	});

	let $body = $(page.body);
	$body.html(`
		<div class="cnn-filter-bar" style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px;">
			<div class="ff ff-case" style="min-width:170px;"></div>
			<div class="ff ff-wn" style="min-width:170px;"></div>
			<div class="ff ff-from" style="min-width:155px;"></div>
			<div class="ff ff-to" style="min-width:155px;"></div>
			<div class="ff ff-min" style="min-width:75px;"></div>
			<div class="ff ff-max" style="min-width:75px;"></div>
			<div class="ff ff-cross" style="min-width:140px;"></div>
			<div><button class="btn btn-primary btn-sm" id="cnn_show">${__("Show Network")}</button></div>
			<div><button class="btn btn-default btn-sm" id="cnn_export" disabled>${__("Export PDF")}</button></div>
		</div>
		<div id="cnn_status" class="text-muted" style="margin:6px 0;"></div>
		<div id="cnn_legend" style="margin-bottom:6px;font-size:12px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;"></div>
		<div id="cnn_wrap" style="height:72vh;width:100%;border:1px solid var(--border-color,#d1d8dd);border-radius:6px;overflow:hidden;background:var(--card-bg,#fff);"></div>
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
	let f_min = mk(".ff-min", { fieldtype: "Int", label: __("Min Digits"), fieldname: "min_digits" });
	let f_max = mk(".ff-max", { fieldtype: "Int", label: __("Max Digits"), fieldname: "max_digits" });
	let f_cross = mk(".ff-cross", { fieldtype: "Check", label: __("Only cross-case"), fieldname: "only_cross_case" });
	f_min.set_value(10);
	f_max.set_value(14);

	$body.find("#cnn_show").on("click", () => {
		load_network(page, {
			case_project: f_case.get_value(),
			working_number: f_wn.get_value(),
			from_date: f_from.get_value(),
			to_date: f_to.get_value(),
			min_digits: f_min.get_value(),
			max_digits: f_max.get_value(),
			only_cross_case: f_cross.get_value() ? 1 : 0,
		});
	});
	$body.find("#cnn_export").on("click", () => export_pdf());
};

function cnn_status(msg, color) {
	let el = document.getElementById("cnn_status");
	if (el) el.innerHTML = color ? `<span class="text-${color}">${msg}</span>` : msg;
}

async function load_network(page, args) {
	cnn_status(__("Loading…"), "blue");
	document.getElementById("cnn_export").disabled = true;
	let data;
	try {
		data = await frappe.xcall("crms.crms.api.cdr_map.get_common_number_network", args);
	} catch (e) {
		cnn_status(__("Error: ") + (e.message || String(e)), "red");
		return;
	}
	if (!data.nodes.length) {
		document.getElementById("cnn_wrap").innerHTML = "";
		document.getElementById("cnn_legend").innerHTML = "";
		cnn_status(__("No shared numbers found for this selection."), "orange");
		return;
	}
	let bridges = data.nodes.filter((n) => n.type === "common" && n.cross_case).length;
	cnn_status(
		__("{0} numbers, {1} links, {2} cross-case bridge(s) in red.", [data.nodes.length, data.edges.length, bridges]),
		"green"
	);
	render_force_graph(document.getElementById("cnn_wrap"), data);
	document.getElementById("cnn_export").disabled = false;
}

function render_force_graph(container, data) {
	const W = container.clientWidth || 900;
	const H = container.clientHeight || 600;
	const SVGNS = "http://www.w3.org/2000/svg";
	container.innerHTML = "";

	// Assign a colour per case project
	const caseColor = {};
	let ci = 0;
	data.nodes.forEach((n) => {
		if (n.type === "working" && n.case && !(n.case in caseColor)) {
			caseColor[n.case] = CNN_PALETTE[ci % CNN_PALETTE.length];
			ci++;
		}
	});
	render_legend(caseColor);

	const idx = {};
	const nodes = data.nodes.map((n, i) => {
		idx[n.id] = i;
		return { ...n, x: W / 2 + (Math.random() - 0.5) * W * 0.7, y: H / 2 + (Math.random() - 0.5) * H * 0.7, vx: 0, vy: 0 };
	});
	const edges = data.edges.map((e) => ({ s: idx[e.source], t: idx[e.target], w: e.weight, cross: e.cross_case }));

	const k = Math.sqrt((W * H) / Math.max(nodes.length, 1)) * 0.9;
	for (let iter = 0; iter < 420; iter++) {
		const alpha = 1 - iter / 420;
		for (let i = 0; i < nodes.length; i++) {
			for (let j = i + 1; j < nodes.length; j++) {
				let dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y;
				let d2 = dx * dx + dy * dy + 0.01;
				let f = (k * k) / d2, d = Math.sqrt(d2);
				let fx = (dx / d) * f, fy = (dy / d) * f;
				nodes[i].vx += fx; nodes[i].vy += fy; nodes[j].vx -= fx; nodes[j].vy -= fy;
			}
		}
		for (const e of edges) {
			let a = nodes[e.s], b = nodes[e.t];
			let dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) + 0.01;
			let f = (d - k) * 0.1, fx = (dx / d) * f, fy = (dy / d) * f;
			a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
		}
		// Clustering: pull each working node toward its case-project centroid → sections
		let cen = {};
		nodes.forEach((n) => {
			if (n.type === "working" && n.case) {
				(cen[n.case] = cen[n.case] || { x: 0, y: 0, n: 0 });
				cen[n.case].x += n.x; cen[n.case].y += n.y; cen[n.case].n++;
			}
		});
		Object.values(cen).forEach((c) => { c.x /= c.n; c.y /= c.n; });
		for (const n of nodes) {
			if (n.type === "working" && n.case && cen[n.case]) {
				n.vx += (cen[n.case].x - n.x) * 0.05; n.vy += (cen[n.case].y - n.y) * 0.05;
			}
			n.vx += (W / 2 - n.x) * 0.004; n.vy += (H / 2 - n.y) * 0.004;
			n.x += n.vx * alpha * 0.5; n.y += n.vy * alpha * 0.5;
			n.vx *= 0.85; n.vy *= 0.85;
		}
	}

	const svg = document.createElementNS(SVGNS, "svg");
	svg.setAttribute("width", "100%"); svg.setAttribute("height", "100%");
	svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
	svg.style.cursor = "grab";
	const viewport = document.createElementNS(SVGNS, "g");
	svg.appendChild(viewport);

	// Case-project "sections" behind everything
	draw_sections(viewport, nodes, caseColor, SVGNS);

	// Edges (cross-case on top, in red)
	const order = [...edges.keys()].sort((a, b) => (edges[a].cross ? 1 : 0) - (edges[b].cross ? 1 : 0));
	const lineByEdge = {};
	for (const ei of order) {
		const e = edges[ei];
		let line = document.createElementNS(SVGNS, "line");
		line.setAttribute("x1", nodes[e.s].x); line.setAttribute("y1", nodes[e.s].y);
		line.setAttribute("x2", nodes[e.t].x); line.setAttribute("y2", nodes[e.t].y);
		line.setAttribute("stroke", e.cross ? "#c62828" : "#c0c8d0");
		line.setAttribute("stroke-width", e.cross ? Math.min(2 + Math.log(e.w + 1), 5) : Math.min(1 + Math.log(e.w + 1), 4));
		line.setAttribute("stroke-opacity", e.cross ? 0.85 : 0.5);
		viewport.appendChild(line);
		lineByEdge[ei] = line;
	}

	nodes.forEach((n) => {
		let g = document.createElementNS(SVGNS, "g");
		let isW = n.type === "working";
		let isBridge = !isW && n.cross_case;
		let r = isW ? 10 : isBridge ? 7 : 4;
		let fill = isW ? (caseColor[n.case] || "#1565c0") : isBridge ? "#c62828" : "#9e9e9e";
		let c = document.createElementNS(SVGNS, "circle");
		c.setAttribute("cx", n.x); c.setAttribute("cy", n.y); c.setAttribute("r", r);
		c.setAttribute("fill", fill); c.setAttribute("stroke", "#fff"); c.setAttribute("stroke-width", 1.5);
		let title = document.createElementNS(SVGNS, "title");
		title.textContent = isW
			? `${n.label}${n.owner ? " — " + n.owner : ""}${n.case ? " (" + n.case + ")" : ""}`
			: n.label + (isBridge ? " — cross-case" : "");
		c.appendChild(title);
		g.appendChild(c);

		let label = null, sub = null;
		if (isW || isBridge) {
			label = document.createElementNS(SVGNS, "text");
			label.setAttribute("x", n.x); label.setAttribute("y", n.y - (isW ? 14 : 11));
			label.setAttribute("text-anchor", "middle");
			label.setAttribute("font-size", isW ? "11" : "10");
			label.setAttribute("font-weight", "600");
			label.setAttribute("fill", isBridge ? "#c62828" : "#333333");
			label.textContent = n.label;
			g.appendChild(label);
		}
		if (isW && n.owner) {
			sub = document.createElementNS(SVGNS, "text");
			sub.setAttribute("x", n.x); sub.setAttribute("y", n.y + 21);
			sub.setAttribute("text-anchor", "middle"); sub.setAttribute("font-size", "9");
			sub.setAttribute("fill", "#888888");
			sub.textContent = n.owner.length > 22 ? n.owner.slice(0, 22) + "…" : n.owner;
			g.appendChild(sub);
		}
		enable_node_drag(g, c, label, sub, n, nodes, edges, lineByEdge, viewport);
		viewport.appendChild(g);
	});

	container.appendChild(svg);
	setup_zoom_pan(svg, viewport);
	CNN_STATE = { svg: svg, viewport: viewport };
}

function render_legend(caseColor) {
	let el = document.getElementById("cnn_legend");
	if (!el) return;
	let parts = [
		`<span><span style="color:#c62828;">●</span> ${__("Cross-case bridge")}</span>`,
		`<span><span style="color:#9e9e9e;">●</span> ${__("Common number")}</span>`,
	];
	Object.entries(caseColor).forEach(([caseName, color]) => {
		parts.push(`<span><span style="color:${color};">●</span> ${frappe.utils.escape_html(caseName)}</span>`);
	});
	parts.push(`<span class="text-muted">${__("scroll = zoom · drag background = pan · drag node = move")}</span>`);
	el.innerHTML = parts.join("");
}

function draw_sections(viewport, nodes, caseColor, SVGNS) {
	const byCase = {};
	nodes.forEach((n) => { if (n.type === "working" && n.case) (byCase[n.case] = byCase[n.case] || []).push(n); });
	Object.entries(byCase).forEach(([caseName, pts]) => {
		const color = caseColor[caseName] || "#1565c0";
		const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
		const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
		let shape;
		if (pts.length >= 3) {
			let hull = pad_hull(convex_hull(pts), { x: cx, y: cy }, 42);
			shape = document.createElementNS(SVGNS, "polygon");
			shape.setAttribute("points", hull.map((p) => `${p.x},${p.y}`).join(" "));
		} else {
			let maxd = Math.max(...pts.map((p) => Math.hypot(p.x - cx, p.y - cy)), 0);
			shape = document.createElementNS(SVGNS, "circle");
			shape.setAttribute("cx", cx); shape.setAttribute("cy", cy); shape.setAttribute("r", maxd + 55);
		}
		shape.setAttribute("fill", color); shape.setAttribute("fill-opacity", "0.07");
		shape.setAttribute("stroke", color); shape.setAttribute("stroke-opacity", "0.45");
		shape.setAttribute("stroke-width", "1.5"); shape.setAttribute("stroke-dasharray", "6 4");
		viewport.appendChild(shape);

		const minY = Math.min(...pts.map((p) => p.y));
		let t = document.createElementNS(SVGNS, "text");
		t.setAttribute("x", cx); t.setAttribute("y", minY - (pts.length >= 3 ? 48 : 62));
		t.setAttribute("text-anchor", "middle"); t.setAttribute("font-size", "13"); t.setAttribute("font-weight", "700");
		t.setAttribute("fill", color);
		t.textContent = caseName;
		viewport.appendChild(t);
	});
}

function convex_hull(points) {
	if (points.length < 3) return points.slice();
	let pts = points.map((p) => ({ x: p.x, y: p.y })).sort((a, b) => a.x - b.x || a.y - b.y);
	const cross = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
	let lower = [];
	for (const p of pts) { while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop(); lower.push(p); }
	let upper = [];
	for (let i = pts.length - 1; i >= 0; i--) { const p = pts[i]; while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop(); upper.push(p); }
	lower.pop(); upper.pop();
	return lower.concat(upper);
}

function pad_hull(hull, c, pad) {
	return hull.map((p) => { let dx = p.x - c.x, dy = p.y - c.y, d = Math.hypot(dx, dy) || 1; return { x: p.x + (dx / d) * pad, y: p.y + (dy / d) * pad }; });
}

function enable_node_drag(g, circle, label, sub, node, nodes, edges, lineByEdge, viewport) {
	let dragging = false;
	function toLocal(evt) {
		let pt = viewport.ownerSVGElement.createSVGPoint();
		pt.x = evt.clientX; pt.y = evt.clientY;
		return pt.matrixTransform(viewport.getScreenCTM().inverse());
	}
	g.addEventListener("mousedown", (e) => { dragging = true; e.stopPropagation(); e.preventDefault(); });
	window.addEventListener("mousemove", (e) => {
		if (!dragging) return;
		let p = toLocal(e); node.x = p.x; node.y = p.y;
		circle.setAttribute("cx", node.x); circle.setAttribute("cy", node.y);
		if (label) { label.setAttribute("x", node.x); label.setAttribute("y", node.y - (node.type === "working" ? 14 : 11)); }
		if (sub) { sub.setAttribute("x", node.x); sub.setAttribute("y", node.y + 21); }
		let ni = nodes.indexOf(node);
		edges.forEach((ed, ei) => {
			let line = lineByEdge[ei];
			if (!line) return;
			if (ed.s === ni) { line.setAttribute("x1", node.x); line.setAttribute("y1", node.y); }
			if (ed.t === ni) { line.setAttribute("x2", node.x); line.setAttribute("y2", node.y); }
		});
	});
	window.addEventListener("mouseup", () => { dragging = false; });
}

function setup_zoom_pan(svg, viewport) {
	let view = { x: 0, y: 0, scale: 1 };
	function apply() { viewport.setAttribute("transform", `translate(${view.x},${view.y}) scale(${view.scale})`); }
	svg.addEventListener("wheel", (e) => {
		e.preventDefault();
		let factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
		let mx = e.offsetX, my = e.offsetY;
		view.x = mx - (mx - view.x) * factor; view.y = my - (my - view.y) * factor; view.scale *= factor;
		apply();
	}, { passive: false });
	let panning = false, sx = 0, sy = 0;
	svg.addEventListener("mousedown", (e) => { panning = true; sx = e.clientX; sy = e.clientY; svg.style.cursor = "grabbing"; });
	window.addEventListener("mousemove", (e) => {
		if (!panning) return;
		view.x += e.clientX - sx; view.y += e.clientY - sy; sx = e.clientX; sy = e.clientY; apply();
	});
	window.addEventListener("mouseup", () => { panning = false; svg.style.cursor = "grab"; });
}

async function export_pdf() {
	if (!CNN_STATE) return;
	const SVGNS = "http://www.w3.org/2000/svg";
	cnn_status(__("Building PDF…"), "blue");
	try {
		// Content bounding box (ignores current zoom/pan — captures the whole graph)
		const bbox = CNN_STATE.viewport.getBBox();
		const pad = 50;
		const x = bbox.x - pad, y = bbox.y - pad, w = bbox.width + pad * 2, h = bbox.height + pad * 2;

		const clone = CNN_STATE.svg.cloneNode(true);
		clone.setAttribute("width", w); clone.setAttribute("height", h);
		clone.setAttribute("viewBox", `${x} ${y} ${w} ${h}`);
		clone.setAttribute("xmlns", SVGNS);
		let vp = clone.querySelector("g");
		if (vp) vp.removeAttribute("transform");
		// white background so the PDF isn't transparent
		let bg = document.createElementNS(SVGNS, "rect");
		bg.setAttribute("x", x); bg.setAttribute("y", y); bg.setAttribute("width", w); bg.setAttribute("height", h);
		bg.setAttribute("fill", "#ffffff");
		clone.insertBefore(bg, clone.firstChild);

		const svgStr = new XMLSerializer().serializeToString(clone);
		let url = await frappe.xcall("crms.crms.api.cdr_map.export_network_pdf", {
			svg: svgStr, width: w, height: h, filename: "Common Numbers Network",
		});
		cnn_status(__("PDF ready."), "green");
		window.open(url, "_blank");
	} catch (e) {
		cnn_status(__("Export failed: ") + (e.message || String(e)), "red");
	}
}
