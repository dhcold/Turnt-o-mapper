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
#  THEME (dark UI colour palette)
# ══════════════════════════════════════════════════════════════════════════════
T = {
    "bg":        "#0c0e1a",
    "bg_panel":  "#12162a",
    "bg_card":   "#1a1f38",
    "bg_input":  "#0e1224",
    "accent":    "#4fc3f7",
    "accent2":   "#9575cd",
    "text":      "#e8eaf6",
    "text_dim":  "#78849e",
    "success":   "#66bb6a",
    "warning":   "#ffa726",
    "border":    "#2a3050",
    "btn_fg":    "#ffffff",
    "prev_bg":   "#0b0f1e",
    "room_col":  "#1a3358",
    "room_bdr":  "#4fc3f7",
    "corr_col":  "#162238",
    "start_col": "#1b5e20",
    "end_col":   "#b71c1c",
    "lbx_bg":    "#0e1224",
    "lbx_sel":   "#263850",
    "dot_grid":  "#182236",
}

# ══════════════════════════════════════════════════════════════════════════════
#  FILE EXTENSIONS recognised as texture images
# ══════════════════════════════════════════════════════════════════════════════
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tga", ".gif", ".tiff"}
