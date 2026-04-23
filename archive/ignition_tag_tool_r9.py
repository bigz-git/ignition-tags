import json
import numbers
import pandas as pd
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

# --- Utility functions --- #


def coerce_value(raw, dtype):
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
    current = container_list
    for part in folder_parts:
        part = part.strip()
        if not part:
            continue
        found = next((obj for obj in current if obj.get("tagType")
                     == "Folder" and obj.get("name") == part), None)
        if not found:
            found = {"tagType": "Folder", "name": part, "tags": []}
            current.append(found)
        current = found["tags"]
    return current


def flatten_tags(tags, parent_path=""):
    flat_list = []
    for tag in tags:
        tag_type = tag.get("tagType")
        if tag_type == "Folder":
            new_path = f"{parent_path}/{tag['name']}" if parent_path else tag['name']
            flat_list.extend(flatten_tags(
                tag.get("tags", []), parent_path=new_path))
            continue

            # --- Robust dataType handling + defaulting to Int4 if missing ---
        raw_dt = tag.get("dataType")
        if raw_dt is None or (isinstance(raw_dt, str) and raw_dt.strip() == ""):
            raw_dt = tag.get("datatype")   # fallback lowercase key

        # If it's a dict, try to extract a meaningful string
        if isinstance(raw_dt, dict):
            raw_dt = raw_dt.get("type") or raw_dt.get(
                "name") or json.dumps(raw_dt, ensure_ascii=False)

        value_val = tag.get("value", None)

        # If still missing or blank, infer from value where possible, otherwise default to Int4
        if raw_dt is None or (isinstance(raw_dt, str) and str(raw_dt).strip() == ""):
            # Prefer integer if the value looks integer-ish
            if isinstance(value_val, numbers.Integral):
                data_type_str = "Int4"
            elif isinstance(value_val, numbers.Real):
                # float-like: if whole-number float, treat as Int4; else Float4
                try:
                    if float(value_val).is_integer():
                        data_type_str = "Int4"
                    else:
                        data_type_str = "Float4"
                except Exception:
                    data_type_str = "Float4"
            else:
                # Final fallback: default to Int4 per your request
                data_type_str = "Int4"

            # Optional debug: notify tags where we defaulted (remove/comment out if noisy)
            if ("dataType" not in tag) and ("datatype" not in tag):
                print(
                    f"DEBUG: datatype missing for tag '{tag.get('name')}', defaulting to {data_type_str}")
        else:
            data_type_str = str(raw_dt)

        # Default values for alarm fields
        alarm_name = alarm_label = alarm_mode = alarm_setpoint = alarm_priority = alarm_notes = ""

        if "alarms" in tag and isinstance(tag["alarms"], list) and len(tag["alarms"]) > 0:
            alarm = tag["alarms"][0]  # only handle the first alarm for now
            alarm_name = alarm.get("name", "")
            alarm_label = alarm.get("label", "")
            alarm_mode = alarm.get("mode", "")
            alarm_setpoint = alarm.get("setpointA", "")
            alarm_priority = alarm.get("priority", "")
            alarm_notes = alarm.get("notes", "")

        row = {
            "Name": tag.get("name", ""),
            "Datatype": data_type_str,
            "Value": tag.get("value", None),
            "ValueSource": tag.get("valueSource", ""),
            "OPCPath": tag.get("opcItemPath", ""),
            "Documentation": tag.get("documentation", ""),
            "Tooltip": tag.get("tooltip", ""),
            "EngLow": tag.get("engLow", ""),
            "EngHigh": tag.get("engHigh", ""),
            "AlarmName": alarm_name,
            "AlarmLabel": alarm_label,
            "AlarmMode": alarm_mode,
            "AlarmSetpoint": alarm_setpoint,
            "AlarmPriority": alarm_priority,
            "AlarmNotes": alarm_notes,
            "Path": parent_path
        }
        flat_list.append(row)
    return flat_list

# --- Excel → Ignition JSON --- #


