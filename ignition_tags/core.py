"""
Pure transformation functions — no file I/O, no UI dependencies.

These functions accept Python data structures (DataFrames, dicts) and return
Python data structures.  The CLI and GUI layers are responsible for reading
files and passing data in; these functions only do the conversion work.
"""

import json
import logging
import numbers
import re

import pandas as pd

from .columns import (
    FOLDER_ALIASES,
    TAG_ALARM_FIELDS,
    TAG_ENG_FIELDS,
    TAG_SCALAR_FIELDS,
    UDT_TAG_FIELDS,
)

logger = logging.getLogger(__name__)


# ── Shared helpers ─────────────────────────────────────────────────────────────

def coerce_value(raw, dtype):
    """Convert a raw cell value to the Python type implied by an Ignition dataType string."""
    if pd.isna(raw):
        if dtype is None:
            return ""
        dt = str(dtype).lower()
        if "int" in dt:
            return 0
        if "float" in dt or "double" in dt:
            return 0.0
        if "bool" in dt or "boolean" in dt:
            return False
        return ""
    dt = str(dtype).lower() if dtype else ""
    try:
        if "int" in dt:
            return int(raw)
        if "float" in dt or "double" in dt:
            return float(raw)
        if "bool" in dt or "boolean" in dt:
            if isinstance(raw, str):
                return raw.strip().lower() in ("true", "1", "yes", "y")
            return bool(raw)
        return str(raw)
    except Exception:
        try:
            if hasattr(raw, "item"):
                return raw.item()
        except Exception:
            pass
        return str(raw)


def ensure_folder_container(container_list, folder_parts):
    """
    Walk (and create if missing) a chain of Folder nodes inside container_list.
    Returns the innermost folder's tags list, ready to append a tag into.
    """
    current = container_list
    for part in folder_parts:
        part = part.strip()
        if not part:
            continue
        found = next(
            (obj for obj in current
             if obj.get("tagType") == "Folder" and obj.get("name") == part),
            None,
        )
        if not found:
            found = {"tagType": "Folder", "name": part, "tags": []}
            current.append(found)
        current = found["tags"]
    return current


# ── Internal helpers ───────────────────────────────────────────────────────────

def _norm_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to lowercase-stripped and fill NaN with empty string."""
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df.fillna("")


def _parse_folder(raw_folder: str, name: str) -> tuple[list[str], str]:
    """
    Return (folder_parts, tag_name).

    Folder path is taken from raw_folder when present; otherwise it is inferred
    from a slash-delimited name (the last segment becomes the tag name).
    """
    raw_folder = raw_folder.strip()
    if raw_folder:
        for sep in ("/", "\\"):
            if sep in raw_folder:
                return [p for p in raw_folder.split(sep) if p.strip()], name
        return [raw_folder], name
    if "/" in name or "\\" in name:
        parts = [p.strip() for p in name.replace("\\", "/").split("/") if p.strip()]
        if len(parts) > 1:
            return parts[:-1], parts[-1]
    return [], name


def _resolve_datatype(tag: dict, value_val) -> str:
    """Determine a tag's dataType string, inferring from its value when the field is absent."""
    raw_dt = tag.get("dataType") or tag.get("datatype")
    if isinstance(raw_dt, dict):
        raw_dt = raw_dt.get("type") or raw_dt.get("name") or json.dumps(raw_dt, ensure_ascii=False)
    if raw_dt and str(raw_dt).strip():
        return str(raw_dt)
    # Infer from stored value
    if isinstance(value_val, numbers.Integral):
        return "Int4"
    if isinstance(value_val, numbers.Real):
        try:
            return "Int4" if float(value_val).is_integer() else "Float4"
        except Exception:
            return "Float4"
    logger.debug("dataType missing for tag '%s', defaulting to Int4", tag.get("name"))
    return "Int4"


def _try_numeric(val):
    """Try to coerce val to int, then float; return original on failure."""
    try:
        if isinstance(val, str) and val.strip().isdigit():
            return int(val)
        return float(val)
    except (ValueError, TypeError):
        return val


def _extract_udt_parameters(first_row, df_cols: set) -> dict:
    """
    Build the UdtType 'parameters' dict from param{N}_name/datatype/value columns.

    Columns are discovered by scanning df_cols for names matching param{N}_name
    (N = 1, 2, …).  Values are read from first_row (the first tag row of the
    UDT group).  The Value column is optional — omitted when blank.
    """
    param_nums = sorted(
        int(m.group(1))
        for col in df_cols
        if (m := re.match(r"^param(\d+)_name$", col))
    )
    params = {}
    for n in param_nums:
        param_name = str(first_row.get(f"param{n}_name", "")).strip()
        if not param_name:
            continue
        param: dict = {}
        dt = str(first_row.get(f"param{n}_datatype", "")).strip()
        if dt:
            param["dataType"] = dt
        v = first_row.get(f"param{n}_value", "")
        if v != "" and not (isinstance(v, float) and pd.isna(v)):
            param["value"] = str(v).strip()
        params[param_name] = param
    return params


