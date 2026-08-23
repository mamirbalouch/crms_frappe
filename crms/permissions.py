"""
Row-level visibility for CRMS records by organisational hierarchy.

Hierarchy: Department -> Unit -> Section. Every Case Project (and the Working
Numbers / Call Records under it) carries crms_section / crms_unit / crms_department.

A user's visibility is set by their role + their assignment fields on the User:
  - CRMS Admin / System Manager / Administrator -> everything
  - CRMS Department User -> records where crms_department = user's crms_department
  - CRMS Unit User       -> records where crms_unit = user's crms_unit
  - CRMS Section User     -> records where crms_section = user's crms_section
  - none of the above     -> nothing (must be assigned a scope)
"""
import frappe

# Access Level (on the User) -> the matching field on the CDR records
_LEVEL_TO_FIELD = {
	"Department": "crms_department",
	"Unit": "crms_unit",
	"Section": "crms_section",
}


def get_user_scope(user=None):
	"""
	Determine a user's data scope from their User fields:
	  crms_access_level (Department/Unit/Section, or blank) + crms_access_value.

	Returns {'level': 'all'|'crms_department'|'crms_unit'|'crms_section'|'none', 'value': <name>|None}.
	  - Administrator / System Manager -> 'all'
	  - blank Access Level (non-admin)  -> 'none' (sees nothing)
	"""
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return {"level": "all", "value": None}

	level, value = frappe.db.get_value("User", user, ["crms_access_level", "crms_access_value"]) or (None, None)
	field = _LEVEL_TO_FIELD.get(level)
	if not field or not value:
		return {"level": "none", "value": None}
	return {"level": field, "value": value}


# ── Permission query conditions (list views, get_list, link pickers, reports UI) ──

def _query(doctype, user):
	scope = get_user_scope(user)
	level = scope["level"]
	if level == "all":
		return ""
	if level == "none" or not scope["value"]:
		return "1=0"  # assigned no scope -> see nothing
	return "`tab{dt}`.`{f}` = {v}".format(dt=doctype, f=level, v=frappe.db.escape(scope["value"]))


def case_project_query(user):
	return _query("Case Project", user)


def working_number_query(user):
	return _query("Working Number", user)


def call_record_query(user):
	return _query("Call Record", user)


# ── Document-level checks (opening a single doc directly) ──

def _has(doc, user):
	scope = get_user_scope(user)
	level = scope["level"]
	if level == "all":
		return True
	if level == "none" or not scope["value"]:
		return False
	return doc.get(level) == scope["value"]


def case_project_has_permission(doc, user=None, permission_type=None):
	return _has(doc, user)


def working_number_has_permission(doc, user=None, permission_type=None):
	return _has(doc, user)


def call_record_has_permission(doc, user=None, permission_type=None):
	return _has(doc, user)


# ── Helper for our raw-SQL Script Reports / API endpoints ──

def scope_condition(alias="wn", user=None):
	"""
	Return (sql_fragment, values) restricting to the user's scope, filtering on
	<alias>.crms_section / crms_unit / crms_department. `alias` must be a table
	that carries those columns (Working Number / Call Record / Case Project).
	Returns ("", {}) for full-access users.
	"""
	scope = get_user_scope(user)
	level = scope["level"]
	if level == "all":
		return "", {}
	if level == "none" or not scope["value"]:
		return "1=0", {}
	return "{a}.{f} = %(crms_scope)s".format(a=alias, f=level), {"crms_scope": scope["value"]}
