# ignition-tags

A command-line tool for bidirectional conversion between Excel spreadsheets and
Ignition SCADA system JSON tag configurations.  Used by industrial automation
engineers to bulk-create and export tag hierarchies without clicking through
Ignition's designer one tag at a time.

## Features

- **Excel -> Ignition JSON** — convert a `DEVICE_LIST` sheet into a Provider JSON
  file ready to drag-and-drop into Ignition's Tag Browser.  Supports atomic tags
  and UDT instances in the same sheet.
- **Ignition JSON -> Excel** — flatten an Ignition JSON export back into a
  `DEVICE_LIST` sheet for editing.  Output column names match the import format
  exactly, so the round-trip works without manual cleanup.
- **Excel -> UDT JSON** — convert a `UDT_LIST` sheet into a UDT type definition
  JSON with optional OPC parameter binding.
- **UDT JSON -> Excel** — flatten an Ignition UDT JSON export back into a
  `UDT_LIST` sheet.

## Setup

Requires Python 3.10+.

```bash
# Create and activate a virtual environment (Windows)
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

All commands are run as a Python module.  Use `-v` for verbose/debug output.

### Excel -> Ignition Provider JSON

```bash
python -m ignition_tags generate_tags input.xlsx output.json
python -m ignition_tags generate_tags input.xlsx output.json --provider MySite --opc-server "My OPC Server"
```

Options:

| Option | Default | Description |
|---|---|---|
| `--provider NAME` | `Default` | Top-level tag provider name in the JSON |
| `--opc-server NAME` | `Ignition OPC UA Server` | OPC server name written into OPC-connected tags |

The input file must have a sheet named `DEVICE_LIST`.  The first row is the
column header.  Supported columns:

| Column | Required | Description |
|---|---|---|
| `name` | yes | Tag name (may include folder path separated by `/`) |
| `folder` | no | Folder path (e.g. `Line1/Station2`) |
| `datatype` | no | Ignition data type (e.g. `Float4`, `Int4`, `Boolean`) — defaults to `Float4` |
| `value` | no | Default value for memory tags |
| `opcpath` | no | OPC item path — if set the tag becomes OPC-connected |
| `valuesource` | no | Explicit `opc` or `memory` override |
| `readonly` | no | Set `true`/`1`/`yes` to mark the tag read-only |
| `documentation` | no | Long description |
| `tooltip` | no | Short tooltip |
| `engunit` | no | Engineering unit label |
| `englow` | no | Engineering low limit |
| `enghigh` | no | Engineering high limit |
| `alarmname` | no | Alarm name — presence of this field triggers alarm creation |
| `alarmlabel` | no | Alarm display label |
| `alarmmode` | no | Alarm mode (e.g. `AboveSetpoint`) |
| `alarmsetpoint` | no | Alarm setpoint value |
| `alarmpriority` | no | Alarm priority |
| `alarmnotes` | no | Alarm notes |
| `alarmdisplaypath` | no | Alarm display path |

The sheet may also contain a UDT instance section below the atomic tag rows.
Start that section with a `:UDTTagName` header row (see [Excel -> UDT Instances](#excel---udt-instances)).

### Ignition JSON -> Excel

```bash
python -m ignition_tags convert_tags export.json output.xlsx
```

Reads an Ignition JSON export and writes a `DEVICE_LIST` sheet using the same
column names as the import format above.

### Excel -> UDT Type JSON

```bash
python -m ignition_tags generate_udt input.xlsx output.json
python -m ignition_tags generate_udt input.xlsx output.json --top-name _types_ --format folder_root --opc-server "My OPC Server"
```

Options:

| Option | Default | Choices | Description |
|---|---|---|---|
| `--top-name NAME` | `_types_` | any | Top-level folder name in the JSON |
| `--format` | `folder_root` | `folder_root`, `wrapped_tags`, `tags_only` | Root structure shape |
| `--opc-server NAME` | `Ignition OPC UA Server` | any | OPC server name for OPC-connected UDT tags |

The input file must have a sheet named `UDT_LIST` using a **sectioned format**
(read with `header=None`).  Rows whose first cell starts with `:` are section
headers that define column names for the rows beneath them.  Two section types
per UDT block:

- `:UDTName` row — one data row per UDT type.  Columns: `UDTName`,
  `Documentation`, `Param1_Name`, `Param1_DataType`, `Param1_Value`, `Param2_*`, …
- `:TagName` row — one data row per tag in the UDT above.  Columns:
  `TagName`, `DocBinding`, `Documentation`, `ValueSource`, `DataType`, `Value`,
  `OPCPathBinding`, `OPCPath`, `EngUnitBinding`, `EngUnit`, `EngHigh`, `EngLow`,
  `ReadOnly`, `AlarmName`, `AlarmPriority`, `AlarmLabel`, `AlarmNotes`,
  `AlarmMode`, `AlarmSetpoint`, `AlarmDisplayPath`

`DocBinding`, `OPCPathBinding`, and `EngUnitBinding` are boolean columns: when
`TRUE`, the corresponding field is written as a parameter binding
`{"bindType": "parameter", "binding": <value>}` instead of a plain string.

### UDT JSON -> Excel

```bash
python -m ignition_tags convert_udt export.json output.xlsx
```

Reads an Ignition UDT JSON export and writes a `UDT_LIST` sheet in the sectioned
format above.  Accepts any root shape: a single `UdtType`, `folder_root`,
`wrapped_tags`, or `tags_only`.

### Excel -> UDT Instances

UDT instances are placed in the same `DEVICE_LIST` sheet as atomic tags, below
the tag rows.  Start the instance section with a `:UDTTagName` header row:

```
:UDTTagName | Documentation | TypeId          | Folder     | Param1_Name | Param1_DataType | Param1_Value
pump_1      | Feed pump     | _types_/Pump    | Area1/Unit2 | DeviceName  | String          | P-101
```

The `generate_tags` command processes both sections in one pass and merges them
into a single Provider JSON.

## Excel Template

See `archive/ignition_tag_tool_excel_format_for_r9.xlsx` for a reference
spreadsheet with both `DEVICE_LIST` and `UDT_LIST` sheets pre-formatted with
the correct column headers.

## Project Layout

```
ignition_tags/          Python package (CLI + library)
  columns.py            Column schema dicts — edit here to add/rename columns
  core.py               Pure conversion functions (no file I/O, no UI)
  cli.py                Argparse entry point and command handlers
  gui.py                GUI placeholder (not yet implemented)
  __init__.py           Public API re-exports for scripting/GUI use
  __main__.py           Enables python -m ignition_tags

