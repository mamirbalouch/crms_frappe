"""
Seed initial master data extracted from the original C# CRMS application.
Column mappings are taken verbatim from CallRecordEntryForm.cs AutoSave_* methods.
"""
import frappe


# ── Mobile Operators ─────────────────────────────────────────────────────────

OPERATORS = [
    "Jazz / Mobilink",
    "Ufone",
    "Telenor",
    "Zong",
    "Warid",
]

# ── Call Types ───────────────────────────────────────────────────────────────

CALL_TYPES = [
    "Outgoing Call",
    "Incoming Call",
    "Outgoing SMS",
    "Incoming SMS",
    "Data / Other",
]

# ── CDR Import Profiles ──────────────────────────────────────────────────────
# Each entry = one profile (one operator format variant).
# `column_mappings` only lists columns that ARE mapped; the rest are silently skipped.
# RBS columns that embed coordinates use target_field "rbs_with_coords".

PROFILES = [

    # ── Zong ─────────────────────────────────────────────────────────────────
    {
        "profile_name": "Zong CDR v1 (MSISDN_ID)",
        "mobile_operator": "Zong",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: CALL_TYPE~MSISDN_ID~STRT_TM~BNUMBER~MINS~SECS~...",
        "column_mappings": [
            ("CALL_TYPE",     "call_type"),
            ("BNUMBER",       "second_party_number"),
            ("STRT_TM",       "date_of_communication"),
            ("MINS",          "duration_minutes"), # combined with SECS by the parser
            ("SECS",          "duration"),
            ("SITE_ADDRESS",  "rbs"),              # human-readable site; CELL_ID is only a cell identifier
            ("IMEI",          "imei"),
            ("LNG",           "longitude"),
            ("LAT",           "latitude"),
        ],
    },
    {
        "profile_name": "Zong CDR v2 (MSISDN)",
        "mobile_operator": "Zong",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: CALL_TYPE~MSISDN~STRT_TM~BNUMBER~MINS~SECS~...",
        "column_mappings": [
            ("CALL_TYPE",     "call_type"),
            ("BNUMBER",       "second_party_number"),
            ("STRT_TM",       "date_of_communication"),
            ("MINS",          "duration_minutes"), # combined with SECS by the parser
            ("SECS",          "duration"),
            ("SITE_ADDRESS",  "rbs"),              # human-readable site; CELL_ID is only a cell identifier
            ("IMEI",          "imei"),
            ("LNG",           "longitude"),
            ("LAT",           "latitude"),
        ],
    },

    # ── Telenor ───────────────────────────────────────────────────────────────
    {
        "profile_name": "Telenor CDR v1",
        "mobile_operator": "Telenor",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: MSISDN~CALL_ORIG_NUM~CALL_DIALED_NUM~IMSI~IMEI~CALL_START_DT_TM~...",
        "column_mappings": [
            ("CALL_DIALED_NUM",     "second_party_number"),
            ("IMEI",                "imei"),
            ("CALL_START_DT_TM",    "date_of_communication"),
            ("Call_Network_Volume", "duration"),
            ("Location",            "rbs"),              # site address; Cell_Site_Id is only a cell identifier
            ("LAT",                 "latitude"),
            ("LONGITUDE",           "longitude"),
            ("CALL_TYPE",           "call_type"),
        ],
    },
    {
        "profile_name": "Telenor CDR v2",
        "mobile_operator": "Telenor",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: MSISDN~call_org_num~CALL_DIALED_NUM~...~Cell_SITE_ID~lat~longitude~CALL_TYPE~location~",
        "column_mappings": [
            ("CALL_DIALED_NUM",     "second_party_number"),
            ("IMEI",                "imei"),
            ("CALL_START_DT_TM",    "date_of_communication"),
            ("Call_Network_Volume", "duration"),
            ("location",            "rbs"),              # site address; Cell_SITE_ID is only a cell identifier
            ("lat",                 "latitude"),
            ("longitude",           "longitude"),
            ("CALL_TYPE",           "call_type"),
        ],
    },

    # ── Jazz / Mobilink ───────────────────────────────────────────────────────
    {
        "profile_name": "Jazz CDR v1 (A Party / B-Party)",
        "mobile_operator": "Jazz / Mobilink",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: Sr #~Call Type~F3~A Party~F5~B-Party~F7~Date & Time~...~Duration~...~Cell ID~...~IMEI~...~Site~...",
        "column_mappings": [
            ("Call Type",   "call_type"),
            ("B-Party",     "second_party_number"),
            ("Date & Time", "date_of_communication"),
            ("Duration",    "duration"),
            ("Cell ID",     "rbs"),
            ("IMEI",        "imei"),
            ("Site",        "rbs_with_coords"),
        ],
    },
    {
        "profile_name": "Jazz CDR v1 (A-Party / B-Party dash)",
        "mobile_operator": "Jazz / Mobilink",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Same as v1 but A-Party uses dash. Headers: Sr #~Call Type~F3~A-Party~F5~B-Party~...",
        "column_mappings": [
            ("Call Type",   "call_type"),
            ("B-Party",     "second_party_number"),
            ("Date & Time", "date_of_communication"),
            ("Duration",    "duration"),
            ("Cell ID",     "rbs"),
            ("IMEI",        "imei"),
            ("Site",        "rbs_with_coords"),
        ],
    },
    {
        "profile_name": "Jazz CDR v2 (short, no F20-F22)",
        "mobile_operator": "Jazz / Mobilink",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: Sr #~Call Type~F3~A Party~F5~B-Party~F7~Date & Time~...~Duration~...~Cell ID~...~IMEI~...~Site~",
        "column_mappings": [
            ("Call Type",   "call_type"),
            ("B-Party",     "second_party_number"),
            ("Date & Time", "date_of_communication"),
            ("Duration",    "duration"),
            ("Cell ID",     "rbs"),
            ("IMEI",        "imei"),
            ("Site",        "rbs_with_coords"),
        ],
    },
    {
        "profile_name": "Jazz CDR v3 (F2/F4/F6... layout)",
        "mobile_operator": "Jazz / Mobilink",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: Sr #~F2~Call Type~F4~A-Party~F6~B-Party~F8~Date & Time~F10~Duration~Cell ID~...",
        "column_mappings": [
            ("Call Type",   "call_type"),
            ("B-Party",     "second_party_number"),
            ("Date & Time", "date_of_communication"),
            ("Duration",    "duration"),
            ("Cell ID",     "rbs"),
            ("IMEI",        "imei"),
            ("Site",        "rbs_with_coords"),
        ],
    },
    {
        "profile_name": "Jazz CDR v4 (AnotherNew layout)",
        "mobile_operator": "Jazz / Mobilink",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: Sr #~Call Type~A-Party~B-Party~Date & Time~F6~Duration~Cell ID~IMEI~IMSI~Site~F12~F13~",
        "column_mappings": [
            ("Call Type",   "call_type"),
            ("B-Party",     "second_party_number"),
            ("Date & Time", "date_of_communication"),
            ("Duration",    "duration"),
            ("Cell ID",     "rbs"),
            ("IMEI",        "imei"),
            ("Site",        "rbs_with_coords"),
        ],
    },
    {
        "profile_name": "Jazz CDR BrandNew (camelCase)",
        "mobile_operator": "Jazz / Mobilink",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: CallType~Aparty~BParty~Datetime~Duration~cellid~Imei~Imsi~SiteLocation~",
        "column_mappings": [
            ("CallType",     "call_type"),
            ("BParty",       "second_party_number"),
            ("Datetime",     "date_of_communication"),
            ("Duration",     "duration"),
            ("cellid",       "rbs"),
            ("Imei",         "imei"),
            ("SiteLocation", "rbs_with_coords"),
        ],
    },

    # ── Warid (now merged into Jazz) ─────────────────────────────────────────
    {
        "profile_name": "Warid CDR v1",
        "mobile_operator": "Warid",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: SUBNO~B_SUBNO~A_TRANSDATE~TRANSTIME~DURATION~CELL_ID~DESCRIPTION~IMEI_NUMBER~OPER~",
        "column_mappings": [
            ("B_SUBNO",      "second_party_number"),
            ("A_TRANSDATE",  "date_of_communication"),
            ("DURATION",     "duration"),
            ("CELL_ID",      "rbs"),
            ("DESCRIPTION",  "rbs_with_coords"),
            ("IMEI_NUMBER",  "imei"),
            ("OPER",         "call_type"),
        ],
    },

    # ── Ufone ─────────────────────────────────────────────────────────────────
    {
        "profile_name": "Ufone CDR v1 (no Duration column)",
        "mobile_operator": "Ufone",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: IMEI~IMSI~A Number~B Number~Start Time~End Time~Service Provider~Type~Direction~Location~Cell Id~Cell Sector~Latitude~Longitude~",
        "column_mappings": [
            ("B Number",   "second_party_number"),
            ("Start Time", "date_of_communication"),
            ("Type",       "call_type"),
            ("IMEI",       "imei"),
            ("Location",   "rbs"),
            ("Latitude",   "latitude"),
            ("Longitude",  "longitude"),
        ],
    },
    {
        "profile_name": "Ufone CDR v2 (with Duration column)",
        "mobile_operator": "Ufone",
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: IMEI~IMSI~A Number~B Number~Start Time~End Time~Service Provider~Type~Direction~Location~Cell Id~Cell Sector~Latitude~Longitude~Duration~",
        "column_mappings": [
            ("B Number",   "second_party_number"),
            ("Start Time", "date_of_communication"),
            ("Duration",   "duration"),
            ("Type",       "call_type"),
            ("IMEI",       "imei"),
            ("Location",   "rbs"),
            ("Latitude",   "latitude"),
            ("Longitude",  "longitude"),
        ],
    },

    # ── Generic formats (operator-neutral) ───────────────────────────────────
    {
        "profile_name": "Generic CDR v1 (Number/CallType/DateTime)",
        "mobile_operator": None,
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: Number~CallType~DateTime~Duration~IMEI~Location~",
        "column_mappings": [
            ("Number",   "second_party_number"),
            ("CallType", "call_type"),
            ("DateTime", "date_of_communication"),
            ("Duration", "duration"),
            ("IMEI",     "imei"),
            ("Location", "rbs_with_coords"),
        ],
    },
    {
        "profile_name": "Generic CDR v2 (A-Party/B-Party/Site)",
        "mobile_operator": None,
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: A-Party~B-Party~Call Type~Date & Time~Duration~IMEI #~Site~",
        "column_mappings": [
            ("B-Party",     "second_party_number"),
            ("Call Type",   "call_type"),
            ("Date & Time", "date_of_communication"),
            ("Duration",    "duration"),
            ("IMEI #",      "imei"),
            ("Site",        "rbs_with_coords"),
        ],
    },
    {
        "profile_name": "Generic CDR v3 (A-Number/B-Number/Location)",
        "mobile_operator": None,
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: A-Number~B-Number~Call Type~Date & Time~Duration~IMEI #~Location~",
        "column_mappings": [
            ("B-Number",    "second_party_number"),
            ("Call Type",   "call_type"),
            ("Date & Time", "date_of_communication"),
            ("Duration",    "duration"),
            ("IMEI #",      "imei"),
            ("Location",    "rbs_with_coords"),
        ],
    },
    {
        "profile_name": "Generic CDR v4 (MINS/SECS/B-Party/Site)",
        "mobile_operator": None,
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: A-Party~B-Party~Call Type~Date & Time~MINS~SECS~IMEI #~Site~",
        "column_mappings": [
            ("B-Party",     "second_party_number"),
            ("Call Type",   "call_type"),
            ("Date & Time", "date_of_communication"),
            ("MINS",        "duration_minutes"),
            ("SECS",        "duration"),
            ("IMEI #",      "imei"),
            ("Site",        "rbs_with_coords"),
        ],
    },
    {
        "profile_name": "Generic CDR v5 (MINS/SECS/B-Number/Location)",
        "mobile_operator": None,
        "header_row": 1,
        "rbs_coord_separator": "|",
        "notes": "Headers: A-Number~B-Number~Call Type~Date & Time~MINS~SECS~IMEI #~Location~",
        "column_mappings": [
            ("B-Number",    "second_party_number"),
            ("Call Type",   "call_type"),
            ("Date & Time", "date_of_communication"),
            ("MINS",        "duration_minutes"),
            ("SECS",        "duration"),
            ("IMEI #",      "imei"),
            ("Location",    "rbs_with_coords"),
        ],
    },
]


