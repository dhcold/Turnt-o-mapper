"""
Data classes representing the core map objects.

Room  -- an axis-aligned rectangular room in Quake coordinate space.
Bridge -- a connection (corridor / ramp) between two rooms.

These are shared by layout, generation, preview, and import modules.
"""

from dataclasses import dataclass
from .constants import DOOR_H


@dataclass
class Room:
    """An axis-aligned rectangular room in Quake 3 coordinate space.

    Attributes:
        x, y, z: world-space origin (minimum corner).
        w, d, h: dimensions along X (width), Y (depth), Z (height).
        idx: sequential room index in the layout (0-based).
        floor_t, wall_t, ceil_t: texture names for floor / walls / ceiling.
        travel_axis: dominant player movement direction ('x' or 'y').
        speed_in: estimated player entry speed in units-per-second (UPS).
        door_hw: half-width of the exit door opening.
    """
    x: int; y: int; z: int
    w: int; d: int; h: int
    idx: int = 0
    floor_t:      str   = "turnt/turnt_concrete"
    wall_t:       str   = "turnt/turnt_tech"
    ceil_t:       str   = "turnt/turnt_sky"
    accent_t:     str   = "turnt/turnt_cyan"
    travel_axis:  str   = 'x'
    speed_in:     float = 550.0
    door_hw:      int   = 64

    @property
    def x1(self):
        """Minimum X bound (same as self.x)."""
        return self.x

    @property
    def y1(self):
        """Minimum Y bound (same as self.y)."""
        return self.y

    @property
    def z1(self):
        """Minimum Z bound (floor level, same as self.z)."""
        return self.z

    @property
    def x2(self):
        """Maximum X bound (self.x + self.w)."""
        return self.x + self.w

    @property
    def y2(self):
        """Maximum Y bound (self.y + self.d)."""
        return self.y + self.d

    @property
    def z2(self):
        """Maximum Z bound (ceiling level, self.z + self.h)."""
        return self.z + self.h

    def cx(self):
        """Centre X coordinate of the room."""
        return (self.x1 + self.x2) // 2

    def cy(self):
        """Centre Y coordinate of the room."""
        return (self.y1 + self.y2) // 2


@dataclass
class Bridge:
    """A connection between two rooms -- either a flat corridor or a ramp.

    Attributes:
        room_a, room_b: indices of the connected rooms (a -> b).
        axis: travel direction of the corridor ('x' or 'y').
        ax, ay, az: bridge endpoint at room_a's wall.
        bx, by, bz: bridge endpoint at room_b's wall.
        door_hw: half-width of the door opening.
        door_ht: height of the door opening.
        floor_t, wall_t, ceil_t: texture names for the corridor brushes.
    """
    room_a: int; room_b: int
    axis: str
    ax: int; ay: int; az: int
    bx: int; by: int; bz: int
    door_hw: int = 64
    door_ht: int = DOOR_H
    floor_t: str = "turnt/turnt_asphalt"
    wall_t:  str = "turnt/turnt_concrete"
    ceil_t:  str = "turnt/turnt_sky"
