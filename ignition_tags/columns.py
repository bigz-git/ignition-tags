# Column schema definitions for the ignition_tags package.
#
# Each dict maps a normalized (lowercase) Excel column name to the
# corresponding Ignition JSON key.  Adding a new column to support is a
# one-line change here — the processing loops in core.py iterate over these
# dicts automatically.

# Sheet names used in the Excel template
TAG_IMPORT_SHEET = "tagImport"
UDT_IMPORT_SHEET = "udtImport"

# Accepted column name variants for the folder/path column in tagImport.
# The first match found in the DataFrame is used.
FOLDER_ALIASES = ["folder", "path", "folderpath", "folder name", "folder_name"]

# ── tagImport columns ─────────────────────────────────────────────────────────

# Free-text fields that map 1-to-1 between Excel and JSON.
TAG_SCALAR_FIELDS = {
    "documentation": "documentation",
    "tooltip":       "tooltip",
}

# Engineering-range fields.  Excel column -> Ignition JSON key (camelCase).
TAG_ENG_FIELDS = {
    "englow":  "engLow",
    "enghigh": "engHigh",
}

# Alarm sub-object fields.  All of these are grouped under tag["alarms"][0].
TAG_ALARM_FIELDS = {
    "alarmname":     "name",
    "alarmlabel":    "label",
    "alarmmode":     "mode",
    "alarmsetpoint": "setpointA",   # coerced to float when possible
    "alarmpriority": "priority",
    "alarmnotes":    "notes",
}

# ── udtImport columns ─────────────────────────────────────────────────────────

# Fields present on every UDT tag row.  The processing loop applies light
# type coercion based on the field name (see core.py: _apply_udt_field).
UDT_TAG_FIELDS = {
    "datatype":      "dataType",
    "valuesource":   "valueSource",
    "value":         "value",
    "enghigh":       "engHigh",
    "englow":        "engLow",
    "documentation": "documentation",
}

# Special udtImport columns handled outside the generic UDT_TAG_FIELDS loop:
#
#   ReadOnly      — Boolean (true/false/1/0).  Written as a JSON boolean on the tag.
#
#   DocBinding    — Boolean.  When true, the Documentation value is written as
#                   {"bindType": "parameter", "binding": <value>} instead of a
#                   plain string.  ParamBinding does the same for OpcPath.
#                   TODO: consider generalising binding support to other string
#                   fields (tooltip, etc.) in a future pass.
#
#   Param{N}_Name      — Name of UDT parameter N (N = 1, 2, 3, …).  Read from
#   Param{N}_DataType    the first tag row of each UDT group and used to build
#   Param{N}_Value       the top-level "parameters" block on the UdtType object.
#                        Value column is optional (no default → omit the key).
