#!/usr/bin/env python3
"""
Tally case — 3D-printed enclosure for the ESP32-C3 Super Mini tally counter.

Four print-ready STLs for a two-part case plus two button caps:

  stl/tally-base.stl       tub: battery + TP4056 + slide switch below, the
                           50 x 50 perfboard on a ledge above
  stl/tally-lid.stl        plate with OLED window, two cap holes and the name
                           engraved on top; its skirt slides inside the frame,
                           clicks into four grooves and clamps the perfboard
  stl/tally-cap-plus.stl   button cap, embossed "+" (right button, UP)
  stl/tally-cap-minus.stl  button cap, embossed "-" (left button, DOWN)

plus two generated web pages (committed, never hand-edited — filtarr style):

  preview.html             self-contained three.js preview: the four parts
                           + ghost electronics, base64 STLs, three.js inlined
                           from vendor/ (`make vendor` fetches it)
  ../index.html            GitHub Pages landing page linking the preview,
                           the STLs, the docs images and the firmware folders

World frame: X = width (left/right as held), Y = length (Y- = bottom end with
both USB-C ports, Y+ = top end with the display), Z up, Z = 0 = outer bottom
face of the base, XY origin = centre of the inner cavity. Everything is built
in this frame; the lid is flipped to print orientation at export only.

Assembly: TP4056 (USB-C first, into its wall pocket) -> battery -> slide
switch (drop it between its two ribs from inside with the handle through the
wall slot; a dab of glue holds it) -> perfboard onto the ledge -> caps into
the lid from below -> lid. Print the base upright, the lid upside-down on its
top face, the caps upright on their flanges; no supports needed.

Usage:
  python3 generate.py [--clear-friction MM] [--snap-bite MM] [--tact-height MM]
                      [--battery WxLxT] [--engraving TEXT | --omit-engraving]

Fit tolerances are CLI flags (defaults below), so they can be tuned per
printer/kit without editing code — via Docker: see the repo README.
All dimensions are millimetres.
"""

import argparse
import base64
import json
import math
import os
import sys

import numpy as np
import trimesh
from shapely import affinity
from shapely.geometry import Polygon, box as shp_box

HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# DESIGN PARAMETERS
# --------------------------------------------------------------------------

# Shell
WALL = 2.0             # base wall: 5 perimeters with a 0.4 nozzle, rigid enough
FLOOR = 2.0            # base floor: 10 layers at 0.2 mm
LID_T = 2.0            # lid plate (same as the floor)
CORNER_R = 4.0         # outer plan-view corner radius: pocketable, no sharp edges
SKIRT_T = 1.2          # lid skirt: 3 perimeters, braced by the frame wall when closed
LEDGE_MIN = 1.5        # minimum ledge the perfboard edge rests on (minus PCB_CLEAR)
CLEAR_FRICTION = 0.28  # lid-skirt-to-frame clearance per side (printer-calibrated
                       # friction fit, carried over from filtarr; --clear-friction)

# Perfboard: Özdisan 5x5 single-sided board, used whole. 18 x 19 holes centred
# on 50 x 50 (2.14 mm from the outer row centres to the Y edges, 3.41 from the
# outer column centres to the X edges). Pads on one face only: they face down,
# components go on the bare face.
PCB_URL = "https://www.ozdisan.com/p/prototipleme-devreleri-621/ozd-arduino-delkl-pertnaks-5x5-643014"
PITCH = 2.54           # 0.1" hole pitch
PCB_W, PCB_L = 50.0, 50.0
PCB_COLS = 18          # holes along X
PCB_ROWS = 19          # holes along Y
PCB_T = 1.6            # FR4 thickness
PCB_CLEAR = 0.3        # per side, so the board drops into the frame

# 6 x 6 tact switches (two: left = DOWN "-", right = UP "+")
TACT_H = 5.0           # PCB top to plunger top; kits ship 4.3/5/6/7 (--tact-height)
TACT_PLUNGER_D = 3.5   # plunger diameter (the cap's underside recess centres on it)

# Battery pouch: 503450 cell 34 x 50 x 5 + PCM tab + 1 mm swelling (--battery)
BAT_W, BAT_L, BAT_T = 34.0, 52.0, 6.0
BAT_GAP = 0.5          # pouch to wall, per side (never squeeze a LiPo)

# TP4056 USB-C charger module, lying flat on the floor, components up, USB at Y-
TP_W, TP_L, TP_T = 17.0, 28.0, 1.0
TP_USB_W, TP_USB_H = 9.0, 3.2     # receptacle shell, sits on top of the PCB
TP_USB_OVERHANG = 1.0  # receptacle beyond the PCB short edge
TP_POCKET = 1.0        # the PCB's USB end sinks this far into the Y- wall, so the
                       # receptacle face ends up flush with the outer face

# ESP32-C3 Super Mini on male headers, USB at Y-
ESP_W, ESP_L = 18.0, 22.5
ESP_PIN_ROW_GAP = 15.24  # 6 pitches between the two pin rows
ESP_PIN_END = 2.36     # first pin centre to the USB short edge
ESP_USB_OVERHANG = 1.5  # receptacle beyond the PCB edge
ESP_USB_W, ESP_USB_H = 9.0, 3.2
ESP_STANDOFF = 2.54    # male-header plastic spacer between perfboard and module
ESP_PCB_T = 1.0
USB_WALL_T = 1.4       # wall left in front of the ESP32's USB-C by the plug relief

# 0.91" 128x32 OLED on a 1x4 header along Y at its X- short end
OLED_W, OLED_L = 38.0, 12.0
OLED_PIN_EDGE = 2.0    # header pin centres to the short PCB edge
OLED_GLASS = (30.0, 11.5)
OLED_AA = (22.4, 5.6)  # active area
OLED_AA_DX = 3.7       # active-area centre offset from the PCB centre, away from the header
OLED_GLASS_TOP = 5.0   # above the perfboard top: header spacer 2.54 + PCB 1.0 + glass
OLED_COVER_TOP = 6.9   # the IC seal cover is the tallest point of the module
WIN_W, WIN_L = 27.0, 9.0  # lid window: active area + 2 mm each side, hides the glass edge

