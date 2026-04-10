"""
Shared constants used across all Turnt-o-mapper modules.

Contains:
- Texture registry and category lists (floor, wall, ceiling, special)
- Map geometry parameters (wall thickness, door dimensions)
- Ramp physics constants (slope ratio, max angle)
- UI theme colour palette
- Image file extensions for texture thumbnail loading
"""

import math
from typing import Dict

# ══════════════════════════════════════════════════════════════════════════════
#  TEXTURES
# ══════════════════════════════════════════════════════════════════════════════
ALL_TEXTURES: Dict[str, int] = {
    "NULL":2,"common/caulk":2,"common/lavacaulk":4,"common/nodraw":2,
    "common/nodrawnonsolid":2,"common/slick":5,"common/slimecaulk":4,
    "common/watercaulk":3,"common/weapclip":2,"common/playerclip":2,
    "turnt/temp_blue":8,"turnt/temp_dark":0,"turnt/temp_green":7,
    "turnt/temp_light":1,"turnt/temp_orange":9,"turnt/temp_purple":10,
    "turnt/temp_red":6,"turnt/temp_yellow":11,
    "turnt/turnt_asphalt":12,"turnt/turnt_asphalt_t2":30,
    "turnt/turnt_boost":13,"turnt/turnt_boost_2":31,
    "turnt/turnt_checkpoint":14,"turnt/turnt_checkpoint_2":32,
    "turnt/turnt_concrete":15,"turnt/turnt_concrete_2":33,
    "turnt/turnt_coral":16,"turnt/turnt_coral_t2":34,
    "turnt/turnt_cyan":17,"turnt/turnt_cyan_t2":17,
    "turnt/turnt_gold":18,"turnt/turnt_gold_t2":36,
    "turnt/turnt_hazard":19,"turnt/turnt_hazard_2t":37,
    "turnt/turnt_lime":20,"turnt/turnt_lime_t2":38,
    "turnt/turnt_magenta":21,"turnt/turnt_magenta_t2":39,
    "turnt/turnt_mint":22,"turnt/turnt_mint_t2":40,
    "turnt/turnt_orange":9,"turnt/turnt_orange_2t":41,
    "turnt/turnt_platform":23,"turnt/turnt_platform_2t":42,
    "turnt/turnt_sky":24,"turnt/turnt_sky_2t":43,
    "turnt/turnt_speed":25,"turnt/turnt_speed_2t":44,
    "turnt/turnt_teal":26,"turnt/turnt_teal_2t":45,
    "turnt/turnt_tech":27,"turnt/turnt_tech_2t":46,
    "turnt/turnt_violet":28,"turnt/turnt_violet_2t":47,
    "turnt/turnt_white":29,"turnt/turnt_white_2t":48,
}

# Mutable texture category lists — the UI mutates these in place via
# _update_tex_lists(); other modules (layout, generation) import the same
# list objects and see the updated selections automatically.
FLOOR_TEX = ["turnt/turnt_concrete", "turnt/turnt_asphalt",
             "turnt/turnt_platform", "turnt/turnt_tech", "turnt/turnt_teal"]
WALL_TEX  = ["turnt/turnt_concrete", "turnt/turnt_tech", "turnt/turnt_white",
             "turnt/turnt_cyan", "turnt/turnt_mint", "turnt/turnt_violet"]
CEIL_TEX  = ["turnt/turnt_sky", "turnt/turnt_white", "turnt/turnt_tech"]

HIDDEN_TEX  = "common/caulk"
NODRAW_TEX  = "common/nodrawnonsolid"
TRIGGER_TEX = "common/trigger"

# ══════════════════════════════════════════════════════════════════════════════
#  MAP GEOMETRY PARAMETERS
# ══════════════════════════════════════════════════════════════════════════════
WALL_T = 16   # wall / shell thickness in Quake units
DOOR_W = 128  # default door width
DOOR_H = 128  # default door height

# ══════════════════════════════════════════════════════════════════════════════
#  RAMP PHYSICS CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
SLOPE_RATIO    = 4.0   # horizontal / vertical ~= 14deg -- ideal shallow slope
MAX_RAMP_ANGLE = 30    # degrees -- steepest allowed ramp
# Minimum slope ratio that keeps angle <= MAX_RAMP_ANGLE: 1/tan(30deg) ~= 1.732
MIN_SLOPE_RATIO = 1.0 / math.tan(math.radians(MAX_RAMP_ANGLE))

# ══════════════════════════════════════════════════════════════════════════════
#  THEME PALETTES
#  T is the *live* mutable dict; clear + update it in-place to switch themes.
#  All modules that `from .constants import T` see the updated values.
# ══════════════════════════════════════════════════════════════════════════════

