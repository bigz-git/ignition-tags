# Manual Test Plan

Check off each item as you complete it. Add notes inline where useful.

---

## Setup

- [ ] Copy `ignition_tag_tool_template.xlsx` to a working file (e.g. `test_input.xlsx`) — never edit the template directly
- [ ] Have a test Ignition gateway available (not production)
- [ ] Know how to import a tag JSON: **Tags → Tag Browser → ⋮ → Import Tags**
- [ ] Know how to import a UDT JSON: **Tags → Tag Types → ⋮ → Import**

---

## Command 1 — `generate_tags` (Excel → Provider JSON)

```
python -m ignition_tags generate_tags test_input.xlsx output.json
```

### 1A — Basic tag types (verify JSON shape, then import into Ignition)

- [x] **OPC Boolean** — row with `datatype=Boolean`, `opcpath` populated. Verify JSON has `valueSource: opc`, `opcItemPath` set, no `value` key.
- [x] **Memory Boolean** — row with `datatype=Boolean`, `opcpath` blank. Verify JSON has `valueSource: memory`, `value: false`, no `opcItemPath`.
- [x] **OPC Float4** — row with `datatype=Float4`, `opcpath` populated.
- [x] **Memory Float4** — row with `datatype=Float4`, `opcpath` blank. Verify `value: 0.0`.
- [x] **OPC Int4** — row with `datatype=Int4`, `opcpath` populated.
- [x] **Memory Int4** — row with `datatype=Int4`, `opcpath` blank. Verify `value: 0`.
- [x] **Memory String** — row with `datatype=String`, `opcpath` blank. Verify `value: ""`.
- [x] **No datatype** — leave `datatype` blank. Verify JSON defaults to `Float4`.

### 1B — Optional fields

- [x] **Documentation + tooltip** — populate both. Verify both appear in JSON and display correctly in Ignition tag browser.
- [x] **Engineering limits** — populate `englow` and `enghigh`. Verify `engLow` / `engHigh` in JSON.
- [x] **Eng unit** — populate `engunit`. Verify `engUnit` in JSON.
- [x] **ReadOnly** — set `readonly=TRUE`. Verify `readOnly: true` in JSON and tag is read-only in Ignition.

### 1C — Alarm

- [x] **Full alarm** — populate `alarmname`, `alarmlabel`, `alarmmode`, `alarmsetpoint`, `alarmpriority`, `alarmnotes`, `alarmdisplaypath`. Verify alarm sub-object in JSON. Import and confirm alarm appears on tag in Ignition.
- [x] **Alarm setpoint numeric** — setpoint should be a number in JSON (not a string).
- [x] **No alarm** — leave `alarmname` blank. Verify no `alarms` key in JSON.

### 1D — Folder nesting

- [x] **Flat (no folder)** — no `folder` column value. Tag appears at root.
- [x] **Single folder** — `folder=Area1`. Verify JSON nests tag inside one Folder node.
- [x] **Two-level folder** — `folder=Area1/Unit2`. Verify two nested Folder nodes.
- [x] **Folder in name column** — leave `folder` blank, set `name=Area1/tag1`. Verify same result as `folder=Area1`, `name=tag1`.
- [x] **Mixed** — some rows with folder, some without. Verify correct tree shape in Ignition.

### 1E — Provider / OPC server options

- [ ] **Custom provider name** — run with `--provider MySite`. Verify no name field is unexpectedly missing in JSON (currently the provider name is not written to JSON — confirm this is expected).
- [ ] **Custom OPC server** — run with `--opc-server "My OPC Server"`. Verify `opcServer` field matches on all OPC tags.

### 1F — Error handling (these should print a clean message, not a Python traceback)

- [ ] **Missing name column** — delete the `:TagName` / `name` header from the sheet. Verify error: *"No tag name column found in DEVICE_LIST sheet. Expected one of…"*
- [ ] **Blank name row** — add a row with no name. Verify warning: *"Row X: name is blank — row will be skipped"*. Confirm the row is skipped, not a crash.
- [ ] **Invalid datatype** — set `datatype=BADTYPE`. Verify warning: *"unrecognised datatype 'BADTYPE'"*. Confirm tag is still written (with BADTYPE preserved).
- [ ] **Duplicate tag path** — add two rows with identical `folder` + `name`. Verify warning: *"duplicate tag path"*.
- [ ] **valueSource=opc, no opcpath** — set `valuesource=opc`, leave `opcpath` blank. Verify warning: *"valueSource is 'opc' but opcpath is blank"*.
- [ ] **Wrong sheet name** — rename `DEVICE_LIST` sheet to something else. Verify clean error, not traceback.
- [ ] **File not found** — run with a path that doesn't exist. Verify clean error.

---

## Command 2 — `convert_tags` (Ignition JSON → Excel)

```
python -m ignition_tags convert_tags export.json output.xlsx
```

### 2A — Basic round-trip

- [ ] **Round-trip** — run `generate_tags` on your test sheet, then run `convert_tags` on the output JSON, open the resulting Excel and confirm all rows and values match the original. Pay attention to: folder paths, datatypes, opcpath, alarm fields.
- [ ] **Folders preserved** — tags nested in folders should have the correct folder path in the output Excel.
- [ ] **Alarms preserved** — alarm fields should round-trip intact.

### 2B — Real Ignition export

- [ ] **Export from Ignition** — export an existing tag tree from a real project as JSON. Run `convert_tags` on it. Verify the Excel output is readable and correct. (Tags with multiple alarms will only show the first alarm — confirm this is acceptable.)
- [ ] **Re-import round-trip** — take the Excel from the step above, run `generate_tags` on it, import back into Ignition, and verify the tag tree matches the original.