# SS12D00 slide switch on the X+ wall, body on the floor
SW_L, SW_H, SW_D = 8.8, 3.9, 3.5      # along the wall / vertical / into the cavity
SW_SLOT_L, SW_SLOT_H = 4.0, 2.0       # wall slot: 1.5 handle + 2.0 travel, 0.5 play
SW_Y = 14.0            # clear of the TP4056 (ends at Y ~ +1) and of the Y+ corner
SW_RIB_T, SW_RIB_D = 1.2, 4.5         # the two ribs that trap the body

# Stack heights
LID_CLEAR = 7.5        # lid underside above the perfboard top: clears the OLED cover
                       # (6.9) and the ESP32's USB-C (6.74)
PCB_Z = 9.0            # perfboard underside above the inner floor: battery 6 + 2.5
                       # solder-side clearance, rounded

# Button caps
CAP_D = 8.0            # stem through the lid hole
CAP_HOLE_D = 8.4       # 0.2 mm per side: slides, no wobble
CAP_FLANGE_D = 11.0    # flange under the plate keeps the cap in the lid
CAP_RECESS_D = 3.8     # underside recess that centres the cap on the Ø3.5 plunger
CAP_RECESS_H = 0.5
SYMBOL_H = 0.5         # embossed + / - height (2-3 layers): felt, not just seen
SYMBOL_BAR = (4.0, 1.0)

RIB_T, RIB_H = 1.2, 5.0  # battery/TP4056 divider rib and the TP stop block
PRY_W, PRY_H = 10.0, 1.5  # pry notch in the Y+ wall top edge

# Lid snap detents: four bumps on the skirt's outer face click into grooves in
# the frame's inner face, so a lid-first pickup or an inverted counter does not
# shed the lid (the skirt alone is a friction fit that also clamps the
# perfboard). Both ramps are 45 deg, so the pry notch still releases it and
# the flipped lid prints them without support. --snap-bite 0 = friction only.
SNAP_BITE = 0.4        # crest past the frame's inner face: PETG; PLA ~0.3 (--snap-bite)
SNAP_LEN = 8.0         # bump length along the wall
SNAP_Z0 = 0.5          # bump root above the skirt bottom, off the perfboard edge
SNAP_CREST = 0.8       # flat crest between the two 45 deg ramps
SNAP_GROOVE_CLEAR = 0.1  # groove deeper than the bite: the crest never bottoms out
SNAP_MIN_WALL = 1.0    # frame wall that must remain behind a groove
USB_CUT_W = 10.0       # USB-C openings: 9 mm shell + 0.5 mm per side
USB_CUT_PAD = 1.0      # extra opening height (0.5 below, 0.5 above the shell)
QS = 24                # quad segments for shapely buffers (corner smoothness)
PARTS = ("base", "lid", "cap-plus", "cap-minus")

