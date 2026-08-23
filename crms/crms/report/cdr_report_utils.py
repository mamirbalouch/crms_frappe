"""Shared query helpers for CRMS CDR analytical reports."""

from collections import Counter

# Ignore time buckets accounting for less than this share of a location's hits,
# so a rare early/late outlier doesn't stretch the "usual" presence window.
OUTLIER_THRESHOLD = 0.05


def trimmed_window(secs, hours, threshold=OUTLIER_THRESHOLD):
	"""Return (first_seconds, last_seconds) after dropping outlier hour-buckets."""
	if not secs:
		return None, None
	counts = Counter(hours)
	total = len(hours)
	kept = {h for h, c in counts.items() if c / total >= threshold}
	if not kept:
		kept = set(counts)
	kept_secs = [s for s, h in zip(secs, hours) if h in kept]
	return min(kept_secs), max(kept_secs)


def fmt_hhmm(seconds):
	"""Format seconds-of-day as HH:MM (empty string for None)."""
	if seconds is None:
		return ""
	return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}"

# Standard join from Detail Call Record up to Working Number
BASE_JOIN = """
	FROM `tabDetail Call Record` dcr
	INNER JOIN `tabCall Record` cr ON dcr.parent = cr.name
	INNER JOIN `tabWorking Number` wn ON cr.working_number = wn.name
"""


def build_conditions(filters, require_datetime=False):
	"""Return (where_clause, values) from the standard CDR report filters."""
	filters = filters or {}
	conditions = []
	values = {}

	if filters.get("case_project"):
		conditions.append("wn.case_project = %(case_project)s")
		values["case_project"] = filters["case_project"]
	if filters.get("working_number"):
		conditions.append("cr.working_number = %(working_number)s")
		values["working_number"] = filters["working_number"]
	if filters.get("from_date"):
		conditions.append("dcr.date_of_communication >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("dcr.date_of_communication <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if require_datetime:
		conditions.append("dcr.date_of_communication IS NOT NULL")

	# Row-level visibility by the viewer's Department/Unit/Section scope
	from crms.permissions import scope_condition
	sc, sv = scope_condition("wn")
	if sc:
		conditions.append(sc)
		values.update(sv)

	where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
	return where, values