DARK_T = {
    # Backgrounds
    "bg":              "#0c0e1a",
    "bg_panel":        "#12162a",
    "bg_card":         "#1a1f38",
    "bg_input":        "#0e1224",
    # Accent
    "accent":          "#4fc3f7",
    "accent2":         "#9575cd",
    "accent_bright":   "#80d8ff",
    "accent_press":    "#0369a1",
    # Text
    "text":            "#e8eaf6",
    "text_dim":        "#78849e",
    "selection_fg":    "#000000",
    # Status
    "success":         "#66bb6a",
    "warning":         "#ffa726",
    # Borders / separators
    "border":          "#2a3050",
    "card_border":     "#1e2540",
    "sec_sep":         "#1e2540",
    "disabled_border": "#161a2e",
    # Standard buttons
    "btn_fg":          "#ffffff",
    "btn_bg":          "#1e2540",
    "btn_border":      "#2a3050",
    "btn_hover":       "#263060",
    "spin_btn_bg":     "#1e2540",
    # Tab / scrollbar
    "tab_hover":       "#1a1f38",
    "scrollbar_h":     "#2a3050",
    # Coloured action buttons
    "save_bg":         "#2e5c30",
    "save_border":     "#3a7a3c",
    "save_hover":      "#3a7a3c",
    "folder_bg":       "#3a2060",
    "folder_border":   "#5a3090",
    "folder_hover":    "#5a3090",
    "launch_bg":       "#5c3800",
    "launch_border":   "#8c5800",
    "launch_hover":    "#8c5800",
    # Auto (seed) button active state
    "auto_bg":         "#3a206a",
    "auto_text":       "#c4b5fd",
    "auto_border":     "#9575cd",
    # Generate / layout button gradient
    "gen_grad_l":      "#1a7fb5",
    "gen_grad_r":      "#0ea5e9",
    "gen_grad_rh":     "#38bdf8",
    # Update banner
    "update_bg":       "#1b3a2a",
    # Preview widget colours (used by QPainter in preview2d / viewer3d)
    "prev_bg":         "#0b0f1e",
    "room_col":        "#1a3358",
    "room_bdr":        "#4fc3f7",
    "corr_col":        "#162238",
    "start_col":       "#1b5e20",
    "end_col":         "#b71c1c",
    "lbx_bg":          "#0e1224",
    "lbx_sel":         "#263850",
    "dot_grid":        "#182236",
}

LIGHT_T = {
    # Backgrounds
    "bg":              "#f0f4fb",
    "bg_panel":        "#e6ecf7",
    "bg_card":         "#ffffff",
    "bg_input":        "#dde6f6",
    # Accent
    "accent":          "#0284c7",
    "accent2":         "#7c3aed",
    "accent_bright":   "#38bdf8",
    "accent_press":    "#075985",
    # Text
    "text":            "#0f172a",
    "text_dim":        "#64748b",
    "selection_fg":    "#ffffff",
    # Status
    "success":         "#16a34a",
    "warning":         "#d97706",
    # Borders / separators
    "border":          "#b8cae0",
    "card_border":     "#c8d8f0",
    "sec_sep":         "#c0cce0",
    "disabled_border": "#d8e4f4",
    # Standard buttons
    "btn_fg":          "#0f172a",
    "btn_bg":          "#dde6f6",
    "btn_border":      "#b8cae0",
    "btn_hover":       "#c8d8f0",
    "spin_btn_bg":     "#c8d8f0",
    # Tab / scrollbar
    "tab_hover":       "#edf2ff",
    "scrollbar_h":     "#a8bad0",
    # Coloured action buttons
    "save_bg":         "#15803d",
    "save_border":     "#166534",
    "save_hover":      "#166534",
    "folder_bg":       "#6d28d9",
    "folder_border":   "#5b21b6",
    "folder_hover":    "#5b21b6",
    "launch_bg":       "#b45309",
    "launch_border":   "#92400e",
    "launch_hover":    "#92400e",
    # Auto (seed) button active state
    "auto_bg":         "#ede9fe",
    "auto_text":       "#6d28d9",
    "auto_border":     "#7c3aed",
    # Generate / layout button gradient (same blue works on both themes)
    "gen_grad_l":      "#1a7fb5",
    "gen_grad_r":      "#0ea5e9",
    "gen_grad_rh":     "#38bdf8",
    # Update banner
    "update_bg":       "#f0fdf4",
    # Preview widget colours
    "prev_bg":         "#dde6f6",
    "room_col":        "#bfdbfe",
    "room_bdr":        "#1d4ed8",
    "corr_col":        "#dbeafe",
    "start_col":       "#bbf7d0",
    "end_col":         "#fecaca",
    "lbx_bg":          "#eef3fc",
    "lbx_sel":         "#bfdbfe",
    "dot_grid":        "#c8d8f0",
}

# Live theme dict — updated in-place when the user switches themes.
# Start in dark mode; all other modules import this object by reference.
T: dict = dict(DARK_T)

# ══════════════════════════════════════════════════════════════════════════════
#  FILE EXTENSIONS recognised as texture images
# ══════════════════════════════════════════════════════════════════════════════
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tga", ".gif", ".tiff"}
