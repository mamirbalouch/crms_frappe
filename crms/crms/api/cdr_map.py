import frappe


@frappe.whitelist()
def export_network_pdf(svg, width=None, height=None, filename="Common Numbers Network"):
	"""
	Render a standalone SVG (the network graph) to a single-page PDF whose page
	size matches the graph's own dimensions — no fixed page limit, colours kept.
	Returns the private File URL to open/download.
	"""
	from frappe.utils.pdf import get_pdf

	try:
		w = float(width)
		h = float(height)
	except (TypeError, ValueError):
		w, h = 1600.0, 1200.0
	# px → mm at 96 dpi, so the page fits the SVG 1:1
	w_mm = round(w / 96.0 * 25.4, 1)
	h_mm = round(h / 96.0 * 25.4, 1)

	html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
	@page {{ size: {w_mm}mm {h_mm}mm; margin: 0; }}
	html, body {{ margin: 0; padding: 0; }}
	</style></head><body>{svg}</body></html>"""

	options = {
		"page-width": f"{w_mm}mm",
		"page-height": f"{h_mm}mm",
		"margin-top": "0", "margin-bottom": "0", "margin-left": "0", "margin-right": "0",
		"disable-smart-shrinking": "",
	}
	pdf = get_pdf(html, options=options)

	safe = "".join(c for c in str(filename) if c.isalnum() or c in " -_") or "network"
	_file = frappe.get_doc({
		"doctype": "File",
		"file_name": f"{safe}.pdf",
		"is_private": 1,
		"content": pdf,
	}).insert(ignore_permissions=True)
	return _file.file_url


@frappe.whitelist()
def export_network_image_pdf(image, width=None, height=None, filename="Common Numbers Network"):
	"""
	Render a graph raster (PNG data URL from Cytoscape) to a single-page PDF whose
	page size matches the image — no fixed page limit, colours preserved.
	"""
	from frappe.utils.pdf import get_pdf

	try:
		w = float(width)
		h = float(height)
	except (TypeError, ValueError):
		w, h = 1600.0, 1200.0
	w_mm = round(w / 96.0 * 25.4, 1)
	h_mm = round(h / 96.0 * 25.4, 1)

	html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
	@page {{ size: {w_mm}mm {h_mm}mm; margin: 0; }}
	html, body {{ margin: 0; padding: 0; }}
	img {{ width: {w_mm}mm; height: {h_mm}mm; display: block; }}
	</style></head><body><img src="{image}"></body></html>"""

	options = {
		"page-width": f"{w_mm}mm", "page-height": f"{h_mm}mm",
		"margin-top": "0", "margin-bottom": "0", "margin-left": "0", "margin-right": "0",
		"disable-smart-shrinking": "", "enable-local-file-access": "",
	}
	pdf = get_pdf(html, options=options)

	safe = "".join(c for c in str(filename) if c.isalnum() or c in " -_") or "network"
	_file = frappe.get_doc({
		"doctype": "File", "file_name": f"{safe}.pdf", "is_private": 1, "content": pdf,
	}).insert(ignore_permissions=True)
	return _file.file_url


