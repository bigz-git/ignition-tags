# ignition-tags

A command-line tool for bidirectional conversion between Excel spreadsheets and
Ignition SCADA system JSON tag configurations.  Used by industrial automation
engineers to bulk-create and export tag hierarchies without clicking through
Ignition's designer one tag at a time.

## Features

- **Excel -> Ignition JSON** — convert a `tagImport` sheet into a Provider JSON
  file ready to drag-and-drop into Ignition's Tag Browser.
- **Ignition JSON -> Excel** — flatten an Ignition JSON export back into a
  `tagImport` sheet for editing.  Output column names match the import format
  exactly, so the round-trip works without manual cleanup.
- **Excel -> UDT JSON** — convert a `udtImport` sheet into a UDT type
  definition JSON with optional OPC parameter binding.

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

The input file must have a sheet named `tagImport` with these columns:

| Column | Required | Description |
|---|---|---|
| `name` | yes | Tag name (may include folder path separated by `/`) |
| `folder` | no | Folder path (e.g. `Line1/Station2`) |
| `datatype` | no | Ignition data type (e.g. `Float4`, `Int4`, `Boolean`) — defaults to `Float4` |
| `value` | no | Default value for memory tags |
| `opcpath` | no | OPC item path — if set the tag becomes OPC-connected |
| `documentation` | no | Long description |
| `tooltip` | no | Short tooltip |
| `englow` | no | Engineering low limit |
| `enghigh` | no | Engineering high limit |
| `alarmname` | no | Alarm name — presence of this field triggers alarm creation |
| `alarmlabel` | no | Alarm display label |
| `alarmmode` | no | Alarm mode (e.g. `AboveSetpoint`) |
| `alarmsetpoint` | no | Alarm setpoint value |
| `alarmpriority` | no | Alarm priority |
| `alarmnotes` | no | Alarm notes |

### Ignition JSON -> Excel

```bash
python -m ignition_tags convert_tags export.json output.xlsx
```

Reads an Ignition JSON export and writes a `tagImport` sheet using the same
column names as the import format above.

### Excel -> UDT JSON

```bash
python -m ignition_tags generate_udt input.xlsx output.json
python -m ignition_tags generate_udt input.xlsx output.json --top-name _types_ --format folder_root
```

Options:

| Option | Default | Choices | Description |
|---|---|---|---|
| `--top-name NAME` | `_types_` | any | Top-level folder name in the JSON |
| `--format` | `folder_root` | `folder_root`, `wrapped_tags`, `tags_only` | Root structure shape |

The input file must have a sheet named `udtImport` with these columns:
`UDTName`, `TagName`, `Datatype`, `ValueSource`, `Value`, `OPCPath`,
`EngHigh`, `EngLow`, `Documentation`, `paramBinding`.

## Excel Template

See `archive/ignition_tag_tool_excel_format_for_r9.xlsx` for a reference
spreadsheet with both `tagImport` and `udtImport` sheets pre-formatted with
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
requirements.txt        Python dependencies (pandas, openpyxl)
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