def excel_to_ignition_json():
    excel_file = filedialog.askopenfilename(title="Select Excel File",
                                            filetypes=[("Excel files", "*.xlsx *.xls")])
    if not excel_file:
        return

    provider_name = simpledialog.askstring(
        "Provider name", "Enter Ignition tag provider name:", initialvalue="Default")
    if provider_name is None:
        return

    opc_server = simpledialog.askstring(
        "OPC Server name", "Enter OPC Server name for OPC tags:", initialvalue="Ignition OPC UA Server")
    if opc_server is None:
        opc_server = "Ignition OPC UA Server"

    json_file = filedialog.asksaveasfilename(
        title="Save JSON File As", defaultextension=".json", filetypes=[("JSON files", "*.json")])
    if not json_file:
        return

    # read sheet labeled "tagImport" in the template excel spreadsheet
    df = pd.read_excel(excel_file, sheet_name="tagImport").fillna('')
    df.columns = [c.strip().lower() for c in df.columns]

    folder_col_candidates = ["folder", "path",
                             "folderpath", "folder name", "folder_name"]
    folder_col = next(
        (c for c in df.columns if c in folder_col_candidates), None)

    top_level_tags = []
    created_count = 0
    for idx, row in df.iterrows():
        name = row.get("name")
        if pd.isna(name) or str(name).strip() == "":
            continue
        name = str(name).strip()

        folder_parts = []
        if folder_col and not pd.isna(row.get(folder_col)):
            raw_folder = str(row.get(folder_col))
            for sep in ("/", "\\"):
                if sep in raw_folder:
                    folder_parts = [p.strip()
                                    for p in raw_folder.split(sep) if p.strip()]
                    break
            if not folder_parts and raw_folder.strip():
                folder_parts = [raw_folder.strip()]
        else:
            if "/" in name or "\\" in name:
                parts = [p.strip() for p in name.replace(
                    "\\", "/").split("/") if p.strip()]
                if len(parts) > 1:
                    folder_parts = parts[:-1]
                    name = parts[-1]

        datatype = row.get("datatype")
        value_raw = row.get("value")
        opcpath = row.get("opcpath") if "opcpath" in df.columns else None

        tag = {"name": name, "tagType": "AtomicTag",
               "dataType": datatype if (datatype and not pd.isna(datatype)) else "Float4"}

        # Documentation
        if "documentation" in df.columns and not pd.isna(row.get("documentation")):
            tag["documentation"] = str(row.get("documentation")).strip()

        # Tooltip
        if "tooltip" in df.columns and not pd.isna(row.get("tooltip")):
            tag["tooltip"] = str(row.get("tooltip")).strip()

        # Engineering low value - only populate if Excel cell is not empty
        value = row.get("englow")
        if "englow" in df.columns and pd.notna(value):
            value_str = str(value).strip()
            if value_str:                       # non-empty after stripping whitespace
                tag["engLow"] = value_str

        # Engineering high value - only populate if Excel cell is not empty
        value = row.get("enghigh")
        if "enghigh" in df.columns and pd.notna(value):
            value_str = str(value).strip()
            if value_str:                       # non-empty after stripping whitespace
                tag["engHigh"] = value_str

        # Alarming
        alarm_name = row.get("alarmname")
        alarm_label = row.get("alarmlabel")
        alarm_mode = row.get("alarmmode")
        alarm_setpoint = row.get("alarmsetpoint")
        alarm_priority = row.get("alarmpriority")
        alarm_notes = row.get("alarmnotes")
        # check if an alarm is configured
        if alarm_name != "":
            alarms = []
            if not pd.isna(alarm_name):
                alarm = {"name": str(alarm_name).strip()}
                if not pd.isna(alarm_label):
                    alarm["label"] = str(alarm_label).strip()
                if not pd.isna(alarm_mode):
                    alarm["mode"] = str(alarm_mode).strip()
                if not pd.isna(alarm_setpoint):
                    try:
                        alarm["setpointA"] = float(alarm_setpoint)
                    except ValueError:
                        # leave as string if not numeric
                        alarm["setpointA"] = alarm_setpoint
                if not pd.isna(alarm_priority):
                    alarm["priority"] = str(alarm_priority).strip()
                if not pd.isna(alarm_notes):
                    alarm["notes"] = str(alarm_notes).strip()
                alarms.append(alarm)

            if alarms:
                tag["alarms"] = alarms

        # OPC Path
        if opcpath and not pd.isna(opcpath) and str(opcpath).strip():
            tag["opcItemPath"] = str(opcpath).strip()
            tag["opcServer"] = opc_server
            tag["valueSource"] = "opc"
        else:
            tag["valueSource"] = "memory"
            tag["value"] = coerce_value(value_raw, datatype)

        container = ensure_folder_container(
            top_level_tags, folder_parts) if folder_parts else top_level_tags
        container.append(tag)
        created_count += 1

    provider = {"tagType": "Provider",
                "name": provider_name, "tags": top_level_tags}

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(provider, f, indent=2, ensure_ascii=False)

    messagebox.showinfo(
        "Done", f"Exported {created_count} tags to {json_file}")

# --- Ignition JSON → Excel --- #