# Lid engraving: ENGRAVE_TEXT into the lid top (--engraving / --omit-engraving),
# Liberation Sans Bold via matplotlib's TextPath (filtarr's mechanism; the font
# comes from the Dockerfile's fonts-liberation). Reads along +X, upright toward
# Y+, i.e. the right way up with the USB ports toward you. The lid prints
# top-face-down, so the recess sits on the bed and comes out crisp.
ENGRAVE_TEXT = "Grindarr"  # None = omitted
ENGRAVE_DEPTH = 0.6        # 3 layers at 0.2 mm
ENGRAVE_H = 6.0            # cap height; auto-shrunk if the text would not fit
ENGRAVE_XY = (0.0, -13.0)  # centre: the free band between the cap holes and the Y- edge
ENGRAVE_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def derive():
    """Cavity, frame and layout numbers that follow from the parameters above.
    Module globals on purpose (house style): re-run after apply_printer_args."""
    global CAV_W, CAV_L, OPEN_W, OPEN_L, OUT_W, OUT_L
    global Z_LEDGE, PCB_TOP, Z_TOP, SKIRT_W, SKIRT_L, SKIRT_NOTCH_W
    global BAT_X0, TP_X0, TP_X, TP_Y0, RIB_X, ESP_X, ESP_Y0, ESP_POCKET
    global USB_RELIEF_Y, ESP_USB_RECESS
    global TACT_XY, OLED_X, OLED_Y, WIN_XY, CAP_FLANGE_T, CAP_STEM_H
    global SNAP_P, SNAP_Z, SNAP_SITES
    # lower cavity: battery beside the TP4056 (rib + two gaps = 3 mm), or the
    # frame opening plus a ledge on each side, whichever is wider
    CAV_W = max(BAT_W + TP_W + 3.0, PCB_W + 2 * (PCB_CLEAR + LEDGE_MIN))
    CAV_L = max(BAT_L + 2 * BAT_GAP, PCB_L + 2 * (PCB_CLEAR + LEDGE_MIN))
    OPEN_W, OPEN_L = PCB_W + 2 * PCB_CLEAR, PCB_L + 2 * PCB_CLEAR
    OUT_W, OUT_L = CAV_W + 2 * WALL, CAV_L + 2 * WALL
    Z_LEDGE = FLOOR + PCB_Z
    PCB_TOP = Z_LEDGE + PCB_T
    Z_TOP = PCB_TOP + LID_CLEAR
    SKIRT_W, SKIRT_L = OPEN_W - 2 * CLEAR_FRICTION, OPEN_L - 2 * CLEAR_FRICTION
    # under the perfboard: battery at X-, TP4056 against the X+ wall, rib between
    BAT_X0 = -CAV_W / 2 + BAT_GAP
    TP_X0 = CAV_W / 2 - TP_W
    TP_X = TP_X0 + TP_W / 2
    TP_Y0 = -CAV_L / 2 - TP_POCKET
    RIB_X = (BAT_X0 + BAT_W + TP_X0) / 2
    # ESP32: pin rows in cols 3 and 9, rows 0..7, USB at Y-. Row 0 sits 2.14 mm
    # from the board edge, so the module's PCB just reaches the frame wall (a
    # shallow clearance pocket in the wall's inner face, 0.3 like the TP4056's)
    # and its USB-C face would sit ~2 mm inside a full-thickness wall — too deep
    # for a plug. So the wall's OUTER face gets a plug relief (SKIRT_NOTCH_W wide,
    # from PCB_TOP + 2 up through the lid plate) that leaves USB_WALL_T of wall
    # beside the USB slot: the receptacle face ends up ~flush with it.
    ESP_X = hole(6, 0)[0]
    ESP_Y0 = hole(3, 0)[1] - ESP_PIN_END
    ESP_POCKET = max(0.0, -OPEN_L / 2 - ESP_Y0 + 0.3)
    SKIRT_NOTCH_W = ESP_W + 1.0
    USB_RELIEF_Y = -OPEN_L / 2 - ESP_POCKET - USB_WALL_T   # the face a plug butts against
    ESP_USB_RECESS = (ESP_Y0 - ESP_USB_OVERHANG) - USB_RELIEF_Y  # > 0 = behind that face
    # tact bodies between cols 3/4 and 13/14 on row 11 (row 12 would hit the OLED)
    TACT_XY = (hole(3.5, 11), hole(13.5, 11))
    # OLED header in col 1, rows 14..17; PCB extends towards X+ and ends at
    # Y +22.5, clear of the lid skirt along the Y+ edge
    OLED_X = hole(1, 0)[0] - OLED_PIN_EDGE + OLED_W / 2
    OLED_Y = hole(0, 15.5)[1]
    WIN_XY = (OLED_X + OLED_AA_DX, OLED_Y)
    # caps: flange fills the gap under the plate minus 0.3 play (no rattle),
    # stem ends 1 mm proud of the lid
    CAP_FLANGE_T = LID_CLEAR - TACT_H - 0.3
    CAP_STEM_H = (LID_CLEAR - TACT_H) + LID_T + 1.0
    # snap detents: a crest CLEAR_FRICTION + SNAP_BITE off the skirt face bites
    # SNAP_BITE past the frame; bump roots (seated lid) from SNAP_Z0 above the
    # skirt bottom (= PCB_TOP) over two 45 deg ramps plus the crest. Sites as
    # (outward normal, XY on the frame's inner face): mid X-, X+ and Y+ walls,
    # and the Y- skirt remnant right of the ESP32 notch, at its midpoint
    SNAP_P = CLEAR_FRICTION + SNAP_BITE
    SNAP_Z = (PCB_TOP + SNAP_Z0, PCB_TOP + SNAP_Z0 + 2 * SNAP_P + SNAP_CREST)
    SNAP_SITES = (((-1.0, 0.0), (-OPEN_W / 2, 0.0)), ((1.0, 0.0), (OPEN_W / 2, 0.0)),
                  ((0.0, 1.0), (0.0, OPEN_L / 2)),
                  ((0.0, -1.0), ((ESP_X + SKIRT_NOTCH_W / 2 + OPEN_W / 2) / 2, -OPEN_L / 2)))


def hole(col, row):
    """Perfboard hole centre (col along X, row along Y; row 0 at Y-) in world
    XY — the board is centred on the cavity. Half-integers = between holes."""
    return ((col - (PCB_COLS - 1) / 2) * PITCH, (row - (PCB_ROWS - 1) / 2) * PITCH)


# --------------------------------------------------------------------------
# STATELESS MESH HELPERS
# --------------------------------------------------------------------------


def prism(poly, z0, z1):
    m = trimesh.creation.extrude_polygon(poly, z1 - z0)
    m.apply_translation([0.0, 0.0, z0])
    return m


def bbox(x0, y0, z0, x1, y1, z1):
    """Axis-aligned box from two corners."""
    m = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    m.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return m


def cyl(d, z0, z1, xy=(0.0, 0.0)):
    m = trimesh.creation.cylinder(radius=d / 2, height=z1 - z0, sections=64)
    m.apply_translation([xy[0], xy[1], (z0 + z1) / 2])
    return m


def diff(solid, *cutters):
    return trimesh.boolean.difference([solid, *cutters], check_volume=False)


def union(*parts):
    return trimesh.boolean.union(list(parts), check_volume=False)


def rounded_rect(w, l, r):
    return shp_box(-w / 2 + r, -l / 2 + r, w / 2 - r, l / 2 - r).buffer(r, quad_segs=QS)


def wall_frame(n, xy):
    """4x4 that stands a mesh built in (u = out of the wall, v = up, s = along
    the wall) against a wall: u along the outward XY normal n, v along world Z,
    origin at xy on Z = 0. s = n x Z keeps it right-handed (no mirrored faces)."""
    m = np.eye(4)
    m[:3, 0] = (*n, 0.0)
    m[:3, 1] = (0.0, 0.0, 1.0)
    m[:3, 2] = np.cross((*n, 0.0), (0.0, 0.0, 1.0))
    m[:3, 3] = (*xy, 0.0)
    return m


def snap_bump(n, xy):
    """One detent bump on the skirt's outer face at site (n, xy): the (u, z)
    profile — 45 deg lead-in out to SNAP_P, flat crest, 45 deg back to the
    face — extruded SNAP_LEN along the wall, sunk 0.5 into the skirt so the
    union has no coplanar seam. Square ends."""
    z0, z1 = SNAP_Z
    profile = Polygon([(-0.5, z0), (0.0, z0), (SNAP_P, z0 + SNAP_P), (SNAP_P, z1 - SNAP_P),
                       (0.0, z1), (-0.5, z1)])
    m = trimesh.creation.extrude_polygon(profile, SNAP_LEN)
    m.apply_translation([0.0, 0.0, -SNAP_LEN / 2])
    m.apply_transform(wall_frame(n, (xy[0] - n[0] * CLEAR_FRICTION, xy[1] - n[1] * CLEAR_FRICTION)))
    return m