---

## Command 3 — `generate_udt` (Excel UDT_LIST → UDT JSON)

```
python -m ignition_tags generate_udt test_input.xlsx output.json --top-name _types_ --format folder_root
```

### 3A — Basic UDT

- [ ] **Memory tags only** — UDT with a few memory tags, no OPC paths, no bindings. Verify JSON shape: `tagType: UdtType`, `tags` array with `AtomicTag` entries.
- [ ] **OPC tags with static path** — `OPCPath` populated, `OPCPathBinding=FALSE`. Verify `opcItemPath` is a plain string.
- [ ] **OPC tags with parameter binding** — `OPCPathBinding=TRUE`, `OPCPath` contains `{ParamName}`. Verify `opcItemPath` is `{"bindType": "parameter", "binding": "..."}`.
- [ ] **Documentation binding** — `DocBinding=TRUE`. Verify `documentation` is a binding object.
- [ ] **EngUnit binding** — `EngUnitBinding=TRUE`. Verify `engUnit` is a binding object.
- [ ] **ReadOnly tag** — `ReadOnly=TRUE`. Verify `readOnly: true` on tag.
- [ ] **Alarm on UDT tag** — populate alarm fields. Verify alarm sub-object in JSON.

### 3B — Parameters

- [ ] **Single parameter** — one `Param1_Name / Param1_DataType / Param1_Value`. Verify `parameters` block on UdtType.
- [ ] **Multiple parameters** — two or more params. Verify all appear in `parameters` block.
- [ ] **Parameter with no default value** — leave `Param1_Value` blank. Verify `value` key is omitted (not written as empty string).
- [ ] **Invalid param datatype** — set `Param1_DataType=Number`. Verify warning logged.

### 3C — Multiple UDTs

- [ ] **Two UDTs in one sheet** — add a second `:UDTName` block below the first. Verify both UdtType objects appear in the JSON output.

### 3D — Root format options

- [ ] **folder_root** (default) — output is `{name: "_types_", tagType: Folder, tags: [...]}`.
- [ ] **wrapped_tags** — run with `--format wrapped_tags`. Output is `{tags: [{name: "_types_", ...}]}`.
- [ ] **tags_only** — run with `--format tags_only`. Output is `{tags: [...]}` with UDT types at root.

### 3E — Ignition import

- [ ] **Import UDT JSON into Ignition** — use **Tag Types → Import**. Verify UDT definition appears with correct parameters and tag members.
- [ ] **Create an instance** — manually create a UDT instance from the imported type in Ignition. Verify parameter bindings resolve correctly on OPC paths.

---

## Command 4 — `convert_udt` (Ignition UDT JSON → Excel)

```
python -m ignition_tags convert_udt export.json output.xlsx
```

### 4A — Basic round-trip

- [ ] **Round-trip** — run `generate_udt` on your UDT_LIST sheet, then run `convert_udt` on the output JSON. Open the resulting Excel and verify it matches the original sheet structure: section headers, parameters, binding flags, alarm fields.
- [ ] **Binding flags** — `DocBinding`, `OPCPathBinding`, `EngUnitBinding` should be `TRUE` where bindings exist and blank elsewhere.
- [ ] **Parameter columns** — `Param1_Name / Param1_DataType / Param1_Value` should round-trip intact.

### 4B — Real Ignition UDT export

- [ ] **Export UDT from Ignition** — export an existing UDT type from a real project. Run `convert_udt` on it. Verify the Excel is readable and the sectioned format is correct.
- [ ] **Re-import round-trip** — take the Excel from above, run `generate_udt`, import back into Ignition, and verify the UDT definition matches the original.

---

## Command 5 — UDT instances in DEVICE_LIST

UDT instances live in the lower section of the `DEVICE_LIST` sheet (`:UDTTagName` header), generated as part of `generate_tags`.

- [ ] **Single instance** — one `:UDTTagName` block with one data row. Verify `tagType: UdtInstance` and `typeId` in output JSON.
- [ ] **Instance with folder** — populate `Folder` column. Verify instance is placed inside the correct folder in the JSON tree.
- [ ] **Instance with parameters** — populate `Param1_Name / Param1_Value`. Verify `parameters` block on the instance.
- [ ] **Missing typeId** — leave `TypeId` blank. Verify warning: *"missing typeId — skipped"*.
- [ ] **Import into Ignition** — run `generate_tags` on a sheet with both atomic tags and UDT instances. Import the JSON. Verify the tag tree contains both atomic tags and resolved UDT instances.

---

## Notes

Use this section to capture anything surprising or broken during testing.

| Date | Command | Finding | Resolved? |
|------|---------|---------|-----------|
|4/27  |generate-tags|entering an undefined tag group will import as entered wihtout error even if tag group is undefined   | na   |
|4/27  |generate-tags|alarm priority must start with capital letter. options are Diagnostic, Low, Medium, High, and Critical| no|
|4/27  |generate-tags|alarm mode must start with capital letter. If it doesnt match available options exactly, it will default to "Equal". There are many options available, but for the purpose of this tool, these should be used: Equal, Not Equal, When True, and When False. These options work for Boolean alarms, this can be expanded later| no|
|4/27  |generate-tags|alarm setpoint column can work with 0 or "FALSE" and 1 or "TRUE"   | na   |
|4/27  |generate-tags|when defining a folder structure, the structure can either be defined in the :TagName column with the "folder/subfolder/tagname" format OR in the Folder column using "folder/subfolder" but not both  | na   |