def ignition_json_to_excel():
    json_file = filedialog.askopenfilename(
        title="Select Ignition JSON File", filetypes=[("JSON files", "*.json")])
    if not json_file:
        return
    excel_file = filedialog.asksaveasfilename(
        title="Save Excel File As", defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx *.xls")])
    if not excel_file:
        return

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "tags" not in data:
        messagebox.showerror("Error", "JSON file missing 'tags'.")
        return

    flat_data = flatten_tags(data["tags"])
    pd.DataFrame(flat_data).to_excel(excel_file, index=False)
    messagebox.showinfo(
        "Done", f"Exported {len(flat_data)} tags to {excel_file}")


# --- Excel → Ignition UDT JSON Import --- #
# --- (this is the "Create UDT" function) --- #

def excel_to_udt_json_gui():
    excel_file = filedialog.askopenfilename(
        title="Select Excel File",
        filetypes=[("Excel files", "*.xlsx *.xls")]
    )
    if not excel_file:
        return

    json_file = filedialog.asksaveasfilename(
        title="Save JSON File",
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")]
    )
    if not json_file:
        return

    try:
        excel_to_udt_json(excel_file, json_file)
        messagebox.showinfo("Success", f"UDT JSON saved to:\n{json_file}")
    except Exception as e:
        messagebox.showerror("Error", str(e))


def excel_to_udt_json(excel_file, json_file, top_types_name="_types_", root_format="folder_root"):
    # """
    # Create Ignition UDT JSON. Use top_types_name (default "_types_") for the top folder name.
    # root_format: "folder_root" (default), "wrapped_tags", or "tags_only".
    # """

    # read sheet labeled "udtImport" in the template excel spreadsheet
    df = pd.read_excel(excel_file, sheet_name="udtImport").fillna('')
    if 'UDTName' not in df.columns or 'TagName' not in df.columns:
        raise ValueError("Excel must contain 'UDTName' and 'TagName' columns")

    udt_types = []
    for udt_name, group in df.groupby('UDTName'):
        udt_name = str(udt_name).strip()
        if not udt_name:
            continue

        udt_obj = {"name": udt_name, "typeId": "",
                   "tagType": "UdtType", "tags": []}
        for _, row in group.iterrows():
            tag_name = str(row.get('TagName', '')).strip()
            if not tag_name:
                continue

            tag = {"name": tag_name, "tagType": "AtomicTag"}

            dt = str(row.get('Datatype', '')).strip()
            if dt:
                tag["dataType"] = dt

            vs = str(row.get('ValueSource', '')).strip()
            tag["valueSource"] = vs.lower() if vs else "memory"

            val = row.get('Value', '')
            if val != '':
                try:
                    if isinstance(val, str):
                        tag['value'] = int(
                            val) if val.isdigit() else float(val)
                    else:
                        tag['value'] = val
                except Exception:
                    tag['value'] = val

            if row.get('EngHigh', '') != '':
                try:
                    tag['engHigh'] = float(row.get('EngHigh'))
                except Exception:
                    pass
            if row.get('EngLow', '') != '':
                try:
                    tag['engLow'] = float(row.get('EngLow'))
                except Exception:
                    pass

            doc = str(row.get('Documentation', '')).strip()
            if doc:
                tag['documentation'] = doc

# < r9 update  - use parameter binding in opcItemPath
            # check if parameter binding is in use (true or false)
            pBinding = row.get('paramBinding', '')
            opc = str(row.get('OPCPath', '')).strip()
            if opc:
                if pBinding == True:
                    boundPath = {
                        "bindType": "parameter", "binding": opc}
                    tag['opcItemPath'] = boundPath
                else:
                    tag['opcItemPath'] = opc
# >
            udt_obj['tags'].append(tag)

        udt_types.append(udt_obj)

    if root_format == "folder_root":
        out = {"name": top_types_name, "tagType": "Folder", "tags": udt_types}
    elif root_format == "wrapped_tags":
        out = {"tags": [{"name": top_types_name,
                         "tagType": "Folder", "tags": udt_types}]}
    elif root_format == "tags_only":
        out = {"tags": udt_types}
    else:
        raise ValueError(
            "root_format must be 'folder_root', 'wrapped_tags', or 'tags_only'")

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"Wrote {json_file} (format={root_format})")


# --- Main GUI --- #


def main_gui():
    root = tk.Tk()
    root.title("Ignition Tag Import/Export Tool")
    root.geometry("400x250")
    tk.Label(root, text="Choose operation:", font=("Arial", 14)).pack(pady=10)
    tk.Button(root, text="Excel → Ignition JSON", width=25, height=2, command=lambda: [
              excel_to_ignition_json(), root.destroy()]).pack(pady=5)
    tk.Button(root, text="Ignition JSON → Excel", width=25, height=2, command=lambda: [
              ignition_json_to_excel(), root.destroy()]).pack(pady=5)

    # Button to create UDT JSON import file
    # btn_excel_to_udt = tk.Button(
    #     root, text="Excel → Ignition UDT JSON", width=25, height=2, command=excel_to_udt_json_gui)
    # btn_excel_to_udt.pack(pady=10)
    tk.Button(root, text="Excel → Ignition UDT JSON", width=25, height=2, command=lambda: [
              excel_to_udt_json_gui(), root.destroy()]).pack(pady=5)
    root.mainloop()


if __name__ == "__main__":
    main_gui()
