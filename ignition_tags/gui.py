"""Tkinter GUI for ignition_tags.

Launch with:
    python -m ignition_tags gui
"""

import json
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import openpyxl
import pandas as pd

from . import __version__
from .columns import TAG_IMPORT_SHEET, UDT_IMPORT_SHEET
from .core import (
    build_tag_provider,
    build_udt_instances,
    build_udt_types,
    ensure_folder_container,
    flatten_tags,
    flatten_udt_types,
    split_device_list,
)


class _TextLogHandler(logging.Handler):
    """Logging handler that appends records to a read-only tk.Text widget."""

    def __init__(self, widget: tk.Text) -> None:
        super().__init__()
        self._widget = widget

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record) + "\n"
        tag = "error" if record.levelno >= logging.ERROR else "warning" if record.levelno >= logging.WARNING else None
        self._widget.configure(state="normal")
        self._widget.insert(tk.END, msg, (tag,) if tag else ())
        self._widget.see(tk.END)
        self._widget.configure(state="disabled")


# ── Column reference data ──────────────────────────────────────────────────────
# Each tuple: (Excel column name, Required, Description)

_DEVICE_LIST_COLUMNS = [
    ("name",             "Yes", "Tag name; may contain / to encode a folder path"),
    ("folder",           "No",  "Folder path, e.g. Line1/Station2"),
    ("datatype",         "No",  "Ignition data type: Float4, Int4, Boolean, String, … (default Float4)"),
    ("value",            "No",  "Default value for memory tags"),
    ("opcpath",          "No",  "OPC item path — presence makes tag OPC-connected"),
    ("valuesource",      "No",  "Explicit value source override: opc or memory"),
    ("readonly",         "No",  "Mark tag read-only: true / 1 / yes"),
    ("documentation",    "No",  "Long description text"),
    ("tooltip",          "No",  "Short tooltip text"),
    ("engunit",          "No",  "Engineering unit label"),
    ("englow",           "No",  "Engineering low limit"),
    ("enghigh",          "No",  "Engineering high limit"),
    ("taggroup",         "No",  "Tag group name"),
    ("alarmname",        "No",  "Alarm name — required to create an alarm sub-object"),
    ("alarmlabel",       "No",  "Alarm display label"),
    ("alarmmode",        "No",  "Alarm mode, e.g. AboveSetpoint"),
    ("alarmsetpoint",    "No",  "Alarm setpoint value (numeric)"),
    ("alarmpriority",    "No",  "Alarm priority"),
    ("alarmnotes",       "No",  "Alarm notes"),
    ("alarmdisplaypath", "No",  "Alarm display path"),
]

# :UDTName section — one data row per UDT type
_UDT_NAME_COLUMNS = [
    ("UDTName",        "Yes", "UDT type name"),
    ("Documentation",  "No",  "UDT type description"),
    ("Param1_Name",    "No",  "Parameter name (repeat as Param2_Name, Param3_Name, …)"),
    ("Param1_DataType","No",  "Parameter data type: Integer, Float, or String"),
    ("Param1_Value",   "No",  "Parameter default value (optional)"),
]

# :TagName section — one data row per tag in the UDT above
_UDT_TAG_COLUMNS = [
    ("TagName",         "Yes", "Tag name within the UDT"),
    ("Documentation",   "No",  "Tag description; supports {Param} binding"),
    ("ValueSource",     "No",  "memory or opc — inferred from OPCPath when omitted"),
    ("DataType",        "No",  "Ignition data type: Float4, Int4, Boolean, String, …"),
    ("Value",           "No",  "Default value for memory tags"),
    ("OPCPath",         "No",  "OPC item path; supports {Param} binding"),
    ("EngUnit",         "No",  "Engineering unit label; supports {Param} binding"),
    ("EngHigh",         "No",  "Engineering high limit; supports {Param} binding"),
    ("EngLow",          "No",  "Engineering low limit; supports {Param} binding"),
    ("ReadOnly",        "No",  "Mark tag read-only: true / 1 / yes"),
    ("AlarmName",       "No",  "Alarm name — required to create an alarm sub-object"),
    ("AlarmPriority",   "No",  "Alarm priority"),
    ("AlarmLabel",      "No",  "Alarm display label"),
    ("AlarmNotes",      "No",  "Alarm notes"),
    ("AlarmMode",       "No",  "Alarm mode, e.g. AboveSetpoint"),
    ("AlarmSetpoint",   "No",  "Alarm setpoint value (numeric)"),
    ("AlarmDisplayPath","No",  "Alarm display path"),
]