@frappe.whitelist()
def get_project_links(case_project, working_number=None, target_case_project=None,
                      target_working_number=None, min_digits=10, max_digits=14, max_common=50):
	"""
	Cross-project link analysis anchored on a Case Project (or one Working Number).

	Finds three kinds of links between the anchor and a target scope
	(a specific project / working number, or — by default — every other project):

	  same_wn         : the same number is a Working Number in both projects
	  contact_is_wn   : a number one side *contacts* is the other side's Working Number
	  common_contact  : both sides contacted the same B-number (shared contact)

	Returns {nodes, edges, counts}. Working-number sets respect the viewer's scope
	(get_list), so a Section user only ever compares numbers they can see.
	"""
	min_len, max_len = int(min_digits or 10), int(max_digits or 14)
	FIELDS = ["name", "working_mobile_number", "owner_name", "case_project"]

	anchor_f = {"case_project": case_project}
	if working_number:
		anchor_f["name"] = working_number
	anchor = frappe.get_list("Working Number", filters=anchor_f, fields=FIELDS, limit_page_length=0)

	if target_working_number:
		tgt_f = {"name": target_working_number}
	elif target_case_project:
		tgt_f = {"case_project": target_case_project}
	else:
		tgt_f = {"case_project": ["!=", case_project]}
	target = frappe.get_list("Working Number", filters=tgt_f, fields=FIELDS, limit_page_length=0)

	if not anchor or not target:
		return {"nodes": [], "edges": [], "counts": {"same_wn": 0, "contact_is_wn": 0, "common_contact": 0}}

	# case-title cache
	titles = {}
	for w in anchor + target:
		if w.case_project not in titles:
			titles[w.case_project] = frappe.db.get_value("Case Project", w.case_project, "case_title") or w.case_project

	anchor_names = [w.name for w in anchor]
	target_names = [w.name for w in target]
	anchor_num_to_wn = {w.working_mobile_number: w.name for w in anchor}
	target_num_to_wn = {w.working_mobile_number: w.name for w in target}
	wn_by_name = {w.name: w for w in anchor + target}
	all_wn_numbers = set(anchor_num_to_wn) | set(target_num_to_wn)

	anchor_contacts = _contacts_for(anchor_names, min_len, max_len)  # {wn: {bnum: calls}}
	target_contacts = _contacts_for(target_names, min_len, max_len)

	edges = {}   # (frozenset(pair), link_type) -> weight ; keeps one edge per pair+type
	used_wns = set()

	def add_edge(a, b, ltype, w=1):
		if a == b:
			return
		key = (frozenset((a, b)), ltype)
		edges[key] = edges.get(key, 0) + w
		used_wns.add(a)
		used_wns.add(b)

	# 1) same_wn
	for num in set(anchor_num_to_wn) & set(target_num_to_wn):
		add_edge(anchor_num_to_wn[num], target_num_to_wn[num], "same_wn")

	# 2) contact_is_wn (either direction)
	for a_wn, contacts in anchor_contacts.items():
		for bnum, calls in contacts.items():
			if bnum in target_num_to_wn:
				add_edge(a_wn, target_num_to_wn[bnum], "contact_is_wn", calls)
	for t_wn, contacts in target_contacts.items():
		for bnum, calls in contacts.items():
			if bnum in anchor_num_to_wn:
				add_edge(t_wn, anchor_num_to_wn[bnum], "contact_is_wn", calls)

	# 3) common_contact (shared B-numbers that are NOT themselves working numbers)
	anchor_bnum_wns, target_bnum_wns = {}, {}
	for a_wn, contacts in anchor_contacts.items():
		for bnum in contacts:
			if bnum not in all_wn_numbers:
				anchor_bnum_wns.setdefault(bnum, set()).add(a_wn)
	for t_wn, contacts in target_contacts.items():
		for bnum in contacts:
			if bnum not in all_wn_numbers:
				target_bnum_wns.setdefault(bnum, set()).add(t_wn)
	shared = set(anchor_bnum_wns) & set(target_bnum_wns)
	# keep the busiest shared contacts
	shared = sorted(shared, key=lambda b: len(anchor_bnum_wns[b]) + len(target_bnum_wns[b]), reverse=True)[:int(max_common)]

	common_nodes = {}
	common_edges = []
	for bnum in shared:
		cn = "cn:" + bnum
		common_nodes[cn] = {"id": cn, "type": "common", "label": bnum}
		for wn in anchor_bnum_wns[bnum] | target_bnum_wns[bnum]:
			common_edges.append({"source": wn, "target": cn, "link_type": "common_contact"})
			used_wns.add(wn)

	# Build nodes
	nodes = {}
	for name in used_wns:
		w = wn_by_name.get(name)
		if not w:
			continue
		nodes[name] = {
			"id": name, "type": "wn", "label": w.working_mobile_number,
			"owner": w.owner_name or "", "case": titles.get(w.case_project, w.case_project),
			"anchor": name in anchor_num_to_wn.values(),
		}
	nodes.update(common_nodes)

	out_edges = [{"source": list(k[0])[0], "target": list(k[0])[1], "link_type": k[1], "weight": v}
	             for k, v in edges.items()]
	out_edges += common_edges

	counts = {
		"same_wn": sum(1 for k in edges if k[1] == "same_wn"),
		"contact_is_wn": sum(1 for k in edges if k[1] == "contact_is_wn"),
		"common_contact": len(common_nodes),
	}
	return {"nodes": list(nodes.values()), "edges": out_edges, "counts": counts}