def snap_groove(n, xy):
    """The bump's groove in the frame's inner face: a plain channel SNAP_BITE +
    SNAP_GROOVE_CLEAR deep, 1 mm longer and 0.2 taller each way than the bump,
    closed above (a slot up to the frame top would retain nothing). Built in
    the wall frame (u, z, s) and reaching 1 mm into the opening: no coplanar
    face with the opening cutter."""
    z0, z1 = SNAP_Z
    m = bbox(-1.0, z0 - 0.2, -(SNAP_LEN + 1.0) / 2,
             SNAP_BITE + SNAP_GROOVE_CLEAR, z1 + 0.2, (SNAP_LEN + 1.0) / 2)
    m.apply_transform(wall_frame(n, xy))
    return m


def print_orientation_lid(lid):
    """Flip the lid so its top face lies on the print bed."""
    m = lid.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
    m.apply_translation([0.0, 0.0, -m.bounds[0][2]])
    return m


# --------------------------------------------------------------------------
# PARTS (world frame)
# --------------------------------------------------------------------------


def build_base():
    solid = prism(rounded_rect(OUT_W, OUT_L, CORNER_R), 0.0, Z_TOP)
    esp_usb_z = PCB_TOP + ESP_STANDOFF + ESP_PCB_T - USB_CUT_PAD / 2
    tp_usb_z = FLOOR + TP_T - USB_CUT_PAD / 2
    cutters = [
        # lower cavity (floor to ledge), then the perfboard frame above it
        bbox(-CAV_W / 2, -CAV_L / 2, FLOOR, CAV_W / 2, CAV_L / 2, Z_LEDGE),
        bbox(-OPEN_W / 2, -OPEN_L / 2, Z_LEDGE - 1.0, OPEN_W / 2, OPEN_L / 2, Z_TOP + 1.0),
        # ESP32 USB-C through the Y- frame wall. Runs out through the wall top:
        # the 0.26 mm of wall the spec'd height would leave is unprintable; the
        # lid plate closes it (its skirt is notched here anyway)
        bbox(ESP_X - USB_CUT_W / 2, -OUT_L / 2 - 1.0, esp_usb_z,
             ESP_X + USB_CUT_W / 2, -OPEN_L / 2 + 1.0, Z_TOP + 1.0),
        # plug relief in the wall's outer face (the lid plate is notched above
        # it), leaving USB_WALL_T of wall around the slot
        bbox(ESP_X - SKIRT_NOTCH_W / 2, -OUT_L / 2 - 1.0, PCB_TOP + 2.0,
             ESP_X + SKIRT_NOTCH_W / 2, USB_RELIEF_Y, Z_TOP + 1.0),
        # clearance pocket in the frame's inner face for the module PCB's edge
        bbox(ESP_X - SKIRT_NOTCH_W / 2, -OPEN_L / 2 - ESP_POCKET, PCB_TOP + ESP_STANDOFF - 0.5,
             ESP_X + SKIRT_NOTCH_W / 2, -OPEN_L / 2 + 1.0, Z_TOP + 1.0),
        # TP4056 USB-C through the Y- lower wall + inner-face pocket for its PCB end
        bbox(TP_X - USB_CUT_W / 2, -OUT_L / 2 - 1.0, tp_usb_z,
             TP_X + USB_CUT_W / 2, -CAV_L / 2 + 1.0, tp_usb_z + TP_USB_H + USB_CUT_PAD),
        bbox(TP_X0 - 0.3, TP_Y0, FLOOR - 1.0, CAV_W / 2, -CAV_L / 2 + 1.0, FLOOR + RIB_H),
        # slide switch handle slot through the X+ wall
        bbox(CAV_W / 2 - 1.0, SW_Y - SW_SLOT_L / 2, FLOOR + (SW_H - SW_SLOT_H) / 2,
             OUT_W / 2 + 1.0, SW_Y + SW_SLOT_L / 2, FLOOR + (SW_H + SW_SLOT_H) / 2),
        # pry notch in the Y+ wall top edge, centred
        bbox(-PRY_W / 2, OPEN_L / 2 - 1.0, Z_TOP - PRY_H, PRY_W / 2, OUT_L / 2 + 1.0, Z_TOP + 1.0),
    ]
    if SNAP_BITE > 0:  # lid detent grooves in the frame's inner face
        cutters += [snap_groove(n, xy) for n, xy in SNAP_SITES]
    shell = diff(solid, *cutters)
    # ribs are sunk 0.5 mm into floor/wall so the union has no coplanar seams
    tp_y1 = TP_Y0 + TP_L
    sw_rib_dy = SW_L / 2 + 0.2 + SW_RIB_T / 2
    ribs = [
        # battery | TP4056 divider, running the TP length
        bbox(RIB_X - RIB_T / 2, -CAV_L / 2 - 0.5, FLOOR - 0.5, RIB_X + RIB_T / 2, tp_y1, FLOOR + RIB_H),
        # stop block behind the TP4056
        bbox(CAV_W / 2 - 5.0, tp_y1, FLOOR - 0.5, CAV_W / 2 + 0.5, tp_y1 + RIB_T, FLOOR + RIB_H),
    ] + [
        bbox(CAV_W / 2 - SW_RIB_D, y - SW_RIB_T / 2, FLOOR - 0.5, CAV_W / 2 + 0.5, y + SW_RIB_T / 2,
             FLOOR + SW_H + 0.6)
        for y in (SW_Y - sw_rib_dy, SW_Y + sw_rib_dy)
    ]
    return union(shell, *ribs)