class IgnitionTagsGUI(tk.Tk):
    _XLSX = [("Excel files", "*.xlsx"), ("All files", "*.*")]
    _JSON = [("JSON files", "*.json"), ("All files", "*.*")]

    def __init__(self) -> None:
        super().__init__()
        self.title(f"Ignition Tags Tool  v{__version__}")
        self.minsize(620, 520)
        self.resizable(True, True)
        self._build_ui()
        self._setup_logging()

    # ── Top-level layout ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_menu()
        notebook = ttk.Notebook(self)
        notebook.pack(fill="x", padx=8, pady=8)
        self._build_tags_tab(notebook)
        self._build_udts_tab(notebook)
        self._build_log_panel()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.configure(menu=menubar)
        help_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Column Reference…", command=self._show_column_reference)
        help_menu.add_separator()
        help_menu.add_command(label="About…", command=self._show_about)

    def _build_tags_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=4)
        notebook.add(tab, text="Tags")

        # Excel -> Provider JSON
        gen = ttk.LabelFrame(tab, text="Excel → Provider JSON", padding=6)
        gen.pack(fill="x", pady=(0, 6))
        gen.columnconfigure(1, weight=1)

        self._v_gt_in = tk.StringVar()
        self._v_gt_out = tk.StringVar()
        self._v_gt_provider = tk.StringVar(value="Default")
        self._v_gt_opc = tk.StringVar(value="Ignition OPC UA Server")

        self._file_row(gen, 0, "Input (.xlsx)", self._v_gt_in, self._XLSX)
        self._file_row(gen, 1, "Output (.json)", self._v_gt_out, self._JSON, save=True)
        self._entry_row(gen, 2, "Provider name", self._v_gt_provider)
        self._entry_row(gen, 3, "OPC server", self._v_gt_opc)
        ttk.Button(gen, text="Generate Tags JSON", command=self._run_generate_tags).grid(
            row=4, column=0, columnspan=3, pady=(8, 2)
        )

        # JSON -> Excel
        conv = ttk.LabelFrame(tab, text="JSON → Excel", padding=6)
        conv.pack(fill="x")
        conv.columnconfigure(1, weight=1)

        self._v_ct_in = tk.StringVar()
        self._v_ct_out = tk.StringVar()

        self._file_row(conv, 0, "Input (.json)", self._v_ct_in, self._JSON)
        self._file_row(conv, 1, "Output (.xlsx)", self._v_ct_out, self._XLSX, save=True)
        ttk.Button(conv, text="Convert Tags to Excel", command=self._run_convert_tags).grid(
            row=2, column=0, columnspan=3, pady=(8, 2)
        )

    def _build_udts_tab(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=4)
        notebook.add(tab, text="UDTs")

        # Excel -> UDT JSON
        gen = ttk.LabelFrame(tab, text="Excel → UDT JSON", padding=6)
        gen.pack(fill="x", pady=(0, 6))
        gen.columnconfigure(1, weight=1)

        self._v_gu_in = tk.StringVar()
        self._v_gu_out = tk.StringVar()
        self._v_gu_top = tk.StringVar(value="_types_")
        self._v_gu_fmt = tk.StringVar(value="folder_root")
        self._v_gu_opc = tk.StringVar(value="Ignition OPC UA Server")

        self._file_row(gen, 0, "Input (.xlsx)", self._v_gu_in, self._XLSX)
        self._file_row(gen, 1, "Output (.json)", self._v_gu_out, self._JSON, save=True)
        self._entry_row(gen, 2, "Top name", self._v_gu_top)
        self._combo_row(gen, 3, "Format", self._v_gu_fmt, ["folder_root", "wrapped_tags", "tags_only"])
        self._entry_row(gen, 4, "OPC server", self._v_gu_opc)
        ttk.Button(gen, text="Generate UDT JSON", command=self._run_generate_udt).grid(
            row=5, column=0, columnspan=3, pady=(8, 2)
        )

        # UDT JSON -> Excel
        conv = ttk.LabelFrame(tab, text="JSON → Excel", padding=6)
        conv.pack(fill="x")
        conv.columnconfigure(1, weight=1)

        self._v_cu_in = tk.StringVar()
        self._v_cu_out = tk.StringVar()

        self._file_row(conv, 0, "Input (.json)", self._v_cu_in, self._JSON)
        self._file_row(conv, 1, "Output (.xlsx)", self._v_cu_out, self._XLSX, save=True)
        ttk.Button(conv, text="Convert UDT to Excel", command=self._run_convert_udt).grid(
            row=2, column=0, columnspan=3, pady=(8, 2)
        )

    def _build_log_panel(self) -> None:
        frame = ttk.LabelFrame(self, text="Output", padding=4)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        btn_bar = ttk.Frame(frame)
        btn_bar.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Button(btn_bar, text="Clear", command=self._clear_log).pack(side="right")

        scroll = ttk.Scrollbar(frame)
        scroll.pack(side="right", fill="y")

        self._log_text = tk.Text(
            frame, height=8, state="disabled", wrap="word",
            yscrollcommand=scroll.set,
        )
        self._log_text.pack(side="left", fill="both", expand=True)
        scroll.configure(command=self._log_text.yview)

        self._log_text.tag_configure("ok", foreground="green")
        self._log_text.tag_configure("warning", foreground="#CC7700")
        self._log_text.tag_configure("error", foreground="red")

    def _setup_logging(self) -> None:
        self._log_handler = _TextLogHandler(self._log_text)
        self._log_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        pkg_logger = logging.getLogger("ignition_tags")
        pkg_logger.setLevel(logging.DEBUG)
        pkg_logger.addHandler(self._log_handler)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        logging.getLogger("ignition_tags").removeHandler(self._log_handler)
        self.destroy()

    # ── Help dialogs ───────────────────────────────────────────────────────────

    def _show_column_reference(self) -> None:
        win = tk.Toplevel(self)
        win.title("Column Reference")
        win.minsize(720, 480)
        win.grab_set()

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # DEVICE_LIST tab
        tag_tab = ttk.Frame(nb, padding=4)
        nb.add(tag_tab, text="DEVICE_LIST")
        self._column_treeview(tag_tab, _DEVICE_LIST_COLUMNS, expand=True)

        # UDT_LIST tab
        udt_tab = ttk.Frame(nb, padding=4)
        nb.add(udt_tab, text="UDT_LIST")

        ttk.Label(udt_tab, text=":UDTName section — one row per UDT type",
                  font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self._column_treeview(udt_tab, _UDT_NAME_COLUMNS, expand=False)

        ttk.Label(udt_tab, text=":TagName section — one row per tag in the UDT above",
                  font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(8, 2))
        self._column_treeview(udt_tab, _UDT_TAG_COLUMNS, expand=True)

        ttk.Label(udt_tab, text="Tip: any cell value containing { } is automatically written as a parameter binding.",
                  foreground="gray").pack(anchor="w", pady=(6, 0))

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About Ignition Tags Tool",
            f"Ignition Tags Tool  v{__version__}\n\n"
            "Bidirectional conversion between Excel spreadsheets\n"
            "and Ignition SCADA tag configuration JSON.\n\n"
            "Commands:\n"
            "  generate-tags  —  Excel DEVICE_LIST → Provider JSON\n"
            "  convert-tags   —  Provider JSON → Excel DEVICE_LIST\n"
            "  generate-udt   —  Excel UDT_LIST → UDT JSON\n"
            "  convert-udt    —  UDT JSON → Excel UDT_LIST\n"
            "  gui            —  Launch this window",
            parent=self,
        )

    @staticmethod
    def _column_treeview(parent, rows, expand=True) -> None:
        cols = ("Column", "Required", "Description")
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=expand)

        tree = ttk.Treeview(
            frame, columns=cols, show="headings", selectmode="browse",
            height=len(rows),
        )
        tree.heading("Column",      text="Column")
        tree.heading("Required",    text="Required")
        tree.heading("Description", text="Description")
        tree.column("Column",      width=155, minwidth=120, stretch=False)
        tree.column("Required",    width=70,  minwidth=60,  stretch=False, anchor="center")
        tree.column("Description", width=450, minwidth=200, stretch=True)

        for row in rows:
            tree.insert("", tk.END, values=row)

        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # ── Layout helpers ─────────────────────────────────────────────────────────

    def _file_row(self, parent, row, label, var, filetypes, save=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 4), pady=2)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ext = filetypes[0][1].lstrip("*")
        if save:
            cmd = lambda v=var, ft=filetypes, e=ext: v.set(
                filedialog.asksaveasfilename(filetypes=ft, defaultextension=e) or v.get()
            )
        else:
            cmd = lambda v=var, ft=filetypes: v.set(
                filedialog.askopenfilename(filetypes=ft) or v.get()
            )
        ttk.Button(parent, text="Browse…", command=cmd).grid(row=row, column=2, padx=(2, 0), pady=2)

    def _entry_row(self, parent, row, label, var):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 4), pady=2)
        ttk.Entry(parent, textvariable=var).grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=2, pady=2
        )

    def _combo_row(self, parent, row, label, var, values):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 4), pady=2)
        ttk.Combobox(parent, textvariable=var, values=values, state="readonly").grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=2, pady=2
        )

    # ── Log helpers ────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        tag = "ok" if msg.startswith("OK:") else None
        self._log_text.configure(state="normal")
        self._log_text.insert(tk.END, msg + "\n", (tag,) if tag else ())
        self._log_text.see(tk.END)
        self._log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state="disabled")

    # ── Command runners ────────────────────────────────────────────────────────

    def _run_generate_tags(self) -> None:
        inp = self._v_gt_in.get().strip()
        out = self._v_gt_out.get().strip()
        if not inp or not out:
            messagebox.showwarning("Missing paths", "Both input and output paths are required.")
            return
        provider = self._v_gt_provider.get().strip() or "Default"
        opc = self._v_gt_opc.get().strip() or "Ignition OPC UA Server"
        try:
            raw_df = pd.read_excel(inp, sheet_name=TAG_IMPORT_SHEET, header=None)
            tag_df, udt_raw_df = split_device_list(raw_df)
            provider_data = (
                build_tag_provider(tag_df, provider, opc) if not tag_df.empty else {"tags": []}
            )
            top_tags = provider_data["tags"]
            udt_count = 0
            if not udt_raw_df.empty:
                instances = build_udt_instances(udt_raw_df)
                for folder_parts, inst in instances:
                    ensure_folder_container(top_tags, folder_parts).append(inst)
                udt_count = len(instances)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(provider_data, f, indent=2, ensure_ascii=False)
            atomic = sum(1 for _ in self._iter_atomic(top_tags))
            parts = [f"{atomic} atomic tag(s)"]
            if udt_count:
                parts.append(f"{udt_count} UDT instance(s)")
            self._log(f"OK: Wrote {', '.join(parts)} to {out}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _run_convert_tags(self) -> None:
        inp = self._v_ct_in.get().strip()
        out = self._v_ct_out.get().strip()
        if not inp or not out:
            messagebox.showwarning("Missing paths", "Both input and output paths are required.")
            return
        try:
            with open(inp, encoding="utf-8") as f:
                data = json.load(f)
            if "tags" not in data:
                messagebox.showerror("Error", f"{inp!r} is missing a top-level 'tags' key.")
                return
            rows = flatten_tags(data["tags"])
            pd.DataFrame(rows).to_excel(out, sheet_name=TAG_IMPORT_SHEET, index=False)
            self._log(f"OK: Wrote {len(rows)} tag(s) to {out}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _run_generate_udt(self) -> None:
        inp = self._v_gu_in.get().strip()
        out = self._v_gu_out.get().strip()
        if not inp or not out:
            messagebox.showwarning("Missing paths", "Both input and output paths are required.")
            return
        top = self._v_gu_top.get().strip() or "_types_"
        fmt = self._v_gu_fmt.get().strip() or "folder_root"
        opc = self._v_gu_opc.get().strip() or "Ignition OPC UA Server"
        try:
            df = pd.read_excel(inp, sheet_name=UDT_IMPORT_SHEET, header=None)
            result = build_udt_types(df, top_types_name=top, root_format=fmt, opc_server=opc)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            self._log(f"OK: Wrote UDT JSON to {out}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _run_convert_udt(self) -> None:
        inp = self._v_cu_in.get().strip()
        out = self._v_cu_out.get().strip()
        if not inp or not out:
            messagebox.showwarning("Missing paths", "Both input and output paths are required.")
            return
        try:
            with open(inp, encoding="utf-8") as f:
                data = json.load(f)
            rows = flatten_udt_types(data)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = UDT_IMPORT_SHEET
            for row in rows:
                ws.append(row)
            wb.save(out)
            udt_count = sum(1 for r in rows if r and str(r[0]) == ":UDTName")
            self._log(f"OK: Wrote {udt_count} UDT(s) to {out}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    @staticmethod
    def _iter_atomic(tags):
        for tag in tags:
            if tag.get("tagType") == "Folder":
                yield from IgnitionTagsGUI._iter_atomic(tag.get("tags", []))
            else:
                yield tag


def launch_gui() -> None:
    app = IgnitionTagsGUI()
    app.mainloop()
