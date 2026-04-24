"""
CLI entry point for ignition_tags.

Run with:
    python -m ignition_tags <command> [args]

Commands
--------
    excel2json   Convert a tagImport Excel sheet to Ignition Provider JSON.
    json2excel   Convert an Ignition JSON export to a tagImport Excel sheet.
    excel2udt    Convert a udtImport Excel sheet to Ignition UDT JSON.

Each command is a thin I/O wrapper: it reads a file, calls a pure core
function, and writes the result.  Adding a new command means adding one
subparser block and one cmd_* function below.
"""

import argparse
import json
import logging
import sys

import pandas as pd

from .columns import TAG_IMPORT_SHEET, UDT_IMPORT_SHEET
import openpyxl

from .core import build_tag_provider, build_udt_types, flatten_tags, flatten_udt_types

logger = logging.getLogger(__name__)


# ── Command handlers ───────────────────────────────────────────────────────────

def cmd_excel_to_json(args: argparse.Namespace) -> None:
    """Excel tagImport sheet -> Ignition Provider JSON."""
    df = pd.read_excel(args.input, sheet_name=TAG_IMPORT_SHEET)
    provider = build_tag_provider(df, args.provider, args.opc_server)
    _write_json(provider, args.output)
    tag_count = sum(1 for t in _iter_atomic(provider.get("tags", [])))
    print(f"Wrote {tag_count} tags to {args.output}")


def cmd_json_to_excel(args: argparse.Namespace) -> None:
    """Ignition Provider JSON -> Excel tagImport sheet."""
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    if "tags" not in data:
        sys.exit(f"Error: {args.input!r} is missing a top-level 'tags' key.")
    rows = flatten_tags(data["tags"])
    pd.DataFrame(rows).to_excel(args.output, sheet_name=TAG_IMPORT_SHEET, index=False)
    print(f"Wrote {len(rows)} tags to {args.output}")


def cmd_udt_to_excel(args: argparse.Namespace) -> None:
    """Ignition UDT JSON -> Excel udtImport sheet."""
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    rows = flatten_udt_types(data)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = UDT_IMPORT_SHEET
    for row in rows:
        ws.append(row)
    wb.save(args.output)
    udt_count = sum(1 for r in rows if r and str(r[0]) == ":UDTName")
    print(f"Wrote {udt_count} UDT(s) to {args.output}")


def cmd_excel_to_udt(args: argparse.Namespace) -> None:
    """Excel udtImport sheet -> Ignition UDT JSON."""
    df = pd.read_excel(args.input, sheet_name=UDT_IMPORT_SHEET, header=None)
    result = build_udt_types(
        df,
        top_types_name=args.top_name,
        root_format=args.format,
        opc_server=args.opc_server,
    )
    _write_json(result, args.output)
    print(f"Wrote {args.output}")


# ── Parser ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ignition_tags",
        description="Ignition SCADA tag import/export tool",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    # ── excel2json ─────────────────────────────────────────────────────────────
    p = sub.add_parser(
        "excel2json",
        help="Convert Excel tagImport sheet -> Ignition Provider JSON",
    )
    p.add_argument("input",  help="Input Excel file (.xlsx)")
    p.add_argument("output", help="Output JSON file")
    p.add_argument(
        "--provider",
        default="Default",
        metavar="NAME",
        help="Tag provider name (default: Default)",
    )
    p.add_argument(
        "--opc-server",
        default="Ignition OPC UA Server",
        dest="opc_server",
        metavar="NAME",
        help='OPC server name for OPC-connected tags (default: "Ignition OPC UA Server")',
    )
    p.set_defaults(func=cmd_excel_to_json)

    # ── json2excel ─────────────────────────────────────────────────────────────
    p = sub.add_parser(
        "json2excel",
        help="Convert Ignition JSON export -> Excel tagImport sheet",
    )
    p.add_argument("input",  help="Input JSON file")
    p.add_argument("output", help="Output Excel file (.xlsx)")
    p.set_defaults(func=cmd_json_to_excel)

    # ── udt2excel ──────────────────────────────────────────────────────────────
    p = sub.add_parser(
        "udt2excel",
        help="Convert Ignition UDT JSON export -> Excel udtImport sheet",
    )
    p.add_argument("input",  help="Input UDT JSON file")
    p.add_argument("output", help="Output Excel file (.xlsx)")
    p.set_defaults(func=cmd_udt_to_excel)

    # ── excel2udt ──────────────────────────────────────────────────────────────
    p = sub.add_parser(
        "excel2udt",
        help="Convert Excel udtImport sheet -> Ignition UDT JSON",
    )
    p.add_argument("input",  help="Input Excel file (.xlsx)")
    p.add_argument("output", help="Output JSON file")
    p.add_argument(
        "--top-name",
        default="_types_",
        dest="top_name",
        metavar="NAME",
        help="Top-level folder name in JSON output (default: _types_)",
    )
    p.add_argument(
        "--format",
        default="folder_root",
        choices=["folder_root", "wrapped_tags", "tags_only"],
        help="Root structure format (default: folder_root)",
    )
    p.add_argument(
        "--opc-server",
        default="Ignition OPC UA Server",
        dest="opc_server",
        metavar="NAME",
        help='OPC server name for OPC-connected UDT tags (default: "Ignition OPC UA Server")',
    )
    p.set_defaults(func=cmd_excel_to_udt)

    return parser


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_json(data: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _iter_atomic(tags: list):
    """Yield every AtomicTag node in a (possibly nested) tag tree."""
    for tag in tags:
        if tag.get("tagType") == "Folder":
            yield from _iter_atomic(tag.get("tags", []))
        else:
            yield tag


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
    try:
        args.func(args)
    except Exception as exc:
        logger.debug("Unhandled exception", exc_info=True)
        sys.exit(f"Error: {exc}")


if __name__ == "__main__":
    main()