def build_lid():
    plate = prism(rounded_rect(OUT_W, OUT_L, CORNER_R), Z_TOP, Z_TOP + LID_T)
    ring = shp_box(-SKIRT_W / 2, -SKIRT_L / 2, SKIRT_W / 2, SKIRT_L / 2).difference(
        shp_box(-SKIRT_W / 2 + SKIRT_T, -SKIRT_L / 2 + SKIRT_T,
                SKIRT_W / 2 - SKIRT_T, SKIRT_L / 2 - SKIRT_T))
    skirt = prism(ring, Z_TOP - LID_CLEAR, Z_TOP + 0.5)  # bottom lands on the perfboard
    bumps = [snap_bump(n, xy) for n, xy in SNAP_SITES] if SNAP_BITE > 0 else []
    cutters = [
        bbox(WIN_XY[0] - WIN_W / 2, WIN_XY[1] - WIN_L / 2, Z_TOP - 1.0,
             WIN_XY[0] + WIN_W / 2, WIN_XY[1] + WIN_L / 2, Z_TOP + LID_T + 1.0),
        # skirt notch on the Y- side: the ESP32 module passes under the plate
        bbox(ESP_X - SKIRT_NOTCH_W / 2, -SKIRT_L / 2 - 1.0, Z_TOP - LID_CLEAR - 1.0,
             ESP_X + SKIRT_NOTCH_W / 2, -SKIRT_L / 2 + SKIRT_T + 1.0, Z_TOP),
        # plate notch over the base's USB-C plug relief, so a plug's overmold
        # reaches the thin wall instead of stopping at the plate edge
        bbox(ESP_X - SKIRT_NOTCH_W / 2, -OUT_L / 2 - 1.0, Z_TOP - 1.0,
             ESP_X + SKIRT_NOTCH_W / 2, USB_RELIEF_Y, Z_TOP + LID_T + 1.0),
    ] + [cyl(CAP_HOLE_D, Z_TOP - 1.0, Z_TOP + LID_T + 1.0, xy) for xy in TACT_XY]
    geom, _ = engraving_geometry()
    if geom is not None:
        top = Z_TOP + LID_T
        cutters += [prism(q, top - ENGRAVE_DEPTH, top + 1.0) for q in getattr(geom, "geoms", [geom])]
    return diff(union(plate, skirt, *bumps), *cutters)


def engraving_geometry():
    """ENGRAVE_TEXT as one shapely (Multi)Polygon in world XY on the lid top,
    plus the cap height actually used: Liberation Sans Bold through matplotlib's
    TextPath, scaled to ENGRAVE_H cap height (shrunk if it would leave the free
    band), centred on ENGRAVE_XY, reading along +X. (None, 0) when omitted."""
    if ENGRAVE_TEXT is None:
        return None, 0.0
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    fp = FontProperties(fname=ENGRAVE_FONT)

    def glyphs(text):
        # outer rings first; a ring inside what we have so far is a counter
        rings = sorted((Polygon(r).buffer(0) for r in TextPath((0, 0), text, size=40, prop=fp)
                        .to_polygons() if len(r) >= 3), key=lambda q: -q.area)
        geom = None
        for q in rings:
            if not q.is_empty:
                geom = q if geom is None else (geom.difference(q) if geom.covers(q) else geom.union(q))
        return geom

    geom, cap = glyphs(ENGRAVE_TEXT), glyphs("H").bounds
    x0, y0, x1, y1 = geom.bounds
    # free band: inside the lid edges by WALL + 4, below the cap holes by 2
    y_lo = -OUT_L / 2 + WALL + 4.0
    y_hi = min(y for _, y in TACT_XY) - CAP_HOLE_D / 2 - 2.0
    max_w, max_h = OUT_W - 2 * (WALL + 4.0), 2 * min(ENGRAVE_XY[1] - y_lo, y_hi - ENGRAVE_XY[1])
    s = min(ENGRAVE_H / (cap[3] - cap[1]), max_w / (x1 - x0), max_h / (y1 - y0))
    geom = affinity.scale(geom, s, s, origin=(0, 0))
    x0, y0, x1, y1 = geom.bounds
    geom = affinity.translate(geom, ENGRAVE_XY[0] - (x0 + x1) / 2, ENGRAVE_XY[1] - (y0 + y1) / 2)
    return geom, s * (cap[3] - cap[1])


def build_cap(symbol):
    """Button cap at XY origin, seated on its plunger (flange underside at
    PCB_TOP + TACT_H). symbol: 'plus' or 'minus'."""
    z0 = PCB_TOP + TACT_H
    top = z0 + CAP_STEM_H
    bw, bt = SYMBOL_BAR
    bars = [bbox(-bw / 2, -bt / 2, top - 0.5, bw / 2, bt / 2, top + SYMBOL_H)]
    if symbol == "plus":
        bars.append(bbox(-bt / 2, -bw / 2, top - 0.5, bt / 2, bw / 2, top + SYMBOL_H))
    body = union(cyl(CAP_FLANGE_D, z0, z0 + CAP_FLANGE_T),
                 cyl(CAP_D, z0 + CAP_FLANGE_T - 0.5, top), *bars)
    return diff(body, cyl(CAP_RECESS_D, z0 - 1.0, z0 + CAP_RECESS_H))


def build(name):
    if name == "base":
        return build_base()
    if name == "lid":
        return build_lid()
    return build_cap(name.split("-")[1])


