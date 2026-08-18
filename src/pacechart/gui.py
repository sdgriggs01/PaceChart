"""Tkinter GUI for PaceChart.

Wires pacechart.app_state.AppState to widgets. Business logic lives in
AppState (unit tested in test_app_state.py, no Tkinter involved) — this
module is intentionally thin: build widgets, read/write AppState,
redraw. Network I/O (scraper.fetch_*) runs on a background thread and
reports back through a queue so the UI never blocks or is touched from
another thread.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from pacechart.app_state import AppState, PaceKey
from pacechart.calculator import DISPLAY_DISTANCES_KM, TRAINING_ZONES, format_minutes, output_decimals_for
from pacechart.models import GENDER_LABELS, Gender, RaceResult
from pacechart.pdf import fits_one_page, generate_pdf
from pacechart.scraper import attach_results, fetch_meet_results, fetch_roster, fetch_schedule

ASSETS_DIR = Path(__file__).parent / "assets"
ICON_PATH = ASSETS_DIR / "logo.png"

_BOLD = ("TkDefaultFont", 9, "bold")

# Green Hope school colors (application chrome only — the exported PDF is
# intentionally left unstyled by these).
SCHOOL_GREEN = "#005F39"
SCHOOL_MAROON = "#9E2F3F"
SCHOOL_GREEN_TINT = "#dcebe4"
BACKGROUND = "#ffffff"


def _configure_style(root: tk.Tk) -> None:
    style = ttk.Style(root)
    # "clam" is the ttk theme that reliably honors background/foreground
    # color configuration cross-platform; the native Windows themes ignore
    # most of it.
    style.theme_use("clam")

    root.configure(background=BACKGROUND)
    style.configure(".", background=BACKGROUND)
    style.configure("TFrame", background=BACKGROUND)
    style.configure("TLabel", background=BACKGROUND)
    style.configure("TCheckbutton", background=BACKGROUND)

    style.configure("TButton", background=SCHOOL_GREEN, foreground=BACKGROUND, padding=5)
    style.map(
        "TButton",
        background=[("disabled", "#cccccc"), ("active", SCHOOL_MAROON)],
        foreground=[("disabled", "#888888")],
    )

    style.configure("PaceHeader.TButton", background=SCHOOL_MAROON, foreground=BACKGROUND, padding=3)
    style.map(
        "PaceHeader.TButton",
        background=[("disabled", "#cccccc"), ("active", SCHOOL_GREEN)],
        foreground=[("disabled", "#888888")],
    )

    style.configure("Header.TLabel", background=SCHOOL_GREEN, foreground=BACKGROUND, font=_BOLD, padding=3)
    style.configure(
        "SmallHeader.TLabel",
        background=SCHOOL_GREEN,
        foreground=BACKGROUND,
        font=("TkDefaultFont", 8, "bold"),
        padding=2,
    )

    style.configure("TNotebook", background=BACKGROUND, borderwidth=0)
    style.configure(
        "TNotebook.Tab", background=SCHOOL_GREEN_TINT, foreground=SCHOOL_GREEN, padding=(12, 6), font=_BOLD
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", SCHOOL_MAROON)],
        foreground=[("selected", BACKGROUND)],
    )

    style.configure("TScrollbar", background=SCHOOL_GREEN_TINT, troughcolor=BACKGROUND)


class ScrollableFrame(ttk.Frame):
    """A Frame with vertical + horizontal scrollbars. Put content in
    `.body`, not in the ScrollableFrame itself. Mousewheel scrolling is
    wired up globally by App (see `_on_mousewheel`), not per-instance —
    binding/unbinding on <Enter>/<Leave> is unreliable: those only fire
    on pointer-crossing events, so a tab that appears under an
    already-stationary cursor (e.g. right after startup) never arms it."""

    def __init__(self, master: tk.Widget, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.body = ttk.Frame(self.canvas)

        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def content_overflows_viewport(self) -> bool:
        """False when `.body` fits entirely within the visible canvas area
        — canvas.yview_scroll doesn't clamp to that on its own, so callers
        must skip scrolling themselves to avoid scrolling into blank space."""
        bbox = self.canvas.bbox("all")
        if bbox is None:
            return False
        _, _, _, content_bottom = bbox
        return content_bottom > self.canvas.winfo_height()


class Tooltip:
    """Hover tooltip shown only while its widget is in the ttk "disabled"
    state — used to explain why a button can't be pressed right now."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self._popup: tk.Toplevel | None = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, event: tk.Event) -> None:
        if "disabled" not in self.widget.state():
            return
        self._popup = tk.Toplevel(self.widget)
        self._popup.wm_overrideredirect(True)
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._popup.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._popup,
            text=self.text,
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 8),
            padx=4,
            pady=2,
        ).pack()

    def _on_leave(self, event: tk.Event) -> None:
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        _configure_style(master)
        super().__init__(master)
        self.master = master
        self.state = AppState()
        self._task_queue: queue.Queue = queue.Queue()
        self._pace_vars: dict[PaceKey, tk.BooleanVar] = {}
        self._result_vars: list[tk.BooleanVar] = []

        self.pack(fill="both", expand=True)
        self._build_controls()
        self._build_notebook()
        self.master.bind_all("<MouseWheel>", self._on_mousewheel)
        self.master.after(100, self._poll_queue)

    def _on_mousewheel(self, event: tk.Event) -> None:
        # Route the wheel to whichever tab is currently visible, rather
        # than relying on per-widget Enter/Leave binding (see ScrollableFrame).
        current = self.notebook.nametowidget(self.notebook.select())
        if isinstance(current, ScrollableFrame) and current.content_overflows_viewport():
            current.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # --- top control bar ---------------------------------------------------

    def _build_controls(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)

        self.load_button = ttk.Button(bar, text="Load Data", command=self._on_load_clicked)
        self.load_button.pack(side="left")
        Tooltip(self.load_button, "A load is already in progress.")

        self.status_var = tk.StringVar(value="Not loaded")
        ttk.Label(bar, textvariable=self.status_var).pack(side="left", padx=10)

        self.generate_pdf_button = ttk.Button(bar, text="Generate PDF", command=self._on_generate_pdf)
        self.generate_pdf_button.pack(side="right", padx=4)
        Tooltip(self.generate_pdf_button, "Press Calc first.")

        self.calc_button = ttk.Button(bar, text="Calc", command=self._on_calc)
        self.calc_button.pack(side="right", padx=4)
        Tooltip(self.calc_button, "Load data first.")

        self.select_most_recent_button = ttk.Button(
            bar, text="Select Most Recent", command=self._on_select_most_recent
        )
        self.select_most_recent_button.pack(side="right", padx=4)
        Tooltip(self.select_most_recent_button, "Load data first.")

        self._update_button_states()

    def _update_button_states(self) -> None:
        has_athletes = bool(self.state.athletes)
        has_computed = bool(self.state.computed_paces)
        for button, enabled in (
            (self.calc_button, has_athletes),
            (self.select_most_recent_button, has_athletes),
            (self.generate_pdf_button, has_computed),
        ):
            button.state(["!disabled"] if enabled else ["disabled"])

    # --- notebook / tabs -----------------------------------------------------

    def _build_notebook(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.results_tabs: dict[Gender, ScrollableFrame] = {}
        for gender, label in ((Gender.BOYS, "Boys"), (Gender.GIRLS, "Girls")):
            tab = ScrollableFrame(self.notebook)
            self.notebook.add(tab, text=label)
            self.results_tabs[gender] = tab

        self.paces_tab = ScrollableFrame(self.notebook)
        self.notebook.add(self.paces_tab, text="Paces")
        self._build_paces_grid()

        self.output_tab = ScrollableFrame(self.notebook)
        self.notebook.add(self.output_tab, text="Output")

    # --- paces grid (static: doesn't depend on loaded data) --------------------

    def _build_paces_grid(self) -> None:
        body = self.paces_tab.body
        distances = list(DISPLAY_DISTANCES_KM)

        controls = ttk.Frame(body)
        controls.grid(row=0, column=0, columnspan=len(distances) + 1, sticky="w", pady=(0, 6))
        ttk.Button(controls, text="Select All", command=self._on_select_all_paces).pack(side="left")
        ttk.Button(controls, text="Select None", command=self._on_select_none_paces).pack(side="left", padx=4)

        for col, dist in enumerate(distances, start=1):
            ttk.Button(
                body, text=dist, style="PaceHeader.TButton", command=lambda d=dist: self._on_select_distance(d)
            ).grid(row=1, column=col, padx=1, sticky="ew")

        for row, zone in enumerate(TRAINING_ZONES, start=2):
            ttk.Button(
                body, text=zone, style="PaceHeader.TButton", command=lambda z=zone: self._on_select_zone(z)
            ).grid(row=row, column=0, sticky="ew")
            for col, dist in enumerate(distances, start=1):
                var = tk.BooleanVar(value=(zone, dist) in self.state.enabled_paces)
                self._pace_vars[(zone, dist)] = var
                ttk.Checkbutton(
                    body,
                    variable=var,
                    command=lambda z=zone, d=dist, v=var: self.state.set_pace_enabled(z, d, v.get()),
                ).grid(row=row, column=col)

    def _on_select_all_paces(self) -> None:
        self.state.enable_all_paces()
        for var in self._pace_vars.values():
            var.set(True)

    def _on_select_distance(self, distance: str) -> None:
        """Paces-tab column header click: select every zone at this distance,
        or clear the column if it's already fully selected."""
        self.state.toggle_paces_for_distance(distance)
        for zone in TRAINING_ZONES:
            key = (zone, distance)
            self._pace_vars[key].set(key in self.state.enabled_paces)

    def _on_select_zone(self, zone: str) -> None:
        """Paces-tab row header click: select every distance at this zone,
        or clear the row if it's already fully selected."""
        self.state.toggle_paces_for_zone(zone)
        for dist in DISPLAY_DISTANCES_KM:
            key = (zone, dist)
            self._pace_vars[key].set(key in self.state.enabled_paces)

    def _on_select_none_paces(self) -> None:
        self.state.disable_all_paces()
        for var in self._pace_vars.values():
            var.set(False)

    # --- data loading (background thread) ------------------------------------

    def _on_load_clicked(self) -> None:
        self.load_button.state(["disabled"])
        self.status_var.set("Loading roster...")
        threading.Thread(target=self._load_data_worker, daemon=True).start()

    def _load_data_worker(self) -> None:
        try:
            athletes = fetch_roster()
            self._task_queue.put(("status", f"Loaded {len(athletes)} athletes. Loading schedule..."))

            scheduled_meets = fetch_schedule()
            self._task_queue.put(("status", f"Loaded {len(scheduled_meets)} meets. Loading results..."))

            for index, scheduled in enumerate(scheduled_meets, start=1):
                for gender in (Gender.BOYS, Gender.GIRLS):
                    if scheduled.results_url(gender) is None:
                        continue
                    results = fetch_meet_results(scheduled, gender)
                    attach_results(athletes, results)
                self._task_queue.put(("status", f"Loaded results: meet {index}/{len(scheduled_meets)}..."))

            self._task_queue.put(("loaded", (athletes, scheduled_meets)))
        except Exception as exc:  # surfaced to the user via the queue, not swallowed
            self._task_queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._task_queue.get_nowait()
                if kind == "status":
                    self.status_var.set(payload)
                elif kind == "loaded":
                    athletes, scheduled_meets = payload
                    self.state.athletes = athletes
                    self.state.scheduled_meets = scheduled_meets
                    self.status_var.set(f"Loaded {len(athletes)} athletes, {len(scheduled_meets)} meets.")
                    self.load_button.state(["!disabled"])
                    self._rebuild_results_grids()
                    self._update_button_states()
                elif kind == "error":
                    self.status_var.set("Load failed.")
                    self.load_button.state(["!disabled"])
                    messagebox.showerror("Load failed", payload)
        except queue.Empty:
            pass
        self.master.after(100, self._poll_queue)

    # --- athlete x meet grids (one per gender tab) ------------------------------

    def _rebuild_results_grids(self) -> None:
        self._result_vars.clear()
        for gender, tab in self.results_tabs.items():
            for widget in tab.body.winfo_children():
                widget.destroy()
            self._build_results_grid(tab.body, gender)

    def _build_results_grid(self, body: ttk.Frame, gender: Gender) -> None:
        meets = self.state.meets_with_results_for(gender)
        athletes = self.state.athletes_by_gender(gender)

        ttk.Label(body, text="Athlete", style="Header.TLabel").grid(row=0, column=0, sticky="nsew")
        for col, scheduled in enumerate(meets, start=1):
            ttk.Label(body, text=scheduled.meet.name, style="Header.TLabel", wraplength=100).grid(
                row=0, column=col, padx=1, sticky="nsew"
            )

        for row, athlete in enumerate(athletes, start=1):
            ttk.Label(body, text=athlete.name).grid(row=row, column=0, sticky="w")
            results_by_meet = {result.meet: result for result in athlete.results}
            for col, scheduled in enumerate(meets, start=1):
                result = results_by_meet.get(scheduled.meet)
                if result is None:
                    tk.Label(body, background="#b0b0b0").grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
                    continue
                var = tk.BooleanVar(value=result.selected)
                self._result_vars.append(var)
                ttk.Checkbutton(
                    body,
                    variable=var,
                    command=lambda r=result, v=var: self._on_toggle_result(r, v),
                ).grid(row=row, column=col)

    def _on_toggle_result(self, result: RaceResult, var: tk.BooleanVar) -> None:
        result.selected = var.get()

    def _on_select_most_recent(self) -> None:
        self.state.select_most_recent_all()
        self._rebuild_results_grids()

    # --- calc / output -----------------------------------------------------------

    def _on_calc(self) -> None:
        self.state.calculate()
        self._rebuild_output_grid()
        self._update_button_states()
        self.notebook.select(self.output_tab)

    def _on_generate_pdf(self) -> None:
        if not fits_one_page(self.state):
            proceed = messagebox.askyesno(
                "Wide table",
                "The selected paces won't fit on one page width-wise and will "
                "wrap onto extra pages. Continue anyway?",
                icon="warning",
            )
            if not proceed:
                return

        output_path = filedialog.asksaveasfilename(
            title="Save PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not output_path:
            return

        try:
            generate_pdf(self.state, output_path)
        except Exception as exc:
            messagebox.showerror("Generate PDF failed", str(exc))
            return

        messagebox.showinfo("Generate PDF", f"Saved to {output_path}")

    def _rebuild_output_grid(self) -> None:
        body = self.output_tab.body
        for widget in body.winfo_children():
            widget.destroy()

        pace_keys = self.state.sorted_enabled_paces()

        for gender in (Gender.BOYS, Gender.GIRLS):
            section = ttk.Frame(body)
            section.pack(anchor="w", fill="x", pady=(0, 16))
            self._build_output_table(section, gender, pace_keys)

    def _build_output_table(self, section: ttk.Frame, gender: Gender, pace_keys: list[PaceKey]) -> None:
        ttk.Label(section, text="Athlete", style="Header.TLabel").grid(row=0, column=0, sticky="nsew")
        ttk.Label(section, text="Gender", style="Header.TLabel").grid(row=0, column=1, sticky="nsew")
        for col, (zone, dist) in enumerate(pace_keys, start=2):
            ttk.Label(section, text=f"{zone}\n{dist}", style="SmallHeader.TLabel", justify="center").grid(
                row=0, column=col, padx=1, sticky="nsew"
            )

        entries = sorted(
            (kv for kv in self.state.athletes.items() if kv[1].gender is gender),
            key=lambda kv: kv[1].name,
        )
        for row, (athlete_id, athlete) in enumerate(entries, start=1):
            ttk.Label(section, text=athlete.name).grid(row=row, column=0, sticky="w")
            ttk.Label(section, text=GENDER_LABELS[athlete.gender]).grid(row=row, column=1, sticky="w")
            paces = self.state.computed_paces.get(athlete_id)
            for col, key in enumerate(pace_keys, start=2):
                zone, dist = key
                text = format_minutes(paces[key], decimals=output_decimals_for(dist)) if paces else ""
                ttk.Label(section, text=text).grid(row=row, column=col, padx=4)


def main() -> None:
    root = tk.Tk()
    root.title("PaceChart")
    root.geometry("1100x700")
    if ICON_PATH.exists():
        icon = tk.PhotoImage(file=str(ICON_PATH))
        root.iconphoto(True, icon)
        root._icon_image = icon  # keep a reference alive; PhotoImage has no other owner
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