def _apply_udt_field(tag: dict, excel_col: str, json_key: str, val) -> None:
    """Write one UDT tag field into tag dict with appropriate type coercion."""
    if excel_col == "valuesource":
        tag[json_key] = str(val).strip().lower() or "memory"
    elif excel_col == "value":
        tag[json_key] = _try_numeric(val)
    elif excel_col in ("enghigh", "englow"):
        try:
            tag[json_key] = float(val)
        except (ValueError, TypeError):
            pass
    else:
        v = str(val).strip()
        if v:
            tag[json_key] = v


# ── Public API ─────────────────────────────────────────────────────────────────

def flatten_tags(tags: list, parent_path: str = "") -> list[dict]:
    """
    Recursively flatten an Ignition tag tree into a list of row dicts.

    Output column names match the tagImport Excel format so the result can be
    written directly to a tagImport sheet and imported back without edits.
    """
    rows = []
    for tag in tags:
        if tag.get("tagType") == "Folder":
            new_path = f"{parent_path}/{tag['name']}" if parent_path else tag["name"]
            rows.extend(flatten_tags(tag.get("tags", []), parent_path=new_path))
            continue

        value_val = tag.get("value")
        alarm = {}
        if isinstance(tag.get("alarms"), list) and tag["alarms"]:
            alarm = tag["alarms"][0]

        rows.append({
            "name":          tag.get("name", ""),
            "folder":        parent_path,
            "datatype":      _resolve_datatype(tag, value_val),
            "value":         value_val,
            "opcpath":       tag.get("opcItemPath", ""),
            "documentation": tag.get("documentation", ""),
            "tooltip":       tag.get("tooltip", ""),
            "englow":        tag.get("engLow", ""),
            "enghigh":       tag.get("engHigh", ""),
            "alarmname":     alarm.get("name", ""),
            "alarmlabel":    alarm.get("label", ""),
            "alarmmode":     alarm.get("mode", ""),
            "alarmsetpoint": alarm.get("setpointA", ""),
            "alarmpriority": alarm.get("priority", ""),
            "alarmnotes":    alarm.get("notes", ""),
        })
    return rows


def build_tag_provider(df: pd.DataFrame, provider_name: str, opc_server: str) -> dict:
    """
    Convert a tagImport DataFrame into an Ignition Provider JSON dict.

    Parameters
    ----------
    df:            DataFrame from the tagImport sheet (column names may be mixed case).
    provider_name: Value for the top-level "name" field in the JSON.
    opc_server:    OPC server name written into opcServer for OPC-connected tags.
    """
    df = _norm_df(df)
    df_cols = set(df.columns)

    folder_col = next((c for c in FOLDER_ALIASES if c in df_cols), None)

    top_level_tags = []
    count = 0

    for _, row in df.iterrows():
        raw_name = str(row.get("name", "")).strip()
        if not raw_name:
            continue

        raw_folder = str(row.get(folder_col, "")) if folder_col else ""
        folder_parts, name = _parse_folder(raw_folder, raw_name)

        datatype = str(row.get("datatype", "")).strip() or "Float4"
        opcpath = str(row.get("opcpath", "")).strip()

        tag: dict = {"name": name, "tagType": "AtomicTag", "dataType": datatype}

        # Optional scalar fields: documentation, tooltip
        for excel_col, json_key in TAG_SCALAR_FIELDS.items():
            if excel_col in df_cols:
                val = str(row.get(excel_col, "")).strip()
                if val:
                    tag[json_key] = val

        # Engineering limits: engLow, engHigh
        for excel_col, json_key in TAG_ENG_FIELDS.items():
            if excel_col in df_cols:
                val = str(row.get(excel_col, "")).strip()
                if val:
                    tag[json_key] = val

        # Alarm sub-object — only created when alarmname is populated
        if "alarmname" in df_cols and str(row.get("alarmname", "")).strip():
            alarm: dict = {}
            for excel_col, json_key in TAG_ALARM_FIELDS.items():
                if excel_col in df_cols:
                    val = str(row.get(excel_col, "")).strip()
                    if val:
                        if json_key == "setpointA":
                            try:
                                val = float(val)
                            except ValueError:
                                pass
                        alarm[json_key] = val
            if alarm:
                tag["alarms"] = [alarm]

        # OPC-connected vs memory tag
        if opcpath:
            tag["opcItemPath"] = opcpath
            tag["opcServer"] = opc_server
            tag["valueSource"] = "opc"
        else:
            tag["valueSource"] = "memory"
            tag["value"] = coerce_value(row.get("value", ""), datatype)

        ensure_folder_container(top_level_tags, folder_parts).append(tag)
        count += 1

    logger.info("Built provider '%s' with %d tags", provider_name, count)
    return {"tagType": "Provider", "name": provider_name, "tags": top_level_tags}