def component_boxes():
    """Where the electronics sit, as world-frame (x0, y0, z0, x1, y1, z1) boxes.
    Shared by the docs renders (ghosts) and verify.py (nothing may intersect
    the shell)."""
    esp_y1 = ESP_Y0 + ESP_L
    esp_z0 = PCB_TOP + ESP_STANDOFF
    oled_z0 = PCB_TOP + ESP_STANDOFF
    gw, gl = OLED_GLASS
    boxes = {
        "perfboard": (-PCB_W / 2, -PCB_L / 2, Z_LEDGE, PCB_W / 2, PCB_L / 2, PCB_TOP),
        "battery": (BAT_X0, -BAT_L / 2, FLOOR, BAT_X0 + BAT_W, BAT_L / 2, FLOOR + BAT_T),
        "tp4056": (TP_X0, TP_Y0, FLOOR, TP_X0 + TP_W, TP_Y0 + TP_L, FLOOR + TP_T),
        "tp4056-usb": (TP_X - TP_USB_W / 2, TP_Y0 - TP_USB_OVERHANG, FLOOR + TP_T,
                       TP_X + TP_USB_W / 2, TP_Y0 + 7.0, FLOOR + TP_T + TP_USB_H),
        "esp32": (ESP_X - ESP_W / 2, ESP_Y0, esp_z0, ESP_X + ESP_W / 2, esp_y1, esp_z0 + ESP_PCB_T),
        "esp32-usb": (ESP_X - ESP_USB_W / 2, ESP_Y0 - ESP_USB_OVERHANG, esp_z0 + ESP_PCB_T,
                      ESP_X + ESP_USB_W / 2, ESP_Y0 + 7.0, esp_z0 + ESP_PCB_T + ESP_USB_H),
        "oled": (OLED_X - OLED_W / 2, OLED_Y - OLED_L / 2, oled_z0,
                 OLED_X + OLED_W / 2, OLED_Y + OLED_L / 2, oled_z0 + 1.0),
        "oled-glass": (OLED_X + OLED_AA_DX - gw / 2, OLED_Y - gl / 2, oled_z0 + 1.0,
                       OLED_X + OLED_AA_DX + gw / 2, OLED_Y + gl / 2, PCB_TOP + OLED_GLASS_TOP),
        "switch": (CAV_W / 2 - SW_D, SW_Y - SW_L / 2, FLOOR, CAV_W / 2, SW_Y + SW_L / 2, FLOOR + SW_H),
    }
    for side, (x, y) in zip(("left", "right"), TACT_XY):
        boxes[f"tact-{side}"] = (x - 3.0, y - 3.0, PCB_TOP, x + 3.0, y + 3.0, PCB_TOP + TACT_H)
    return boxes


# --------------------------------------------------------------------------
# BUILD + EXPORT
# --------------------------------------------------------------------------


def apply_printer_args(argv=None):
    """Override the printer/kit-fit parameters from the command line, so parts
    can be tuned without editing code (`... generate.py --clear-friction 0.32`)."""
    global CLEAR_FRICTION, SNAP_BITE, TACT_H, BAT_W, BAT_L, BAT_T, ENGRAVE_TEXT
    p = argparse.ArgumentParser(description="Generate the tally case STLs.")
    p.add_argument("--clear-friction", type=float, default=CLEAR_FRICTION,
                   metavar="MM", help="lid skirt clearance to the frame per side "
                   f"(default {CLEAR_FRICTION}; tune in ±0.04 steps)")
    p.add_argument("--snap-bite", type=float, default=SNAP_BITE, metavar="MM",
                   help="lid detent bite past the frame's inner face (default "
                   f"{SNAP_BITE}; PLA ~0.3; 0 = no detents, plain friction fit)")
    p.add_argument("--tact-height", type=float, default=TACT_H, metavar="MM",
                   help="6x6 tact switch height, PCB top to plunger top "
                   f"(default {TACT_H}; kits ship 4.3/5/6/7)")
    p.add_argument("--battery", default=f"{BAT_W:g}x{BAT_L:g}x{BAT_T:g}",
                   metavar="WxLxT", help="battery pouch envelope incl. tab and "
                   f"swelling (default {BAT_W:g}x{BAT_L:g}x{BAT_T:g})")
    p.add_argument("--engraving", default=ENGRAVE_TEXT, metavar="TEXT",
                   help=f"text engraved into the lid top (default {ENGRAVE_TEXT!r}; "
                   f"{ENGRAVE_H:g} mm caps, {ENGRAVE_DEPTH:g} mm deep, auto-shrunk to fit)")
    p.add_argument("--omit-engraving", action="store_true", help="plain lid top, no text")
    a = p.parse_args(argv)
    ENGRAVE_TEXT = None if a.omit_engraving else a.engraving
    if ENGRAVE_TEXT is not None:
        if not ENGRAVE_TEXT.strip():
            p.error("--engraving wants some text (or use --omit-engraving)")
        if not os.path.exists(ENGRAVE_FONT):
            p.error(f"{ENGRAVE_FONT} is missing — run inside the Docker image "
                    "(fonts-liberation) or use --omit-engraving")
        from matplotlib.font_manager import FontProperties
        from matplotlib.textpath import TextPath
        fp = FontProperties(fname=ENGRAVE_FONT)
        for ch in set(ENGRAVE_TEXT) - {" "}:
            if not TextPath((0, 0), ch, size=40, prop=fp).to_polygons():
                p.error(f"--engraving: Liberation Sans Bold has no outline for {ch!r}")
    try:
        bat = [float(v) for v in a.battery.lower().split("x")]
        assert len(bat) == 3
    except (ValueError, AssertionError):
        p.error("--battery wants WxLxT, e.g. 34x52x6")
    if LID_CLEAR < a.tact_height + 1.5:
        p.error(f"--tact-height {a.tact_height} needs LID_CLEAR >= "
                f"{a.tact_height + 1.5} (cap flange + 1 mm; LID_CLEAR is {LID_CLEAR})")
    if PCB_Z < bat[2] + 2.0:
        p.error(f"battery {bat[2]} mm thick needs PCB_Z >= {bat[2] + 2.0} "
                f"(2 mm solder-side clearance; PCB_Z is {PCB_Z})")
    if a.snap_bite < 0:
        p.error("--snap-bite wants >= 0 (0 = no detents)")
    CLEAR_FRICTION, SNAP_BITE, TACT_H = a.clear_friction, a.snap_bite, a.tact_height
    BAT_W, BAT_L, BAT_T = bat
    derive()
    if SNAP_BITE > 0:  # the grooves must leave wall, the Y- bump must miss the skirt notch
        wall = min(OUT_W - OPEN_W, OUT_L - OPEN_L) / 2 - (SNAP_BITE + SNAP_GROOVE_CLEAR)
        if wall < SNAP_MIN_WALL:
            p.error(f"--snap-bite {SNAP_BITE} leaves {wall:.2f} mm of frame wall behind "
                    f"the grooves (SNAP_MIN_WALL {SNAP_MIN_WALL})")
        x = SNAP_SITES[-1][1][0]  # the Y- bump, between the skirt notch and the corner
        if (x - SNAP_LEN / 2 < ESP_X + SKIRT_NOTCH_W / 2 + 1.0
                or x + SNAP_LEN / 2 > SKIRT_W / 2 - 1.0):
            p.error(f"the Y- snap bump ({x - SNAP_LEN / 2:.1f}..{x + SNAP_LEN / 2:.1f}) "
                    "comes within 1 mm of the skirt notch or corner: shorten SNAP_LEN")


