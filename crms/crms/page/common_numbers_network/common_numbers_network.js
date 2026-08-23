// Case-project palette (red reserved for cross-case bridges, grey for common numbers)
const CNN_PALETTE = ["#2563eb", "#0d9488", "#d97706", "#7c3aed", "#0369a1", "#be185d", "#4d7c0f", "#b45309"];

// Frappe's desk locks Array.prototype.move (read-only + non-configurable), which
// makes Cytoscape throw when it loads in the main page. So the whole graph runs
// inside a same-origin iframe (a fresh realm with a clean Array.prototype). Data
// is passed in as JSON and parsed inside the iframe to keep arrays in-realm.
const CNN_IFRAME_HTML = [
"<!doctype html><html><head><meta charset='utf-8'><style>",
"html,body{margin:0;height:100%}",
"#cy{position:absolute;inset:0}",
"#readout{position:absolute;right:14px;top:14px;max-width:230px;background:#fff;border:1px solid #d1d8dd;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.12);padding:12px 14px;font-family:sans-serif;font-size:12px;display:none;z-index:5}",
"#readout .num{font-family:monospace;font-size:15px;font-weight:600}",
"#readout .meta{color:#7c8a9c;margin-top:3px;line-height:1.5}",
"#readout .tag{display:inline-block;margin-top:8px;font-size:10px;text-transform:uppercase;letter-spacing:.05em;padding:2px 7px;border-radius:999px}",
"</style></head><body>",
"<div id='cy'></div><div id='readout'></div>",
"<script src='/assets/crms/js/cytoscape.min.js'></script>",
"<script>",
"var CNN={ready:false,cy:null};",
"var MONO='monospace';",
"CNN.render=function(dataJson,caseColorJson){",
"  var data=JSON.parse(dataJson), caseColor=JSON.parse(caseColorJson);",
"  var els=[];",
"  Object.keys(caseColor).forEach(function(cs){els.push({data:{id:'case:'+cs,type:'case',label:(cs||'').toUpperCase(),color:caseColor[cs]}});});",
"  data.nodes.forEach(function(n){",
"    if(n.type==='working'){els.push({data:{id:n.id,type:'wn',parent:n.case?'case:'+n.case:undefined,color:caseColor[n.case]||'#2563eb',num:n.label,owner:n.owner||'',cs:n.case||'',label:n.label+(n.owner?'\\n'+n.owner:'')}});}",
"    else{els.push({data:{id:n.id,type:n.cross_case?'bridge':'common',num:n.label,label:n.label}});}",
"  });",
"  data.edges.forEach(function(e,i){els.push({data:{id:'e'+i,source:e.source,target:e.target,cross:e.cross_case?1:0}});});",
"  if(CNN.cy)CNN.cy.destroy();",
"  CNN.cy=cytoscape({container:document.getElementById('cy'),elements:els,wheelSensitivity:0.25,style:[",
"    {selector:'node[type=\"case\"]',style:{'shape':'round-rectangle','background-color':'data(color)','background-opacity':0.05,'border-width':1.4,'border-color':'data(color)','border-opacity':0.55,'border-style':'dashed','label':'data(label)','text-valign':'top','text-halign':'center','font-size':12,'font-weight':600,'color':'data(color)','padding':30,'text-margin-y':-6}},",
"    {selector:'node[type=\"wn\"]',style:{'background-color':'data(color)','width':42,'height':42,'border-width':3,'border-color':'#fff','label':'data(label)','font-family':MONO,'font-size':10,'color':'#1d2733','text-wrap':'wrap','text-max-width':96,'text-valign':'bottom','text-margin-y':5,'line-height':1.35}},",
"    {selector:'node[type=\"common\"]',style:{'background-color':'#94a3b8','width':15,'height':15,'border-width':2,'border-color':'#fff','label':'data(label)','font-family':MONO,'font-size':8.5,'color':'#7c8a9c','text-valign':'bottom','text-margin-y':3}},",
"    {selector:'node[type=\"bridge\"]',style:{'background-color':'#dc2626','width':28,'height':28,'border-width':3,'border-color':'#fff','label':'data(label)','font-family':MONO,'font-size':10,'font-weight':600,'color':'#dc2626','text-valign':'bottom','text-margin-y':4}},",
"    {selector:'edge',style:{'width':1.5,'line-color':'#c6cfdb','curve-style':'bezier','opacity':0.85}},",
"    {selector:'edge[cross=1]',style:{'width':2.6,'line-color':'#dc2626','opacity':0.9}},",
"    {selector:'.faded',style:{'opacity':0.1,'text-opacity':0.1}},",
"    {selector:'node.pick',style:{'border-color':'#1d2733','border-width':3}}",
"  ]});",
"  CNN.relayout();",
"  var ro=document.getElementById('readout');",
"  CNN.cy.on('tap','node',function(e){var n=e.target;if(n.data('type')==='case')return;",
"    CNN.cy.elements().addClass('faded');n.closedNeighborhood().removeClass('faded');CNN.cy.nodes().removeClass('pick');n.addClass('pick');",
"    var t=n.data('type');var col=t==='bridge'?'#dc2626':(t==='wn'?(caseColor[n.data('cs')]||n.data('color')):'#94a3b8');",
"    var tag=t==='bridge'?'Cross-case bridge':(t==='wn'?'Working number':'Common number');var deg=n.connectedEdges().length;",
"    ro.innerHTML='<div class=\"num\">'+n.data('num')+'</div><div class=\"meta\">'+(n.data('owner')?n.data('owner')+'<br>':'')+deg+' links</div><span class=\"tag\" style=\"color:'+col+';background:'+col+'1a\">'+tag+'</span>';ro.style.display='block';});",
"  CNN.cy.on('tap',function(e){if(e.target===CNN.cy){CNN.cy.elements().removeClass('faded');CNN.cy.nodes().removeClass('pick');ro.style.display='none';}});",
"};",
"CNN.relayout=function(){if(!CNN.cy)return;CNN.cy.layout({name:'cose',animate:false,padding:36,nodeRepulsion:9000,idealEdgeLength:78,edgeElasticity:120,nestingFactor:1.15,gravity:0.5,componentSpacing:140,randomize:true,fit:true}).run();var c=CNN.cy;[0,150,500,1200].forEach(function(t){setTimeout(function(){if(CNN.cy){c.resize();c.fit(undefined,40);}},t);});};",
"CNN.fit=function(){if(CNN.cy)CNN.cy.fit(undefined,40);};",
"CNN.png=function(){return CNN.cy?CNN.cy.png({full:true,scale:2,bg:'#ffffff'}):null;};",
"CNN.bbox=function(){if(!CNN.cy)return null;var b=CNN.cy.elements().boundingBox();return {w:b.w,h:b.h};};",
"window.CNN=CNN;CNN.ready=(typeof cytoscape==='function');",
"</script></body></html>"
].join("");

