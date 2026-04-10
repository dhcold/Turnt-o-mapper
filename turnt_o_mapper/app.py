"""
Main application window (Tkinter GUI).

The ``App`` class builds the full UI: header, left panel with four tabs
(Generate, DBT Import, Textures, Settings), right panel with 2D / 3D
preview and log.  Event handlers delegate to the generation, import, and
preview modules for the actual work.
"""

import os
import random
import subprocess
import threading
import time
from typing import Dict, List, Optional

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

from .constants import (
    ALL_TEXTURES, FLOOR_TEX, WALL_TEX, CEIL_TEX,
    DOOR_H, T, IMG_EXTS,
)
from .models import Room, Bridge
from .config import load_app_cfg, save_app_cfg
from .generation import generate_map
from .viewer3d import Viewer3D
from .preview2d import draw_2d_preview
from . import dbt_import
from .layout import _snap


class App(tk.Tk):
    """Main Turnt-o-mapper application window."""

    def __init__(self):
        super().__init__()
        self.title("Turnt-o-mapper")
        self.configure(bg=T["bg"])
        self.minsize(860, 600)
        self.resizable(True, True)

        self._map_str        = ""
        self._last_map_path  = ""
        self._rooms:   List[Room]   = []
        self._bridges: List[Bridge] = []
        self._is_rbe_import  = False

        app_cfg = load_app_cfg()

        self._tex_folder = tk.StringVar(value=app_cfg.get("tex_folder", ""))
        self._out_path   = tk.StringVar(
            value=app_cfg.get("out_path",
                              os.path.join(os.getcwd(), "generated.map")))
        self._game_exe   = tk.StringVar(value=app_cfg.get("game_exe", ""))
        self._tex_paths: Dict[str, str]    = {}
        self._thumb_refs: Dict[str, object] = {}

        self._floor_sel: Dict[str, tk.BooleanVar] = {}
        self._wall_sel:  Dict[str, tk.BooleanVar] = {}
        self._ceil_sel:  Dict[str, tk.BooleanVar] = {}

        self._build_styles()
        self._build_ui()

        # Restore settings from config
        self._v_rbe_sx.set(app_cfg.get("rbe_sx", 48))
        self._v_rbe_sy.set(app_cfg.get("rbe_sy", 48))
        self._v_rbe_sz.set(app_cfg.get("rbe_sz", 42))
        if app_cfg.get("rbe_path"):
            self._v_rbe_path.set(app_cfg["rbe_path"])
        if "n_rooms" in app_cfg:
            self._v_rooms.set(app_cfg["n_rooms"])
        if "layout" in app_cfg:
            self._v_layout.set(app_cfg["layout"])
        if "corr_frac" in app_cfg:
            self._v_corr_frac.set(app_cfg["corr_frac"])
        if "height_var" in app_cfg:
            self._v_height.set(app_cfg["height_var"])
        if "checkpoints" in app_cfg:
            self._v_checks.set(app_cfg["checkpoints"])
        if "use_physics" in app_cfg:
            self._v_use_physics.set(app_cfg["use_physics"])
        for k, v in self._sz.items():
            cfg_key = f"sz_{k}"
            if cfg_key in app_cfg:
                v.set(app_cfg[cfg_key])
        for attr in ("_v_u_base", "_v_u_gain", "_v_t_air",
                     "_v_strafe_f", "_v_rpt"):
            if attr in app_cfg and hasattr(self, attr):
                getattr(self, attr).set(app_cfg[attr])
        if "prev_labels" in app_cfg:
            self._v_prev_labels.set(app_cfg["prev_labels"])
        if "prev_hmap" in app_cfg:
            self._v_prev_hmap.set(app_cfg["prev_hmap"])
        if "prev_ramps" in app_cfg:
            self._v_prev_ramps.set(app_cfg["prev_ramps"])

        # Auto-save on any variable change (debounced 500 ms)
        self._cfg_save_pending = False
        def _schedule_save(*_):
            if not self._cfg_save_pending:
                self._cfg_save_pending = True
                self.after(500, self._flush_settings)
        tracked = [self._out_path, self._tex_folder, self._game_exe,
                   self._v_rbe_path, self._v_rbe_sx, self._v_rbe_sy,
                   self._v_rbe_sz, self._v_rooms, self._v_layout,
                   self._v_corr_frac, self._v_height, self._v_checks,
                   self._v_use_physics, self._v_prev_labels,
                   self._v_prev_hmap, self._v_prev_ramps]
        tracked.extend(self._sz.values())
        for attr in ("_v_u_base", "_v_u_gain", "_v_t_air",
                     "_v_strafe_f", "_v_rpt"):
            if hasattr(self, attr):
                tracked.append(getattr(self, attr))
        for var in tracked:
            var.trace_add("write", _schedule_save)

        self._randomize_seed(silent=True)
        self._log("Turnt-o-mapper ready. Configure and hit Generate!", "info")

    # ── styles ────────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        bg  = T["bg"];      bgp = T["bg_panel"]; bgc = T["bg_card"]
        acc = T["accent"];  txt = T["text"];      dim = T["text_dim"]
        brd = T["border"]

        s.configure(".",              background=bg,  foreground=txt, font=("Segoe UI", 10))
        s.configure("TFrame",         background=bg)
        s.configure("P.TFrame",       background=bgp)
        s.configure("C.TFrame",       background=bgc)
        s.configure("TLabel",         background=bg,  foreground=txt)
        s.configure("P.TLabel",       background=bgp, foreground=txt)
        s.configure("Pd.TLabel",      background=bgp, foreground=dim)
        s.configure("C.TLabel",       background=bgc, foreground=txt)
        s.configure("H1.TLabel",      background=bg,  foreground=acc, font=("Segoe UI", 22, "bold"))
        s.configure("H2.TLabel",      background=bgp, foreground=acc, font=("Segoe UI", 9, "bold"))
        s.configure("H3.TLabel",      background=bgc, foreground=acc, font=("Segoe UI",  9, "bold"))
        s.configure("TNotebook",      background=bg,  borderwidth=0)
        s.configure("TNotebook.Tab",  background=bgp, foreground=dim, padding=[14, 7], font=("Segoe UI", 9, "bold"))
        s.map("TNotebook.Tab", background=[("selected", bgc)], foreground=[("selected", acc)])
        s.configure("TCheckbutton",   background=bgp, foreground=txt, indicatorcolor=bgc, font=("Segoe UI", 9))
        s.map("TCheckbutton", indicatorcolor=[("selected", acc)])
        s.configure("TScale",         background=bgp, troughcolor=T["bg_input"], sliderthickness=13, sliderrelief="flat")
        s.configure("TEntry",         fieldbackground=T["bg_input"], foreground=txt, insertcolor=txt, bordercolor=brd, relief="flat", padding=5)
        s.configure("TSeparator",     background=brd)
        s.configure("Vertical.TScrollbar",   background=brd, troughcolor=bg, bordercolor=bg, arrowcolor=dim, relief="flat")
        s.configure("Horizontal.TScrollbar", background=brd, troughcolor=bg, bordercolor=bg, arrowcolor=dim, relief="flat")

    # ── master layout ─────────────────────────────────────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self, bg=T["bg_card"])
        hdr.pack(fill="x")
        stripe = tk.Canvas(hdr, height=3, bg=T["bg_card"], highlightthickness=0)
        stripe.pack(fill="x")
        stripe.bind("<Configure>", lambda e: (
            stripe.delete("all"),
            stripe.create_rectangle(0, 0, e.width, 3, fill=T["accent"], outline="")))
        hdr_inner = tk.Frame(hdr, bg=T["bg_card"], pady=10)
        hdr_inner.pack(fill="x", padx=18)
        tk.Label(hdr_inner, text="TURNT", bg=T["bg_card"], fg=T["accent"],
                 font=("Consolas", 18, "bold")).pack(side="left")
        tk.Label(hdr_inner, text="-O-MAPPER", bg=T["bg_card"], fg=T["text"],
                 font=("Consolas", 18, "bold")).pack(side="left")
        tk.Frame(hdr_inner, bg=T["accent"], width=2).pack(side="left", fill="y", padx=14, pady=2)
        tk.Label(hdr_inner, text=".map generator + DBT importer",
                 bg=T["bg_card"], fg=T["text_dim"], font=("Segoe UI", 8)).pack(side="left")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=12, pady=(8, 8))
        body.columnconfigure(0, weight=2, minsize=340)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="P.TFrame", padding=(10, 10))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._build_left(left)

        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        self._build_right(right)

        self._status = tk.Label(self, text="Ready", anchor="w", padx=10,
                                bg=T["bg_panel"], fg=T["text_dim"],
                                font=("Segoe UI", 8))
        self._status.pack(fill="x", side="bottom")

    # ── LEFT PANEL ────────────────────────────────────────────────────────
    def _build_left(self, p):
        nb = ttk.Notebook(p)
        nb.pack(fill="both", expand=True)

        t1 = ttk.Frame(nb, style="P.TFrame", padding=8)
        t2 = ttk.Frame(nb, style="P.TFrame", padding=8)
        t3 = ttk.Frame(nb, style="P.TFrame", padding=8)
        t4 = ttk.Frame(nb, style="P.TFrame", padding=8)
        nb.add(t1, text="  Generate  ")
        nb.add(t2, text="  DBT Import  ")
        nb.add(t3, text="  Textures  ")
        nb.add(t4, text="  Settings  ")

        self._tab_generate(t1)
        self._tab_dbt_import(t2)
        self._tab_textures(t3)
        self._tab_settings(t4)

        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=(6, 4))
        shared_row = ttk.Frame(p, style="P.TFrame")
        shared_row.pack(fill="x", pady=(0, 4))
        shared_row.columnconfigure(0, weight=1)
        shared_row.columnconfigure(1, weight=0)
        shared_row.columnconfigure(2, weight=1)
        BTN_F = ("Segoe UI", 9, "bold")
        self._btn(shared_row, "Save .map", self._on_save,
                  color=T["success"], font=BTN_F).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self._btn(shared_row, "Open folder", self._on_open_folder,
                  color=T["accent2"], font=BTN_F).grid(row=0, column=1, sticky="ew", padx=3)
        self._btn(shared_row, "Launch game", self._on_launch_game,
                  color=T["warning"], font=BTN_F).grid(row=0, column=2, sticky="ew", padx=(3, 0))

    def _tab_generate(self, p):
        self._v_rooms = tk.IntVar(value=10)
        self._slider(p, "Number of rooms", self._v_rooms, 2, 100)

        sr = ttk.Frame(p, style="P.TFrame")
        sr.pack(fill="x", pady=(2, 4))
        self._v_autorand = tk.BooleanVar(value=True)
        self._auto_btn = tk.Button(sr, text="\U0001f3b2 Auto",
            bg=T["accent2"], fg=T["btn_fg"], font=("Segoe UI", 8, "bold"),
            relief="flat", cursor="hand2", padx=6, pady=2, bd=0,
            activebackground=T["lbx_sel"], command=self._toggle_autorand)
        self._auto_btn.pack(side="left")
        self._v_seed = tk.IntVar(value=0)
        self._seed_spin = self._spinbox(sr, self._v_seed, 0, 9_999_999, 1,
                                        state="readonly", pack=False)
        self._seed_spin.pack(side="left", padx=(8, 0), fill="x", expand=True)

        gen_row = ttk.Frame(p, style="P.TFrame")
        gen_row.pack(fill="x", pady=(6, 4))
        self._btn(gen_row, "\u26a1 Generate", self._on_generate,
                  color=T["accent"], font=("Segoe UI", 11, "bold")).pack(
            side="left", fill="x", expand=True, padx=(0, 4))
        self._btn(gen_row, "\U0001f3b2 New seed", self._randomize_seed,
                  color=T["accent2"]).pack(side="left", fill="x", expand=True)

        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=(4, 0))

        q = ttk.Frame(p, style="P.TFrame")
        q.pack(fill="both", expand=True)

        self._sec(q, "Room settings")
        g = ttk.Frame(q, style="P.TFrame")
        g.pack(fill="x", pady=(0, 2))
        labels  = ["Min W", "Max W", "Min D", "Max D", "Min H", "Max H"]
        defvals = [384, 2048, 256, 768, 256, 640]
        self._sz: Dict[str, tk.IntVar] = {}
        for i, (lbl, val) in enumerate(zip(labels, defvals)):
            r, c = divmod(i, 2)
            f = ttk.Frame(g, style="P.TFrame")
            f.grid(row=r, column=c, padx=3, pady=2, sticky="ew")
            g.columnconfigure(c, weight=1)
            ttk.Label(f, text=lbl, style="P.TLabel", font=("Segoe UI", 7)).pack(anchor="w")
            v = tk.IntVar(value=val)
            self._sz[lbl] = v
            self._spinbox(f, v, 64, 4096, 64)
        tk.Label(q, text="Long side = travel axis  |  Short side = lateral sweep",
                 bg=T["bg_panel"], fg=T["text_dim"], font=("Segoe UI", 7)).pack(anchor="w", pady=(0, 2))

        cw_row = ttk.Frame(q, style="P.TFrame")
        cw_row.pack(fill="x", pady=(0, 4))
        ttk.Label(cw_row, text="Corridor width", style="P.TLabel", font=("Segoe UI", 7)).pack(anchor="w")
        self._v_corr_frac = tk.DoubleVar(value=0.67)
        cw_lbl_var = tk.StringVar(value="67%")
        def _update_cw_lbl(*_):
            v = self._v_corr_frac.get()
            cw_lbl_var.set("100% (open)" if v >= 0.98 else f"{int(v*100)}%")
        self._v_corr_frac.trace_add("write", _update_cw_lbl)
        cw_inner = ttk.Frame(cw_row, style="P.TFrame")
        cw_inner.pack(fill="x")
        ttk.Scale(cw_inner, from_=0.25, to=1.0, variable=self._v_corr_frac,
                  orient="horizontal").pack(side="left", fill="x", expand=True)
        ttk.Label(cw_inner, textvariable=cw_lbl_var, style="Pd.TLabel",
                  font=("Segoe UI", 8)).pack(side="left", padx=(4, 0))

        self._v_height = tk.BooleanVar(value=True)
        self._v_checks = tk.BooleanVar(value=True)
        for text, var in [
            ("Height variation between rooms", self._v_height),
            ("Add trigger_checkpoint entities", self._v_checks),
        ]:
            ttk.Checkbutton(q, text=text, variable=var).pack(anchor="w", pady=1)

        ttk.Separator(q, orient="horizontal").pack(fill="x", pady=(6, 2))

        self._sec(q, "Physics")
        self._v_use_physics = tk.BooleanVar(value=False)
        phy_hdr = ttk.Frame(q, style="P.TFrame")
        phy_hdr.pack(fill="x", pady=(0, 4))
        tk.Checkbutton(phy_hdr, text="Use acceleration model",
            variable=self._v_use_physics,
            bg=T["bg_card"], fg=T["text"], selectcolor=T["bg_input"],
            activebackground=T["bg_card"], activeforeground=T["accent"],
            font=("Segoe UI", 8), anchor="w", relief="flat",
            command=self._toggle_physics).pack(side="left")
        pg = ttk.Frame(q, style="P.TFrame")
        pg.pack(fill="x", pady=(0, 4))
        pg.columnconfigure(0, weight=1)
        pg.columnconfigure(1, weight=1)
        phy_params = [
            ("Base speed (UPS)",      "_v_u_base",   550, 100, 2000, 10),
            ("Speed gain / room",     "_v_u_gain",    60,   0,  300,  5),
            ("Air time (\u00d70.01 s)",    "_v_t_air",     68,  30,  150,  1),
            ("Strafe factor (\u00d70.01)", "_v_strafe_f",  20,   5,   40,  1),
            ("Rooms per segment",     "_v_rpt",        3,   1,   10,  1),
        ]
        self._phy_widgets: list = []
        for row_i, (lbl, attr, dflt, lo, hi, inc) in enumerate(phy_params):
            r, c = divmod(row_i, 2)
            f = ttk.Frame(pg, style="P.TFrame")
            f.grid(row=r, column=c, padx=3, pady=2, sticky="ew")
            ttk.Label(f, text=lbl, style="P.TLabel", font=("Segoe UI", 7)).pack(anchor="w")
            v = tk.IntVar(value=dflt)
            setattr(self, attr, v)
            sb = self._spinbox(f, v, lo, hi, inc)
            self._phy_widgets.append(sb)
        self._toggle_physics()

        ttk.Separator(q, orient="horizontal").pack(fill="x", pady=(6, 2))

        self._sec(q, "Layout style")
        self._v_layout = tk.StringVar(value="Zigzag")
        layouts = ["Linear", "Zigzag", "Snake", "Random", "Spiral", "Multilevel"]
        layout_grid = ttk.Frame(q, style="P.TFrame")
        layout_grid.pack(fill="x", pady=(0, 6))
        self._layout_btns: Dict[str, tk.Button] = {}

        def _select_layout(name):
            self._v_layout.set(name)
            for n, btn in self._layout_btns.items():
                btn.config(bg=T["accent"] if n == name else T["bg_card"],
                           fg=T["btn_fg"] if n == name else T["text_dim"],
                           relief="flat")

        for col, name in enumerate(layouts):
            btn = tk.Button(layout_grid, text=name,
                bg=T["accent"] if name == "Zigzag" else T["bg_card"],
                fg=T["btn_fg"] if name == "Zigzag" else T["text_dim"],
                font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
                padx=4, pady=4, activebackground=T["lbx_sel"],
                command=lambda n=name: _select_layout(n))
            btn.grid(row=col // 3, column=col % 3, padx=2, pady=2, sticky="ew")
            layout_grid.columnconfigure(col % 3, weight=1)
            self._layout_btns[name] = btn

    def _tab_textures(self, p):
        tk.Label(p, text="F = use as Floor   W = Wall   C = Ceiling",
                 bg=T["bg_panel"], fg=T["text_dim"], font=("Segoe UI", 7)).pack(anchor="w", pady=(0, 4))

        outer = ttk.Frame(p, style="P.TFrame")
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=0)
        outer.rowconfigure(0, weight=1)

        list_f = ttk.Frame(outer, style="P.TFrame")
        list_f.grid(row=0, column=0, sticky="nsew")
        list_f.rowconfigure(0, weight=1)
        list_f.columnconfigure(0, weight=1)

        self._tex_canvas = tk.Canvas(list_f, bg=T["lbx_bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(list_f, orient="vertical", command=self._tex_canvas.yview)
        self._tex_canvas.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        self._tex_canvas.grid(row=0, column=0, sticky="nsew")

        self._tex_inner = tk.Frame(self._tex_canvas, bg=T["lbx_bg"])
        self._tex_canvas_win = self._tex_canvas.create_window((0, 0), window=self._tex_inner, anchor="nw")

        self._tex_inner.bind("<Configure>",
            lambda e: self._tex_canvas.configure(scrollregion=self._tex_canvas.bbox("all")))
        self._tex_canvas.bind("<Configure>",
            lambda e: self._tex_canvas.itemconfig(self._tex_canvas_win, width=e.width))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._tex_canvas.bind(seq, self._on_tex_scroll)

        prev_f = tk.Frame(outer, bg=T["bg_card"], padx=6, pady=6)
        prev_f.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(prev_f, text="Preview", bg=T["bg_card"], fg=T["accent"],
                 font=("Segoe UI", 9, "bold")).pack()
        self._prev_lbl = tk.Label(prev_f, bg=T["bg_card"], width=16, height=8,
                                  text="\u2014", fg=T["text_dim"], font=("Segoe UI", 8))
        self._prev_lbl.pack(pady=4)
        self._prev_name = tk.Label(prev_f, bg=T["bg_card"], fg=T["text_dim"],
                                   font=("Consolas", 6), wraplength=120, text="")
        self._prev_name.pack()
        self._populate_tex_list()

    def _on_tex_scroll(self, e):
        if e.num == 4:
            self._tex_canvas.yview_scroll(-1, "units")
        elif e.num == 5:
            self._tex_canvas.yview_scroll(1, "units")
        else:
            self._tex_canvas.yview_scroll(-1 * (e.delta // 120), "units")

    def _populate_tex_list(self):
        for w in self._tex_inner.winfo_children():
            w.destroy()
        for tex in ALL_TEXTURES:
            self._floor_sel.setdefault(tex, tk.BooleanVar(value=(tex in FLOOR_TEX)))
            self._wall_sel.setdefault(tex, tk.BooleanVar(value=(tex in WALL_TEX)))
            self._ceil_sel.setdefault(tex, tk.BooleanVar(value=(tex in CEIL_TEX)))
        for tex_name in sorted(ALL_TEXTURES.keys()):
            row = tk.Frame(self._tex_inner, bg=T["lbx_bg"])
            row.pack(fill="x")
            thumb = tk.Label(row, bg=T["lbx_bg"], width=2, height=1, text=" ")
            thumb.pack(side="left")
            self._load_thumb(tex_name, thumb, size=16)
            name_btn = tk.Button(row, text=tex_name, bg=T["lbx_bg"], fg=T["text"],
                font=("Consolas", 7), relief="flat", anchor="w", cursor="hand2",
                activebackground=T["lbx_sel"], activeforeground=T["accent"],
                command=lambda t=tex_name: self._show_tex_preview(t))
            name_btn.pack(side="left", fill="x", expand=True)
            for label, color, sel_dict in [
                ("F", T["success"], self._floor_sel),
                ("W", T["accent2"], self._wall_sel),
                ("C", T["accent"],  self._ceil_sel),
            ]:
                ck = tk.Checkbutton(row, text=label, variable=sel_dict[tex_name],
                    bg=T["lbx_bg"], fg=color, selectcolor=T["bg_card"],
                    activebackground=T["lbx_bg"], font=("Segoe UI", 7),
                    relief="flat", cursor="hand2", command=self._update_tex_lists)
                ck.pack(side="left")

    def _load_thumb(self, tex_name, lbl, size=16):
        if not PIL_OK:
            return
        path = self._tex_paths.get(tex_name) or self._find_tex_file(tex_name)
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((size, size))
            tk_img = ImageTk.PhotoImage(img)
            lbl.config(image=tk_img, text="", width=size)
            self._thumb_refs[f"{tex_name}_{size}"] = tk_img
        except Exception:
            pass

    def _find_tex_file(self, tex_name) -> Optional[str]:
        folder = self._tex_folder.get()
        if not folder or not os.path.isdir(folder):
            return None
        base = tex_name.split("/")[-1]
        for root_d, _, files in os.walk(folder):
            for fn in files:
                nm, ext = os.path.splitext(fn)
                if nm.lower() == base.lower() and ext.lower() in IMG_EXTS:
                    fp = os.path.join(root_d, fn)
                    self._tex_paths[tex_name] = fp
                    return fp
        return None

    def _show_tex_preview(self, tex_name):
        self._prev_name.config(text=tex_name)
        if not PIL_OK:
            self._prev_lbl.config(image="", text="pip install pillow", fg=T["warning"])
            return
        path = self._tex_paths.get(tex_name) or self._find_tex_file(tex_name)
        if not path:
            self._prev_lbl.config(image="", text="No image\n(set folder)", fg=T["text_dim"])
            return
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((128, 128))
            tk_img = ImageTk.PhotoImage(img)
            self._prev_lbl.config(image=tk_img, text="", width=128, height=128)
            self._thumb_refs["preview"] = tk_img
        except Exception as ex:
            self._prev_lbl.config(image="", text=f"Error:\n{ex}", fg=T["warning"])

    def _browse_tex_folder(self):
        d = filedialog.askdirectory(title="Select texture folder")
        if d:
            self._tex_folder.set(d)
            self._tex_paths.clear()
            self._status.config(text="Scanning texture folder\u2026")
            threading.Thread(target=self._scan_tex_folder, args=(d,), daemon=True).start()

    def _scan_tex_folder(self, folder):
        found = {}
        for root_d, _, files in os.walk(folder):
            for fn in files:
                nm, ext = os.path.splitext(fn)
                if ext.lower() not in IMG_EXTS:
                    continue
                for tex in ALL_TEXTURES:
                    base = tex.split("/")[-1]
                    if nm.lower() == base.lower():
                        found[tex] = os.path.join(root_d, fn)
        self._tex_paths.update(found)
        self.after(0, lambda: self._status.config(text=f"Scan complete \u2014 {len(found)} textures matched"))
        self.after(0, self._refresh_thumbs)

    def _refresh_thumbs(self):
        if not PIL_OK:
            return
        for row in self._tex_inner.winfo_children():
            ch = row.winfo_children()
            if len(ch) < 2:
                continue
            thumb_lbl = ch[0]
            name_btn  = ch[1]
            tex_name  = name_btn.cget("text")
            if tex_name in ALL_TEXTURES:
                self._load_thumb(tex_name, thumb_lbl, size=16)

    def _update_tex_lists(self):
        FLOOR_TEX.clear()
        FLOOR_TEX.extend([t for t, v in self._floor_sel.items() if v.get()])
        WALL_TEX.clear()
        WALL_TEX.extend([t for t, v in self._wall_sel.items()  if v.get()])
        CEIL_TEX.clear()
        CEIL_TEX.extend([t for t, v in self._ceil_sel.items()  if v.get()])
        if not FLOOR_TEX: FLOOR_TEX.append("turnt/turnt_concrete")
        if not WALL_TEX:  WALL_TEX.append("turnt/turnt_tech")
        if not CEIL_TEX:  CEIL_TEX.append("turnt/turnt_sky")

    def _tab_settings(self, p):
        def _path_row(parent, label, var, browse_cmd):
            self._sec(parent, label)
            row = ttk.Frame(parent, style="P.TFrame")
            row.pack(fill="x", pady=(0, 8))
            ttk.Entry(row, textvariable=var, font=("Consolas", 8)).pack(side="left", fill="x", expand=True)
            self._btn(row, "\u2026", browse_cmd, w=4, color=T["accent2"]).pack(side="left", padx=(6, 0))

        _path_row(p, "Output .map file", self._out_path, self._browse_out)
        _path_row(p, "Texture folder (for preview)", self._tex_folder, self._browse_tex_folder)
        _path_row(p, "Game executable", self._game_exe, self._browse_game_exe)

        self._sec(p, "Preview")
        self._v_prev_labels = tk.BooleanVar(value=True)
        self._v_prev_hmap   = tk.BooleanVar(value=True)
        self._v_prev_ramps  = tk.BooleanVar(value=True)
        for text, var in [
            ("Show room numbers", self._v_prev_labels),
            ("Show heightmap bar", self._v_prev_hmap),
            ("Show ramps in 3D preview", self._v_prev_ramps),
        ]:
            ttk.Checkbutton(p, text=text, variable=var).pack(anchor="w", pady=1)

    def _tab_dbt_import(self, p):
        self._sec(p, "Source .rbe file")
        file_row = ttk.Frame(p, style="P.TFrame")
        file_row.pack(fill="x", pady=(0, 8))
        self._v_rbe_path = tk.StringVar(value="")
        ttk.Entry(file_row, textvariable=self._v_rbe_path,
                  font=("Consolas", 8)).pack(side="left", fill="x", expand=True)
        def _browse_rbe():
            path_ = filedialog.askopenfilename(
                title="Open Diabotical map",
                filetypes=[("Diabotical Map", "*.rbe"), ("All files", "*.*")])
            if path_:
                self._v_rbe_path.set(path_)
        self._btn(file_row, "\u2026", _browse_rbe, w=4, color=T["accent2"]).pack(side="left", padx=(6, 0))

        self._sec(p, "Scale (Quake units per block)")
        sc_row = ttk.Frame(p, style="P.TFrame")
        sc_row.pack(fill="x", pady=(0, 8))
        self._v_rbe_sx = tk.IntVar(value=48)
        self._v_rbe_sy = tk.IntVar(value=48)
        self._v_rbe_sz = tk.IntVar(value=42)
        for lbl, var in [("X:", self._v_rbe_sx), ("Y:", self._v_rbe_sy),
                          ("Z (height):", self._v_rbe_sz)]:
            ttk.Label(sc_row, text=lbl, style="P.TLabel").pack(side="left")
            self._spinbox(sc_row, var, 1, 512, 1, pack=False).pack(side="left", padx=(2, 12))

        self._sec(p, "Actions")
        self._btn(p, "Import & Convert", self._on_import_rbe,
                  color=T["accent"], font=("Segoe UI", 11, "bold")).pack(fill="x", pady=(0, 8))

    # ── RIGHT PANEL ───────────────────────────────────────────────────────
    def _build_right(self, p):
        pc = ttk.Frame(p, style="P.TFrame")
        pc.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        pc.rowconfigure(2, weight=1)
        pc.columnconfigure(0, weight=1)

        ph = ttk.Frame(pc, style="P.TFrame", padding=(10, 4))
        ph.grid(row=0, column=0, sticky="ew")
        ttk.Label(ph, text="MAP PREVIEW", style="H2.TLabel").pack(side="left")
        self._lbl_stats = ttk.Label(ph, text="", style="Pd.TLabel", font=("Segoe UI", 8))
        self._lbl_stats.pack(side="right")

        leg = tk.Frame(pc, bg=T["bg_panel"], padx=10, pady=2)
        leg.grid(row=1, column=0, sticky="ew")
        for color, label in [
            (T["start_col"], "Start"), (T["room_col"], "Room"),
            (T["end_col"], "End"),     (T["corr_col"], "Corridor"),
        ]:
            tk.Label(leg, bg=color, width=2, relief="flat").pack(side="left")
            tk.Label(leg, text=f" {label}   ", bg=T["bg_panel"], fg=T["text_dim"],
                     font=("Segoe UI", 7)).pack(side="left")

        view_nb = ttk.Notebook(pc)
        view_nb.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))

        tab2d = ttk.Frame(view_nb, style="P.TFrame")
        view_nb.add(tab2d, text="  2D  ")
        tab2d.rowconfigure(1, weight=1)
        tab2d.columnconfigure(0, weight=1)

        bar2d = ttk.Frame(tab2d, style="P.TFrame", padding=(4, 2))
        bar2d.grid(row=0, column=0, sticky="ew")
        self._btn(bar2d, "Fit", self._2d_fit, color=T["accent2"],
                  font=("Segoe UI", 8, "bold"), pady=2).pack(side="left", padx=2)
        tk.Label(bar2d, text="  scroll=zoom  drag=pan  dbl-click=fit",
                 bg=T["bg_panel"], fg=T["text_dim"], font=("Segoe UI", 7)).pack(side="left", padx=6)

        self._canvas = tk.Canvas(tab2d, bg=T["prev_bg"], highlightthickness=0)
        self._canvas.grid(row=1, column=0, sticky="nsew")
        self._canvas.bind("<Configure>",       lambda e: self._redraw())
        self._canvas.bind("<MouseWheel>",      self._2d_on_scroll)
        self._canvas.bind("<Button-4>",        self._2d_on_scroll)
        self._canvas.bind("<Button-5>",        self._2d_on_scroll)
        self._canvas.bind("<ButtonPress-1>",   self._2d_pan_start)
        self._canvas.bind("<B1-Motion>",       self._2d_pan_move)
        self._canvas.bind("<Double-Button-1>", lambda e: self._2d_fit())
        self._2d_zoom  = 1.0
        self._2d_pan_x = 0.0
        self._2d_pan_y = 0.0
        self._2d_drag_x = 0
        self._2d_drag_y = 0

        tab3d = ttk.Frame(view_nb, style="P.TFrame")
        view_nb.add(tab3d, text="  3D  ")
        tab3d.rowconfigure(1, weight=1)
        tab3d.columnconfigure(0, weight=1)

        btn_bar = ttk.Frame(tab3d, style="P.TFrame", padding=(4, 3))
        btn_bar.grid(row=0, column=0, sticky="ew")
        self._viewer3d = Viewer3D(tab3d)
        self._viewer3d.grid(row=1, column=0, sticky="nsew")

        for preset_name in ("Iso", "Top", "Front", "Side"):
            self._btn(btn_bar, preset_name,
                      lambda n=preset_name: self._viewer3d.set_preset(n),
                      color=T["accent2"], font=("Segoe UI", 8, "bold"), pady=2).pack(side="left", padx=2)
        tk.Label(btn_bar, text="  drag=rotate  scroll=zoom  WASD=pan (click 3D first)",
                 bg=T["bg_panel"], fg=T["text_dim"], font=("Segoe UI", 7)).pack(side="left", padx=6)

        view_nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_change(view_nb))
        self._view_nb = view_nb

        lc = ttk.Frame(p, style="P.TFrame")
        lc.grid(row=1, column=0, sticky="nsew")
        lc.rowconfigure(1, weight=1)
        lc.columnconfigure(0, weight=1)

        lh = ttk.Frame(lc, style="P.TFrame", padding=(10, 5))
        lh.grid(row=0, column=0, sticky="ew")
        ttk.Label(lh, text="LOG", style="H2.TLabel").pack(side="left")
        self._btn(lh, "Clear", self._clear_log, color=T["accent2"],
                  font=("Segoe UI", 8), pady=2).pack(side="right")

        self._logbox = scrolledtext.ScrolledText(lc, height=7,
            bg=T["bg_input"], fg=T["text_dim"], font=("Consolas", 9),
            relief="flat", insertbackground=T["text"], wrap="word",
            state="disabled", borderwidth=0)
        self._logbox.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._logbox.tag_config("info",  foreground=T["success"])
        self._logbox.tag_config("warn",  foreground=T["warning"])
        self._logbox.tag_config("error", foreground=T["accent"])

    def _on_tab_change(self, nb):
        try:
            if nb.tab(nb.select(), "text").strip() == "3D" and self._rooms:
                self._viewer3d.load(
                    self._rooms, self._bridges,
                    show_labels=(self._v_prev_labels.get() and not self._is_rbe_import))
        except Exception:
            pass

    # ── 2D zoom/pan ───────────────────────────────────────────────────────
    def _2d_on_scroll(self, e):
        if e.num == 4 or e.delta > 0:
            factor = 1.15
        else:
            factor = 1.0 / 1.15
        self._2d_zoom = max(0.05, min(self._2d_zoom * factor, 80.0))
        self._redraw()

    def _2d_pan_start(self, e):
        self._2d_drag_x = e.x
        self._2d_drag_y = e.y

    def _2d_pan_move(self, e):
        dx = e.x - self._2d_drag_x
        dy = e.y - self._2d_drag_y
        self._2d_pan_x += dx
        self._2d_pan_y += dy
        self._2d_drag_x = e.x
        self._2d_drag_y = e.y
        self._redraw()

    def _2d_fit(self):
        self._2d_zoom  = 1.0
        self._2d_pan_x = 0.0
        self._2d_pan_y = 0.0
        self._redraw()

    # ── UI helpers ────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, color=None, font=None, w=None, pady=4):
        color = color or T["accent"]
        font  = font  or ("Segoe UI", 9, "bold")
        kw = dict(text=text, command=cmd, bg=color, fg=T["btn_fg"],
                  activebackground=color, activeforeground=T["btn_fg"],
                  relief="flat", cursor="hand2", font=font, padx=10, pady=pady, bd=0)
        if w:
            kw["width"] = w
        b = tk.Button(parent, **kw)
        lit = self._lighten(color, .18)
        b.bind("<Enter>", lambda e: b.config(bg=lit))
        b.bind("<Leave>", lambda e: b.config(bg=color))
        return b

    @staticmethod
    def _lighten(hx, f):
        hx = hx.lstrip("#")
        r, g, b = (int(hx[i:i+2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(
            min(255, int(r + (255 - r) * f)),
            min(255, int(g + (255 - g) * f)),
            min(255, int(b + (255 - b) * f)))

    def _sec(self, p, text):
        f = ttk.Frame(p, style="P.TFrame")
        f.pack(fill="x", pady=(8, 3))
        ttk.Label(f, text=text, style="H2.TLabel").pack(side="left")
        ttk.Separator(f, orient="horizontal").pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _slider(self, p, label, var, lo, hi, step=1):
        row = ttk.Frame(p, style="P.TFrame")
        row.pack(fill="x", pady=(0, 2))
        ttk.Label(row, text=label, style="P.TLabel", font=("Segoe UI", 9)).pack(side="left")
        vl = ttk.Label(row, text=str(var.get()), style="P.TLabel",
                       foreground=T["accent"], font=("Consolas", 9, "bold"))
        vl.pack(side="right")
        def ch(v):
            sv = round(float(v) / step) * step
            var.set(int(sv))
            vl.config(text=str(sv))
        ttk.Scale(p, from_=lo, to=hi, variable=var,
                  orient="horizontal", command=ch).pack(fill="x", pady=(0, 8))

    def _spinbox(self, parent, var, lo, hi, inc, state="normal", pack=True):
        sb = tk.Spinbox(parent, textvariable=var,
            from_=lo, to=hi, increment=inc, width=8,
            bg=T["bg_input"], fg=T["text"], insertbackground=T["text"],
            relief="flat", font=("Consolas", 9), buttonbackground=T["bg_card"],
            state=state, disabledforeground=T["text_dim"],
            disabledbackground=T["bg_input"])
        if pack:
            sb.pack(fill="x")
        return sb

    def _toggle_physics(self):
        st = "normal" if self._v_use_physics.get() else "disabled"
        for sb in self._phy_widgets:
            sb.config(state=st)

    def _toggle_autorand(self):
        self._v_autorand.set(not self._v_autorand.get())
        is_auto = self._v_autorand.get()
        self._auto_btn.config(bg=T["accent2"] if is_auto else T["bg_card"])
        self._seed_spin.config(state="readonly" if is_auto else "normal")

    def _randomize_seed(self, silent=False):
        if not self._v_autorand.get():
            return
        s = random.randint(0, 9_999_999)
        self._v_seed.set(s)
        if not silent:
            self._log(f"Seed \u2192 {s}", "info")

    def _browse_out(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".map",
            filetypes=[("Quake Map", "*.map"), ("All", "*.*")],
            initialfile=os.path.basename(self._out_path.get()))
        if p:
            self._out_path.set(p)

    def _flush_settings(self):
        self._cfg_save_pending = False
        d = {
            "out_path": self._out_path.get(), "tex_folder": self._tex_folder.get(),
            "game_exe": self._game_exe.get(), "rbe_path": self._v_rbe_path.get(),
            "rbe_sx": self._v_rbe_sx.get(), "rbe_sy": self._v_rbe_sy.get(),
            "rbe_sz": self._v_rbe_sz.get(), "n_rooms": self._v_rooms.get(),
            "layout": self._v_layout.get(), "corr_frac": self._v_corr_frac.get(),
            "height_var": self._v_height.get(), "checkpoints": self._v_checks.get(),
            "use_physics": self._v_use_physics.get(),
            "prev_labels": self._v_prev_labels.get(),
            "prev_hmap": self._v_prev_hmap.get(), "prev_ramps": self._v_prev_ramps.get(),
        }
        for k, v in self._sz.items():
            d[f"sz_{k}"] = v.get()
        for attr in ("_v_u_base", "_v_u_gain", "_v_t_air", "_v_strafe_f", "_v_rpt"):
            if hasattr(self, attr):
                d[attr] = getattr(self, attr).get()
        save_app_cfg(d)

    def _browse_game_exe(self):
        p = filedialog.askopenfilename(
            title="Select game executable",
            filetypes=[("Executable", "*.exe *.sh *.app"), ("All", "*.*")])
        if p:
            self._game_exe.set(p)

    def _on_launch_game(self):
        exe  = self._game_exe.get().strip()
        path = self._last_map_path or self._out_path.get()
        if not exe:
            self._log("Set the game executable path first.", "warn")
            return
        if not path or not os.path.isfile(path):
            self._log("Save a map first (or generate + auto-save).", "warn")
            return
        try:
            cmd = [exe, "--", f"--import={path}"]
            subprocess.Popen(cmd)
            self._log(f"Launched: {' '.join(cmd)}", "info")
        except Exception as ex:
            self._log(f"Launch failed: {ex}", "error")

    def _log(self, msg, level="plain"):
        self._logbox.config(state="normal")
        pfx = {"info": "[OK] ", "warn": "[!!] ", "error": "[ERR] "}.get(level, "")
        self._logbox.insert("end", pfx + msg + "\n", level)
        self._logbox.see("end")
        self._logbox.config(state="disabled")
        self._status.config(text=msg)

    def _clear_log(self):
        self._logbox.config(state="normal")
        self._logbox.delete("1.0", "end")
        self._logbox.config(state="disabled")

    # ── Generation ────────────────────────────────────────────────────────
    def _collect_cfg(self) -> dict:
        self._update_tex_lists()
        return {
            "n_rooms":      self._v_rooms.get(),
            "min_w": self._sz["Min W"].get(), "max_w": self._sz["Max W"].get(),
            "min_d": self._sz["Min D"].get(), "max_d": self._sz["Max D"].get(),
            "min_h": self._sz["Min H"].get(), "max_h": self._sz["Max H"].get(),
            "use_physics":  self._v_use_physics.get(),
            "u_base":       float(self._v_u_base.get()),
            "u_gain":       float(self._v_u_gain.get()),
            "t_air":        self._v_t_air.get() / 100.0,
            "strafe_f":     self._v_strafe_f.get() / 100.0,
            "rooms_per_turn": self._v_rpt.get(),
            "layout_style":   self._v_layout.get(),
            "seed":         self._v_seed.get(),
            "map_name":     "turnt_map",
            "height_var":   self._v_height.get(),
            "checkpoints":  self._v_checks.get(),
            "corridor_width_frac": self._v_corr_frac.get(),
        }

    def _on_generate(self):
        def run():
            try:
                cfg = self._collect_cfg()
                errs = []
                if cfg["min_w"] >= cfg["max_w"]: errs.append("Min W must be < Max W")
                if cfg["min_d"] >= cfg["max_d"]: errs.append("Min D must be < Max D")
                if cfg["min_h"] >= cfg["max_h"]: errs.append("Min H must be < Max H")
                if errs:
                    for e in errs: self._log(e, "warn")
                    return

                u_end = cfg["u_base"] + (cfg["n_rooms"] - 1) * cfg["u_gain"]
                self._log(
                    f"Generating {cfg['n_rooms']} rooms | "
                    f"u: {cfg['u_base']:.0f}\u2192{u_end:.0f} UPS | "
                    f"layout: {cfg['layout_style']} | seed {cfg['seed']}\u2026", "info")
                t0 = time.perf_counter()
                ms, rooms, bridges, gen_warnings = generate_map(cfg)
                dt = time.perf_counter() - t0

                self._map_str = ms
                self._rooms   = rooms
                self._bridges = bridges
                self._is_rbe_import = False

                nb = len(rooms) * 6 + len(bridges) * 4
                kb = len(ms.encode()) / 1024
                self._log(
                    f"Done in {dt:.2f}s \u2014 {len(rooms)} rooms, "
                    f"{len(bridges)} bridges, ~{nb} brushes, {kb:.1f} KB", "info")
                for w in gen_warnings:
                    self._log(w, "warn")
                self._lbl_stats.config(
                    text=f"rooms={len(rooms)}  bridges={len(bridges)}"
                         f"  brushes\u2248{nb}  {kb:.1f} KB")

                self.after(0, self._redraw)
                self.after(0, lambda: self._viewer3d.load(self._rooms, self._bridges))

                if self._v_autorand.get():
                    self.after(200, self._randomize_seed)

            except Exception as ex:
                import traceback; traceback.print_exc()
                self._log(f"Error: {ex}", "error")

        threading.Thread(target=run, daemon=True).start()

    def _on_import_rbe(self):
        def run():
            path = self._v_rbe_path.get().strip()
            if not path:
                self._log("No file selected.", "error")
                return
            sx = self._v_rbe_sx.get()
            sy = self._v_rbe_sy.get()
            sz = self._v_rbe_sz.get()
            try:
                ms, fake_rooms, _ = dbt_import.run_import(
                    path, sx, sy, sz, log_fn=self._log)
                self._map_str = ms
                self._rooms   = fake_rooms
                self._bridges = []
                self._is_rbe_import = True
                self.after(0, self._redraw)
                self.after(0, lambda r=fake_rooms:
                           self._viewer3d.load(r, [], show_labels=False))
            except Exception as ex:
                import traceback; traceback.print_exc()
                self._log(f"Error: {ex}", "error")

        threading.Thread(target=run, daemon=True).start()

    def _on_save(self):
        if not self._map_str:
            self._log("Nothing to save \u2014 generate or import first.", "warn")
            return
        self._do_save(manual=True)

    def _on_open_folder(self):
        folder = os.path.dirname(os.path.abspath(self._out_path.get()))
        try:
            if os.name == 'nt':
                os.startfile(folder)
            else:
                subprocess.run(['xdg-open', folder])
        except Exception as ex:
            self._log(f"Cannot open folder: {ex}", "error")

    def _do_save(self, manual=False):
        path = self._out_path.get()
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._map_str)
            self._last_map_path = path
            self._log(f"{'Saved' if manual else 'Auto-saved'}: {path}", "info")
        except Exception as e:
            self._log(f"Save error: {e}", "error")

    # ── 2D Preview ────────────────────────────────────────────────────────
    def _redraw(self):
        draw_2d_preview(
            self._canvas, self._rooms, self._bridges,
            zoom=self._2d_zoom,
            pan_x=self._2d_pan_x,
            pan_y=self._2d_pan_y,
            is_rbe_import=self._is_rbe_import,
            use_physics=self._v_use_physics.get(),
            show_labels=self._v_prev_labels.get(),
            show_hmap=self._v_prev_hmap.get(),
        )