# ── Public entry point ────────────────────────────────────────────────────────

def seed_initial_data():
    """Idempotent: skips records that already exist."""
    _seed_operators()
    _seed_call_types()
    _seed_profiles()
    frappe.db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_operators():
    for name in OPERATORS:
        if not frappe.db.exists("Mobile Operator", name):
            frappe.get_doc({"doctype": "Mobile Operator", "operator_name": name}).insert(ignore_permissions=True)


def _seed_call_types():
    for name in CALL_TYPES:
        if not frappe.db.exists("Call Type", name):
            frappe.get_doc({"doctype": "Call Type", "type_description": name}).insert(ignore_permissions=True)


def _seed_profiles():
    """
    Ensure every baseline profile exists and matches this file (the source of
    truth for these named profiles). Existing seed profiles are re-synced so
    mapping fixes ship on migrate; user-created profiles have other names and
    are left untouched.
    """
    for p in PROFILES:
        if frappe.db.exists("CDR Import Profile", p["profile_name"]):
            doc = frappe.get_doc("CDR Import Profile", p["profile_name"])
            doc.column_mappings = []
        else:
            doc = frappe.new_doc("CDR Import Profile")
            doc.profile_name = p["profile_name"]
        doc.mobile_operator = p.get("mobile_operator")
        doc.header_row = p.get("header_row", 1)
        doc.rbs_coord_separator = p.get("rbs_coord_separator", "|")
        doc.notes = p.get("notes", "")
        for src, tgt in p.get("column_mappings", []):
            doc.append("column_mappings", {"source_column": src, "target_field": tgt})
        doc.save(ignore_permissions=True)