frappe.pages["common-numbers-network"].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({ parent: wrapper, title: __("Common Numbers Network"), single_column: true });
	let $body = $(page.body);
	$body.html(`
		<div class="cnn-filter-bar" style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px;">
			<div class="ff ff-case" style="min-width:180px;"></div>
			<div class="ff ff-wn" style="min-width:180px;"></div>
			<div class="ff ff-from" style="min-width:160px;"></div>
			<div class="ff ff-to" style="min-width:160px;"></div>
			<div class="ff ff-min" style="min-width:80px;"></div>
			<div class="ff ff-max" style="min-width:80px;"></div>
			<div class="ff ff-cross" style="min-width:140px;"></div>
			<div><button class="btn btn-primary btn-sm" id="cnn_show">${__("Show Network")}</button></div>
			<div><button class="btn btn-default btn-sm" id="cnn_fit">${__("Fit")}</button></div>
			<div><button class="btn btn-default btn-sm" id="cnn_relayout">${__("Re-run")}</button></div>
			<div><button class="btn btn-default btn-sm" id="cnn_export" disabled>${__("Export PDF")}</button></div>
		</div>
		<div id="cnn_status" class="text-muted" style="margin:6px 0;"></div>
		<div id="cnn_legend" style="margin-bottom:6px;font-size:12px;display:flex;flex-wrap:wrap;gap:14px;align-items:center;"></div>
		<div id="cnn_wrap" style="position:relative;height:72vh;width:100%;border:1px solid var(--border-color,#d1d8dd);border-radius:6px;overflow:hidden;background:#fbfcff;">
			<iframe id="cnn_frame" style="position:absolute;inset:0;width:100%;height:100%;border:0;background:#fbfcff;"></iframe>
		</div>
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

	// Prime the iframe now so the first click is fast
	ensure_frame();

	$body.find("#cnn_show").on("click", () => {
		load_network({
			case_project: f_case.get_value(),
			working_number: f_wn.get_value(),
			from_date: f_from.get_value(),
			to_date: f_to.get_value(),
			min_digits: f_min.get_value(),
			max_digits: f_max.get_value(),
			only_cross_case: f_cross.get_value() ? 1 : 0,
		});
	});
	$body.find("#cnn_fit").on("click", () => { let c = frame_cnn(); if (c) c.fit(); });
	$body.find("#cnn_relayout").on("click", () => { let c = frame_cnn(); if (c) c.relayout(); });
	$body.find("#cnn_export").on("click", () => export_pdf());
};

function frame_cnn() {
	let f = document.getElementById("cnn_frame");
	return f && f.contentWindow && f.contentWindow.CNN && f.contentWindow.CNN.ready ? f.contentWindow.CNN : null;
}

async function ensure_frame() {
	let f = document.getElementById("cnn_frame");
	if (!f) return null;
	if (f.contentWindow && f.contentWindow.CNN && f.contentWindow.CNN.ready) return f;
	await new Promise((res) => {
		f.addEventListener("load", res, { once: true });
		f.srcdoc = CNN_IFRAME_HTML;
	});
	for (let i = 0; i < 160 && !(f.contentWindow.CNN && f.contentWindow.CNN.ready); i++) {
		await new Promise((r) => setTimeout(r, 50));
	}
	return f;
}

function cnn_status(msg, color) {
	let el = document.getElementById("cnn_status");
	if (el) el.innerHTML = color ? `<span class="text-${color}">${msg}</span>` : msg;
}

async function load_network(args) {
	cnn_status(__("Loading…"), "blue");
	document.getElementById("cnn_export").disabled = true;
	await ensure_frame();
	let cnn = frame_cnn();
	if (!cnn) {
		cnn_status(__("Graph engine failed to start. Try a hard refresh (Ctrl+Shift+R)."), "red");
		return;
	}
	let data;
	try {
		data = await frappe.xcall("crms.crms.api.cdr_map.get_common_number_network", args);
	} catch (e) {
		cnn_status(__("Error: ") + (e.message || String(e)), "red");
		return;
	}
	if (!data.nodes.length) {
		document.getElementById("cnn_legend").innerHTML = "";
		cnn_status(__("No shared numbers found for this selection."), "orange");
		return;
	}

	// Colours + legend + stats (computed here; render happens inside the iframe)
	const caseColor = {};
	let ci = 0, wns = 0, commons = 0, bridges = 0;
	data.nodes.forEach((n) => {
		if (n.type === "working") {
			wns++;
			if (n.case && !(n.case in caseColor)) { caseColor[n.case] = CNN_PALETTE[ci % CNN_PALETTE.length]; ci++; }
		} else { commons++; if (n.cross_case) bridges++; }
	});
	render_legend(caseColor);
	cnn_status(__("{0} working numbers · {1} common numbers · {2} cross-case bridge(s) · {3} links",
		[wns, commons, bridges, data.edges.length]), "green");

	try {
		cnn.render(JSON.stringify(data), JSON.stringify(caseColor));
		document.getElementById("cnn_export").disabled = false;
	} catch (e) {
		cnn_status(__("Graph render failed: ") + (e.message || String(e)), "red");
	}
}

function render_legend(caseColor) {
	let el = document.getElementById("cnn_legend");
	if (!el) return;
	let parts = [
		`<span><span style="color:#dc2626;">●</span> ${__("Cross-case bridge")}</span>`,
		`<span><span style="color:#94a3b8;">●</span> ${__("Common number")}</span>`,
	];
	Object.entries(caseColor).forEach(([name, color]) => {
		parts.push(`<span><span style="color:${color};">●</span> ${frappe.utils.escape_html(name)}</span>`);
	});
	parts.push(`<span class="text-muted">${__("click node = isolate · scroll = zoom · drag = move")}</span>`);
	el.innerHTML = parts.join("");
}

async function export_pdf() {
	let cnn = frame_cnn();
	if (!cnn) return;
	cnn_status(__("Building PDF…"), "blue");
	try {
		const png = cnn.png();
		const bb = cnn.bbox() || { w: 1200, h: 800 };
		const w = Math.max(Math.round(bb.w) + 140, 600);
		const h = Math.max(Math.round(bb.h) + 140, 400);
		let url = await frappe.xcall("crms.crms.api.cdr_map.export_network_image_pdf", {
			image: png, width: w, height: h, filename: "Common Numbers Network",
		});
		cnn_status(__("PDF ready."), "green");
		window.open(url, "_blank");
	} catch (e) {
		cnn_status(__("Export failed: ") + (e.message || String(e)), "red");
	}
}