archive/                Original single-file GUI tool (reference only)
json_files/             Working directory for generated JSON output
requirements.txt        Python dependencies (pandas, openpyxl)
```

## Public API

The three core functions are importable directly for scripting or GUI use:

```python
from ignition_tags import (
    build_tag_provider,   # DataFrame -> Provider JSON dict
    build_udt_types,      # DataFrame -> UDT type JSON dict
    build_udt_instances,  # DataFrame -> list of (folder_parts, instance_dict)
    flatten_tags,         # tag tree -> list of row dicts (DEVICE_LIST format)
    flatten_udt_types,    # UDT JSON -> list of raw rows (UDT_LIST format)
    split_device_list,    # raw DEVICE_LIST DataFrame -> (tag_df, udt_raw_df)
)
```

## Extending the Tool

**Add a new Excel column** — open `ignition_tags/columns.py` and add one entry
to the relevant dict (`TAG_SCALAR_FIELDS`, `TAG_ENG_FIELDS`, `TAG_ALARM_FIELDS`,
or `UDT_TAG_FIELDS`).  The processing loop picks it up automatically.

**Add a new command** — open `ignition_tags/cli.py`, add a `sub.add_parser(...)`
block, and write a `cmd_*` function that reads a file, calls a core function,
and writes the result.

**Build the GUI** — import from the package and wrap with Tkinter dialogs:

```python
from ignition_tags import build_tag_provider, build_udt_types, flatten_tags
```

See `ignition_tags/gui.py` for the starting point and
`archive/ignition_tag_tool_r9.py` for the original GUI as a reference.

## TODO

- [ ] **Error checking** — add structured validation before conversion (missing
  required columns, invalid datatype strings, duplicate tag names, malformed OPC
  paths) and surface actionable messages instead of stack traces.
- [ ] **Nested UDTs** — investigate support for UDT types that contain other UDT
  instances as members, including how the sectioned sheet format should represent
  the nesting hierarchy.
- [ ] **GUI** — implement `ignition_tags/gui.py` as a Tkinter front-end using the
  existing public API (`build_tag_provider`, `build_udt_types`, `flatten_tags`).
- [ ] **Package as wheel** — add `pyproject.toml` (or `setup.cfg`) so the tool
  can be installed with `pip install .` and invoked as `ignition-tags` without
  the `python -m` prefix.
- [ ] **Version number tracking** — introduce a `__version__` string (e.g. in
  `__init__.py`) and wire it to `--version` in the CLI and the wheel metadata.