def tolerance_summary():
    snap = (f"snap bite {SNAP_BITE:g} ({len(SNAP_SITES)} detents)" if SNAP_BITE > 0
            else "no snap (friction only)")
    return (f"lid skirt clearance {CLEAR_FRICTION:.2f} mm/side; {snap}; tact height "
            f"{TACT_H:.1f} (cap flange {CAP_FLANGE_T:.1f}, stem {CAP_STEM_H:.1f}); "
            f"battery {BAT_W:g} x {BAT_L:g} x {BAT_T:g}")


def shell_summary():
    return (f"walls {WALL:.1f} / floor {FLOOR:.1f} / lid {LID_T:.1f} / skirt "
            f"{SKIRT_T:.1f} mm; cavity {CAV_W:.1f} x {CAV_L:.1f}, perfboard on the "
            f"ledge at Z {Z_LEDGE:.1f}; outer {OUT_W:.1f} x {OUT_L:.1f} x "
            f"{Z_TOP + LID_T:.1f} with lid; ESP32 USB-C behind {USB_WALL_T:.1f} mm "
            f"of wall, recessed {ESP_USB_RECESS:.2f}")


def engraving_summary():
    if ENGRAVE_TEXT is None:
        return "omitted"
    _, cap = engraving_geometry()
    return f'"{ENGRAVE_TEXT}" ({cap:.3g} mm, {ENGRAVE_DEPTH:g} deep)'


def main():
    apply_printer_args()
    summary = [("tolerances", tolerance_summary()), ("shell", shell_summary()),
               ("engraving", engraving_summary())]
    for label, text in summary:
        print(f"{label} — {text}")
    print()
    stl_dir = os.path.join(HERE, "stl")
    os.makedirs(stl_dir, exist_ok=True)
    parts = {}
    for name in PARTS:
        mesh = parts[name] = build(name)
        assert mesh.is_watertight, f"{name} is not watertight!"
        out = print_orientation_lid(mesh) if name == "lid" else mesh.copy()
        out.apply_translation([0.0, 0.0, -out.bounds[0][2]])
        path = os.path.join(stl_dir, f"tally-{name}.stl")
        out.export(path)
        ext = out.bounds[1] - out.bounds[0]
        print(f"  {os.path.basename(path):24s} {ext[0]:6.1f} x {ext[1]:6.1f} x "
              f"{ext[2]:5.1f} mm  {mesh.volume / 1000.0:6.1f} cm3")
    build_preview(parts, summary)
    build_index()
    print("\ndone.")


# --------------------------------------------------------------------------
# PREVIEW + PAGES INDEX (filtarr mechanism: base64 STLs and the vendored
# three.js inlined into the template, so the page works offline)
# --------------------------------------------------------------------------

REPO_URL = "https://github.com/Ardakilic/esp32-tally"
PART_COLORS = {"base": "#8a8f98", "lid": "#5f8cc4", "cap-plus": "#e0a040",
               "cap-minus": "#e0a040"}
# ghost electronics (component_boxes names -> colour), the render_docs.py
# palette as hex; the tact switches are hidden under the caps and skipped
PREVIEW_GHOSTS = {"perfboard": "#bf8c33", "battery": "#59a6d9", "tp4056": "#d95959",
                  "tp4056-usb": "#666666", "esp32": "#333333", "esp32-usb": "#666666",
                  "oled": "#334d99", "oled-glass": "#1a1a1a", "switch": "#e6e6e6"}


def b64stl(mesh):
    return base64.b64encode(mesh.export(file_type="stl")).decode()