def _contacts_for(wn_names, min_len, max_len):
	"""Return {working_number: {b_number: call_count}} for the given working numbers."""
	if not wn_names:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT cr.working_number AS wn, dcr.second_party_number AS bnum, COUNT(*) AS calls
		FROM `tabDetail Call Record` dcr
		INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
		WHERE cr.working_number IN %(wns)s
		  AND dcr.second_party_number NOT IN ('', '1')
		  AND LENGTH(dcr.second_party_number) BETWEEN %(mn)s AND %(mx)s
		GROUP BY cr.working_number, dcr.second_party_number
		""",
		{"wns": tuple(wn_names), "mn": min_len, "mx": max_len},
		as_dict=True,
	)
	out = {}
	for r in rows:
		out.setdefault(r.wn, {})[r.bnum] = r.calls
	return out


@frappe.whitelist()
def get_common_number_network(case_project=None, working_number=None, from_date=None, to_date=None,
                              min_digits=10, max_digits=14, only_cross_case=0, max_nodes=60):
	"""
	Build a link graph: working numbers (A-numbers) connected through the common
	B-numbers they share. Returns {nodes, edges} for a force-directed chart.
	Only B-numbers linking >= 2 working numbers are included; only real
	mobile/foreign numbers (by digit length) are considered.
	"""
	max_nodes = int(max_nodes or 60)
	min_len = int(min_digits or 10)
	max_len = int(max_digits or 14)
	conditions = [
		"dcr.second_party_number IS NOT NULL",
		"dcr.second_party_number NOT IN ('', '1')",
		"LENGTH(dcr.second_party_number) BETWEEN %(min_len)s AND %(max_len)s",
	]
	values = {"min_len": min_len, "max_len": max_len}
	if from_date:
		conditions.append("dcr.date_of_communication >= %(from_date)s")
		values["from_date"] = from_date
	if to_date:
		conditions.append("dcr.date_of_communication <= %(to_date)s")
		values["to_date"] = to_date
	if working_number:
		# center on one working number: only its common numbers and their other links
		values["wn"] = working_number

	from crms.permissions import scope_condition
	sc, sv = scope_condition("wn")
	if sc:
		conditions.append(sc)
		values.update(sv)

	where = "WHERE " + " AND ".join(conditions)

	# HAVING clause for the "common" set (>=2 working numbers; optional case scope)
	having = "COUNT(DISTINCT c.wn) >= 2"
	if case_project:
		having += " AND SUM(c.case_project = %(cp)s) > 0"
		values["cp"] = case_project

	rows = frappe.db.sql(
		f"""
		WITH contacts AS (
			SELECT
				wn.name AS wn,
				wn.working_mobile_number AS wnum,
				wn.owner_name AS owner,
				wn.case_project AS case_project,
				dcr.second_party_number AS bnum,
				COUNT(*) AS calls
			FROM `tabDetail Call Record` dcr
			INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
			INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
			{where}
			GROUP BY wn.name, dcr.second_party_number
		),
		common AS (
			SELECT c.bnum
			FROM contacts c
			GROUP BY c.bnum
			HAVING {having}
		)
		SELECT c.wn, c.wnum, c.owner, c.case_project, cp.case_title, c.bnum, c.calls
		FROM contacts c
		INNER JOIN common ON c.bnum = common.bnum
		LEFT JOIN `tabCase Project` cp ON c.case_project = cp.name
		ORDER BY c.bnum
		""",
		values,
		as_dict=True,
	)

	# Optionally narrow to the neighbourhood of a chosen working number
	if working_number:
		bnums_of_wn = {r["bnum"] for r in rows if r["wn"] == working_number}
		rows = [r for r in rows if r["bnum"] in bnums_of_wn]

	from collections import defaultdict

	# A common number is a "cross-case bridge" when the working numbers it links
	# span more than one Case Project — that's the finding worth highlighting.
	bnum_cases = defaultdict(set)
	for r in rows:
		bnum_cases[r["bnum"]].add(r["case_project"])
	cross = {b: len(cs) > 1 for b, cs in bnum_cases.items()}

	if int(only_cross_case or 0):
		rows = [r for r in rows if cross.get(r["bnum"])]

	# Cap graph size: keep the highest-degree common numbers (cross-case first)
	degree = defaultdict(set)
	for r in rows:
		degree[r["bnum"]].add(r["wn"])
	ranked = sorted(degree.items(), key=lambda kv: (cross.get(kv[0], False), len(kv[1])), reverse=True)
	keep_bnums = {b for b, _ in ranked[:max_nodes]}
	rows = [r for r in rows if r["bnum"] in keep_bnums]

	nodes = {}
	edges = []
	for r in rows:
		wn_id = "wn:" + r["wn"]
		cn_id = "cn:" + r["bnum"]
		is_cross = cross.get(r["bnum"], False)
		if wn_id not in nodes:
			nodes[wn_id] = {
				"id": wn_id, "label": r["wnum"], "type": "working",
				"owner": r.get("owner") or "",
				"case": r.get("case_title") or r["case_project"],
			}
		if cn_id not in nodes:
			nodes[cn_id] = {"id": cn_id, "label": r["bnum"], "type": "common", "cross_case": is_cross}
		edges.append({"source": wn_id, "target": cn_id, "weight": r["calls"], "cross_case": is_cross})

	return {"nodes": list(nodes.values()), "edges": edges}


@frappe.whitelist()
def get_movement_points(working_number, from_date=None, to_date=None):
	"""
	Return time-ordered geo points for a Working Number's CDR, for plotting
	movement on a map. Only rows with valid numeric lat/lon are returned.
	"""
	if not working_number:
		frappe.throw(frappe._("Select a Working Number."))

	conditions = [
		"cr.working_number = %(wn)s",
		"dcr.latitude IS NOT NULL AND dcr.latitude != ''",
		"dcr.longitude IS NOT NULL AND dcr.longitude != ''",
		"dcr.date_of_communication IS NOT NULL",
	]
	values = {"wn": working_number}
	if from_date:
		conditions.append("dcr.date_of_communication >= %(fd)s")
		values["fd"] = from_date
	if to_date:
		conditions.append("dcr.date_of_communication <= %(td)s")
		values["td"] = to_date

	from crms.permissions import scope_condition
	sc, sv = scope_condition("cr")
	if sc:
		conditions.append(sc)
		values.update(sv)

	rows = frappe.db.sql(
		f"""
		SELECT
			dcr.date_of_communication AS ts,
			dcr.second_party_number,
			dcr.call_type,
			dcr.duration,
			dcr.rbs,
			dcr.latitude,
			dcr.longitude
		FROM `tabDetail Call Record` dcr
		INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
		WHERE {" AND ".join(conditions)}
		ORDER BY dcr.date_of_communication
		""",
		values,
		as_dict=True,
	)

	points = []
	for r in rows:
		try:
			lat = float(r.latitude)
			lon = float(r.longitude)
		except (TypeError, ValueError):
			continue
		if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
			continue
		points.append({
			"ts": str(r.ts),
			"lat": lat,
			"lon": lon,
			"number": r.second_party_number,
			"call_type": r.call_type,
			"duration": r.duration,
			"rbs": r.rbs,
		})
	return points