def build_udt_types(
    df: pd.DataFrame,
    top_types_name: str = "_types_",
    root_format: str = "folder_root",
    opc_server: str = "Ignition OPC UA Server",
) -> dict:
    """
    Convert a udtImport DataFrame into an Ignition UDT JSON dict.

    Parameters
    ----------
    df:             DataFrame from the udtImport sheet.
    top_types_name: Name of the top-level folder (default: "_types_").
    root_format:    Output shape — one of:
                      "folder_root"  -> {name, tagType: Folder, tags: [...]}
                      "wrapped_tags" -> {tags: [{name, tagType: Folder, tags: [...]}]}
                      "tags_only"    -> {tags: [...]}
    opc_server:     OPC server name written into opcServer for OPC-connected tags.
    """
    df = _norm_df(df)
    df_cols = set(df.columns)

    if "udtname" not in df_cols or "tagname" not in df_cols:
        raise ValueError("Sheet must contain 'UDTName' and 'TagName' columns")

    udt_list = []
    for udt_name, group in df.groupby("udtname"):
        udt_name = str(udt_name).strip()
        if not udt_name:
            continue

        udt: dict = {"name": udt_name, "tagType": "UdtType", "tags": []}

        # Build parameters block from param{N}_* columns on the first tag row
        first_row = group.iloc[0]
        params = _extract_udt_parameters(first_row, df_cols)
        if params:
            udt["parameters"] = params

        for _, row in group.iterrows():
            tag_name = str(row.get("tagname", "")).strip()
            if not tag_name:
                continue

            tag: dict = {"name": tag_name, "tagType": "AtomicTag"}

            # General fields driven by UDT_TAG_FIELDS schema
            for excel_col, json_key in UDT_TAG_FIELDS.items():
                if excel_col not in df_cols:
                    continue
                val = row.get(excel_col, "")
                if val == "" or (isinstance(val, float) and pd.isna(val)):
                    continue
                _apply_udt_field(tag, excel_col, json_key, val)

            tag.setdefault("valueSource", "memory")

            # ReadOnly boolean
            if "readonly" in df_cols:
                ro = row.get("readonly", "")
                if ro is True or str(ro).strip().lower() in ("true", "1", "yes"):
                    tag["readOnly"] = True

            # Documentation with optional parameter binding
            if "docbinding" in df_cols and "documentation" in tag:
                doc_bind = row.get("docbinding", "")
                if doc_bind is True or str(doc_bind).strip().lower() in ("true", "1", "yes"):
                    tag["documentation"] = {
                        "bindType": "parameter",
                        "binding": tag["documentation"],
                    }

            # EngUnit with optional parameter binding
            if "engunitbinding" in df_cols and "engUnit" in tag:
                eu_bind = row.get("engunitbinding", "")
                if eu_bind is True or str(eu_bind).strip().lower() in ("true", "1", "yes"):
                    tag["engUnit"] = {
                        "bindType": "parameter",
                        "binding": tag["engUnit"],
                    }

            # OPC path with optional parameter binding
            opc = str(row.get("opcpath", "")).strip() if "opcpath" in df_cols else ""
            if opc:
                param_binding = row.get("opcpathbinding", "") if "opcpathbinding" in df_cols else ""
                use_binding = (
                    param_binding is True
                    or str(param_binding).strip().lower() in ("true", "1", "yes")
                )
                tag["opcItemPath"] = (
                    {"bindType": "parameter", "binding": opc} if use_binding else opc
                )
                tag["valueSource"] = "opc"
                tag["opcServer"] = opc_server

            udt["tags"].append(tag)

        udt_list.append(udt)

    if root_format == "folder_root":
        return {"name": top_types_name, "tagType": "Folder", "tags": udt_list}
    if root_format == "wrapped_tags":
        return {"tags": [{"name": top_types_name, "tagType": "Folder", "tags": udt_list}]}
    if root_format == "tags_only":
        return {"tags": udt_list}
    raise ValueError("root_format must be 'folder_root', 'wrapped_tags', or 'tags_only'")