def build_preview(parts, summary):
    """Write preview.html: the world-frame parts (caps moved onto their tact
    switches) + translucent component boxes, embedded as base64 binary STL,
    plus both vendored three.js files, into preview_template.html.
    summary = [(label, text), ...] as printed by main() -> Dimensions panel."""
    for name in ("three.module.min.js", "three.core.min.js"):
        if not os.path.exists(os.path.join(HERE, "vendor", name)):
            sys.exit(f"vendor/{name} is missing — run `make vendor` first")

    def part(name, mesh, attach):
        return {"name": name, "attach": attach, "color": PART_COLORS[name],
                "stl": b64stl(mesh)}

    caps = {"cap-minus": TACT_XY[0], "cap-plus": TACT_XY[1]}  # left / right
    data_parts = [part("base", parts["base"], "base"), part("lid", parts["lid"], "lid")]
    for name, (x, y) in caps.items():
        m = parts[name].copy()
        m.apply_translation([x, y, 0.0])
        data_parts.append(part(name, m, "cap"))
    for name, b in component_boxes().items():
        if name in PREVIEW_GHOSTS:
            data_parts.append({"name": name, "attach": "base", "ghost": True,
                               "color": PREVIEW_GHOSTS[name], "opacity": 0.45,
                               "stl": b64stl(bbox(*b))})

    data = {
        "title": "ESP32 Tally Counter — case preview",
        "parts": data_parts,
        "dims": {"closed": f"{OUT_W:.1f} x {OUT_L:.1f} x {Z_TOP + LID_T:.1f} mm",
                 **dict(summary)},
        "files": [f"stl/tally-{name}.stl" for name in PARTS],
    }

    def b64file(name):
        with open(os.path.join(HERE, "vendor", name), "rb") as f:
            return base64.b64encode(f.read()).decode()

    with open(os.path.join(HERE, "preview_template.html")) as f:
        tpl = f.read()

    html = tpl.replace("/*__THREE_B64__*/", b64file("three.module.min.js"))
    html = html.replace("/*__THREE_CORE_B64__*/", b64file("three.core.min.js"))
    html = html.replace("/*__DATA__*/null", json.dumps(data))
    out = os.path.join(HERE, "preview.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"  {os.path.basename(out):24s} ({os.path.getsize(out) / 1e6:.1f} MB preview)")


def build_index():
    """Landing page (repo-root index.html) linking the preview, the STL
    downloads, the docs images and the firmware folders — published to
    GitHub Pages by .github/workflows/pages.yml. Needs the repo root mounted
    (the Makefile mounts it at /app and runs in /app/case)."""
    def size(path):
        return f"{os.path.getsize(os.path.join(HERE, path)) / 1e3:.0f} kB"

    stls = "".join(
        f'<li><a href="case/stl/tally-{name}.stl">tally-{name}.stl</a> '
        f"({size(f'stl/tally-{name}.stl')})</li>" for name in PARTS)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP32 Tally Counter — pocket tally counter, 3D-printed case</title>
<style>
  :root {{ --bg: #14171c; --panel: #1e232b; --ink: #e8eaee; --muted: #9aa3b0;
           --accent: #35b8a5; --line: #313945; }}
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ background: var(--bg); color: var(--ink); padding: 40px 20px;
          font: 15px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif; }}
  main {{ max-width: 1080px; margin: 0 auto; }}
  h1 {{ font-size: 30px; }} h1 span {{ color: var(--accent); }}
  .tagline {{ color: var(--muted); margin: 6px 0 8px; }}
  .top a {{ color: var(--accent); }}
  .grid {{ display: grid; gap: 18px; margin-top: 28px;
           grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }}
  article {{ background: var(--panel); border: 1px solid var(--line);
             border-radius: 14px; padding: 16px; }}
  article img {{ width: 100%; border-radius: 8px; background: #fff; }}
  article h2 {{ font-size: 17px; margin: 12px 0 4px; }}
  .geo {{ color: var(--muted); font-size: 13px; margin-bottom: 10px; }}
  .btn {{ display: inline-block; background: var(--accent); color: #08201c;
          font-weight: 600; text-decoration: none; padding: 8px 14px;
          border-radius: 8px; font-size: 14px; }}
  details {{ margin-top: 10px; font-size: 13px; color: var(--muted); }}
  details a, ul.links a {{ color: var(--ink); }}
  details li, ul.links li {{ margin: 3px 0 3px 18px; word-break: break-all; }}
  ul.links {{ font-size: 13px; color: var(--muted); }}
  footer {{ color: var(--muted); font-size: 13px; margin-top: 32px; }}
  footer a {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <div class="top">
    <h1><span>ESP32 Tally Counter</span> — pocket tally counter</h1>
    <p class="tagline">Two buttons, a 0.91" OLED, an ESP32-C3 Super Mini and a
      1000 mAh LiPo in a {OUT_W:.0f} × {OUT_L:.0f} × {Z_TOP + LID_T:.0f} mm 3D-printed case.
      Plain and ESPHome firmwares. Open source, generated from one script.</p>
    <p><a href="{REPO_URL}">Source, build guide &amp; README on GitHub</a></p>
  </div>
  <div class="grid">
  <article>
    <a href="case/docs/renders.png"><img loading="lazy" src="case/docs/renders.png"
         alt="Renders of the tally counter case, closed and exploded"></a>
    <h2>Case</h2>
    <p class="geo">{OUT_W:.1f} × {OUT_L:.1f} × {Z_TOP + LID_T:.1f} mm closed ·
       {'snap-fit' if SNAP_BITE > 0 else 'friction-fit'} lid · 4 parts, no supports</p>
    <p><a class="btn" href="case/preview.html">Interactive 3D preview</a></p>
    <details open><summary>STL downloads</summary><ul>{stls}</ul></details>
  </article>
  <article>
    <a href="case/docs/perfboard-layout.png"><img loading="lazy" src="case/docs/perfboard-layout.png"
         alt="Perfboard layout with every component, pin name and wire"></a>
    <h2>Build it</h2>
    <p class="geo">50 × 50 mm single-sided perfboard ({PCB_COLS} × {PCB_ROWS} holes) ·
       ESP32-C3 Super Mini · SSD1306 128 × 32 · TP4056 · 503450 LiPo</p>
    <ul class="links">
      <li><a href="case/docs/perfboard-layout.png">Perfboard layout</a>
          (<a href="{PCB_URL}">Özdisan 5x5 perfboard</a>)</li>
      <li><a href="case/docs/wiring.png">Wiring block schematic</a></li>
      <li><a href="{REPO_URL}#bill-of-materials">Bill of materials, wiring table, assembly (README)</a></li>
    </ul>
  </article>
  <article>
    <a href="case/docs/wiring.png"><img loading="lazy" src="case/docs/wiring.png"
         alt="Wiring block schematic: power path and signals"></a>
    <h2>Firmware</h2>
    <p class="geo">Same behaviour in both: click counts on release, hold both to
       reset, 60 s idle → deep sleep, count kept in flash</p>
    <ul class="links">
      <li><a href="{REPO_URL}/tree/main/firmware/plain">firmware/plain/</a> — PlatformIO + Arduino, no radio</li>
      <li><a href="{REPO_URL}/tree/main/firmware/esphome">firmware/esphome/</a> — ESPHome, Home Assistant entities</li>
      <li><a href="{REPO_URL}#flashing">Flashing from the browser (README)</a></li>
    </ul>
  </article>
  </div>
  <footer>Code: MIT · Models &amp; images: CC BY 4.0 ·
    <a href="{REPO_URL}">{REPO_URL.split('//')[1]}</a></footer>
</main>
</body>
</html>
"""
    out = os.path.join(HERE, os.pardir, "index.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"  {'../index.html':24s} ({os.path.getsize(out) / 1e3:.1f} kB landing page)")


derive()

if __name__ == "__main__":
    main()
