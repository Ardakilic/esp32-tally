#!/usr/bin/env python3
"""Verify the tally case without a printer: rebuilds every part IN MEMORY
(never touches stl/) and measures the finished meshes — bounding boxes, cross-
sections, ray casts, boolean overlaps — against the constants in generate.py.
Exits 1 on any failure.

Usage:  python3 tools/verify.py [-v] [generate.py flags]

  -v   also list every passing check with its measured value

Every fit override of generate.py is accepted, so a tuned build can be
verified the same way it is generated:
  ... python3 tools/verify.py --clear-friction 0.32 --tact-height 4.3
  ... python3 tools/verify.py --omit-engraving
  ... python3 tools/verify.py --snap-bite 0      (plain friction lid, no detents)

Needs the ray-cast extras on top of requirements.txt — see requirements-dev.txt
(the documented verify command installs them into a throwaway container).
"""

import argparse
import importlib.util
import os
import sys
import time
import warnings

import numpy as np
import trimesh
from shapely.geometry import Point, Polygon, box as shp_box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import generate as g  # noqa: E402  (has a __main__ guard — importing is free)

TOL = 0.01      # mm — fit dimensions must hit their constant this closely
BBOX_TOL = 1.0  # mm — outer bounding boxes vs the expected envelope
EPS = 0.05      # mm — shrink ghost boxes so touching faces don't count as inside


class Report:
    """Collects (scope, check, ok, detail) rows."""

    def __init__(self):
        self.rows = []
        self.scope = None

    def check(self, name, ok, detail=""):
        self.rows.append((self.scope, name, bool(ok), detail))

    def near(self, name, value, want, tol=TOL, unit="mm"):
        self.check(name, abs(value - want) <= tol, f"{value:.3f} {unit} (want {want:.3f})")

    def at_least(self, name, value, want, unit="mm"):
        self.check(name, value >= want - TOL, f"{value:.3f} {unit} (need >= {want:.3f})")


# --------------------------------------------------------------------------
# measuring helpers
# --------------------------------------------------------------------------


def section(mesh, z):
    """XY cross-section at height z as shapely polygons (world coordinates)."""
    sec = mesh.section(plane_origin=[0.0, 0.0, float(z)], plane_normal=[0.0, 0.0, 1.0])
    if sec is None:
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        planar, _ = sec.to_planar(to_2D=np.eye(4))
    geom = unary_union(list(planar.polygons_full))
    return [p for p in getattr(geom, "geoms", [geom]) if p.geom_type == "Polygon"]


def cut(mesh, origin, normal):
    """3D vertices of the mesh's outline in an arbitrary plane."""
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    return sec.vertices if sec is not None else np.zeros((0, 3))


def wall_strip(c, n, u0, u1, a):
    """Axis-aligned XY box beside a wall: u0..u1 out from point c along the
    (axis-aligned) outward normal n, +-a along the wall."""
    xs, ys = zip(*[(c[0] + n[0] * u + abs(n[1]) * s, c[1] + n[1] * u + abs(n[0]) * s)
                   for u in (u0, u1) for s in (-a, a)])
    return shp_box(min(xs), min(ys), max(xs), max(ys))


def reach(geom, n):
    """How far a shapely geometry extends along the axis-aligned direction n."""
    x0, y0, x1, y1 = geom.bounds
    return max(n[0] * x0 + n[1] * y0, n[0] * x1 + n[1] * y1)


def hits(mesh, origin, direction):
    """Every surface point a ray from origin along direction crosses."""
    loc, _, _ = mesh.ray.intersects_location(
        np.array([origin], dtype=float), np.array([direction], dtype=float), multiple_hits=True)
    return loc


def overlap(a, b):
    """Volume two meshes share, mm3."""
    with warnings.catch_warnings():  # an empty result divides by zero volume
        warnings.simplefilter("ignore")
        m = trimesh.boolean.intersection([a, b], check_volume=False)
        return 0.0 if m.is_empty or len(m.faces) == 0 else abs(m.volume)


def corners(b):
    x0, y0, z0, x1, y1, z1 = b
    return [(x, y, z) for x in (x0 + EPS, x1 - EPS) for y in (y0 + EPS, y1 - EPS)
            for z in (z0 + EPS, z1 - EPS)]


def extents(mesh):
    return mesh.bounds[1] - mesh.bounds[0]


def width_of(poly):
    x0, y0, x1, y1 = poly.bounds
    return x1 - x0, y1 - y0


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------


def verify():
    rep = Report()
    rep.scope = "params"
    rep.at_least("LID_CLEAR >= TACT_H + 1.5 (cap flange + play)", g.LID_CLEAR, g.TACT_H + 1.5)
    rep.at_least("PCB_Z >= BAT_T + 2.0 (solder-side clearance)", g.PCB_Z, g.BAT_T + 2.0)
    rep.at_least("ledge X >= LEDGE_MIN", (g.CAV_W - g.OPEN_W) / 2, g.LEDGE_MIN)
    rep.at_least("ledge Y >= LEDGE_MIN", (g.CAV_L - g.OPEN_L) / 2, g.LEDGE_MIN)
    rep.at_least("lid clears the OLED cover", g.LID_CLEAR, g.OLED_COVER_TOP + 0.3)
    rep.at_least("lid clears the ESP32 USB-C", g.LID_CLEAR,
                 g.ESP_STANDOFF + g.ESP_PCB_T + g.ESP_USB_H + 0.3)

    parts = {name: g.build(name) for name in g.PARTS}
    base, lid = parts["base"], parts["lid"]
    boxes = g.component_boxes()
    seated_caps = {f"cap-{s}": g.build_cap(s).apply_translation([*xy, 0.0])
                   for s, xy in zip(("minus", "plus"), g.TACT_XY)}

    for name, mesh in parts.items():
        rep.scope = name
        rep.check("watertight", mesh.is_watertight, f"{len(mesh.faces)} faces")

    rep.scope = "base"
    for axis, want in zip("XYZ", (g.OUT_W, g.OUT_L, g.Z_TOP)):
        rep.near(f"outer {axis}", extents(base)["XYZ".index(axis)], want, tol=BBOX_TOL)
    # USB-C openings: a ray along +Y at each receptacle centre must cross
    # nothing inside the Y- wall (the first thing it may hit is the far wall)
    usb = {"ESP32 USB-C": (boxes["esp32-usb"], -g.OPEN_L / 2),
           "TP4056 USB-C": (boxes["tp4056-usb"], -g.CAV_L / 2)}
    for name, (b, inner_face) in usb.items():
        c = ((b[0] + b[3]) / 2, (b[2] + b[5]) / 2)
        h = hits(base, (c[0], -g.OUT_L / 2 - 5.0, c[1]), (0.0, 1.0, 0.0))
        in_wall = h[h[:, 1] < inner_face + 0.1] if len(h) else h
        rep.check(f"{name} opening clear through the Y- wall", len(in_wall) == 0,
                  f"{len(in_wall)} surfaces hit inside the wall")
    # ESP32 USB-C plug relief: beside the slot, a ray along +Y crosses the thin
    # wall (relief face -> inner clearance pocket); the receptacle face must
    # sit at most 0.3 mm behind the relief face a plug butts against
    b = boxes["esp32-usb"]
    h = hits(base, (g.ESP_X + g.USB_CUT_W / 2 + 1.0, -g.OUT_L / 2 - 5.0, (b[2] + b[5]) / 2),
             (0.0, 1.0, 0.0))
    ys = sorted(h[:, 1]) if len(h) > 1 else [-g.OUT_L / 2, -g.OPEN_L / 2]
    rep.at_least("ESP32 USB-C wall beside the slot >= 1.2", ys[1] - ys[0], 1.2)
    rep.near("ESP32 USB-C wall = USB_WALL_T", ys[1] - ys[0], g.USB_WALL_T)
    rep.check("ESP32 USB-C face recess <= 0.3 behind the relief face", -0.05 <= b[1] - ys[0] <= 0.3,
              f"{b[1] - ys[0]:.2f} mm (derived ESP_USB_RECESS {g.ESP_USB_RECESS:.2f})")
    h = hits(base, (g.OUT_W / 2 + 5.0, g.SW_Y, g.FLOOR + g.SW_H / 2), (-1.0, 0.0, 0.0))
    in_wall = h[h[:, 0] > g.CAV_W / 2 - 0.1] if len(h) else h
    rep.check("switch slot clear through the X+ wall", len(in_wall) == 0,
              f"{len(in_wall)} surfaces hit inside the wall")
    # battery and TP4056 lie inside the cavity: no corner inside the base solid,
    # and within the cavity envelope (the TP's USB end may sit in its pocket)
    for name, (xlo, ylo) in (("battery", (-g.CAV_W / 2, -g.CAV_L / 2)),
                             ("tp4056", (-g.CAV_W / 2, g.TP_Y0))):
        b = boxes[name]
        inside = base.contains(np.array(corners(b)))
        envelope = (b[0] >= xlo - TOL and b[1] >= ylo - TOL and b[3] <= g.CAV_W / 2 + TOL
                    and b[4] <= g.CAV_L / 2 + TOL and b[2] >= g.FLOOR - TOL
                    and b[5] <= g.Z_LEDGE + TOL)
        rep.check(f"{name} inside the cavity", not inside.any() and envelope,
                  f"{int(inside.sum())}/8 corners in the base solid")
    for name, b in boxes.items():
        v = overlap(base, g.bbox(*b))
        rep.check(f"{name} does not intersect the base", v < 1e-6, f"{v:.3f} mm3 overlap")
    rep.near("switch pocket between ribs", g.SW_L + 0.4, 2 * (g.SW_L / 2 + 0.2))

    rep.scope = "lid"
    for axis, want in zip("XYZ", (g.OUT_W, g.OUT_L, g.LID_T + g.LID_CLEAR)):
        rep.near(f"outer {axis}", extents(lid)["XYZ".index(axis)], want, tol=BBOX_TOL)
    rep.near("skirt bottom lands on the perfboard top", lid.bounds[0][2], g.PCB_TOP)
    skirt = max(section(lid, g.Z_TOP - g.LID_CLEAR / 2), key=lambda p: p.area)
    sw, sl = width_of(skirt)
    rep.near("skirt outer X = opening - 2 x clearance", sw, g.OPEN_W - 2 * g.CLEAR_FRICTION)
    rep.near("skirt outer Y = opening - 2 x clearance", sl, g.OPEN_L - 2 * g.CLEAR_FRICTION)
    h = hits(lid, (-g.OUT_W / 2 - 5.0, 0.0, g.Z_TOP - g.LID_CLEAR / 2), (1.0, 0.0, 0.0))
    xs = sorted(h[:, 0])
    rep.near("skirt wall thickness", xs[1] - xs[0] if len(xs) > 1 else 0.0, g.SKIRT_T)
    for name, xy in (("window", g.WIN_XY), ("cap hole left", g.TACT_XY[0]),
                     ("cap hole right", g.TACT_XY[1])):
        h = hits(lid, (xy[0], xy[1], g.Z_TOP + g.LID_T + 5.0), (0.0, 0.0, -1.0))
        rep.check(f"{name} open through the plate", len(h) == 0, f"{len(h)} surfaces hit")
    plate = max(section(lid, g.Z_TOP + g.LID_T / 2), key=lambda p: p.area)
    holes = [Polygon(r) for r in plate.interiors
             if any(Polygon(r).contains(Point(xy)) for xy in g.TACT_XY)]
    hole_d = min(width_of(h)[0] for h in holes) if holes else 0.0
    rep.near("cap hole diameter", hole_d, g.CAP_HOLE_D, tol=0.05)
    h = hits(lid, (g.ESP_X, (-g.OUT_L / 2 + g.USB_RELIEF_Y) / 2, g.Z_TOP + g.LID_T + 5.0), (0.0, 0.0, -1.0))
    rep.check("plate notched over the USB-C plug relief", len(h) == 0, f"{len(h)} surfaces hit")
    for name, b in boxes.items():
        if b[5] > g.PCB_TOP - TOL:  # only what rises above the perfboard can touch the lid
            v = overlap(lid, g.bbox(*b))
            rep.check(f"{name} does not intersect the lid", v < 1e-6, f"{v:.3f} mm3 overlap")
    # engraving: a recess ENGRAVE_DEPTH into the top, inside the free band
    top = g.Z_TOP + g.LID_T
    geom, cap = g.engraving_geometry()
    if geom is None:
        h = hits(lid, (*g.ENGRAVE_XY, top + 5.0), (0.0, 0.0, -1.0))
        rep.near("engraving omitted: plain top at ENGRAVE_XY", h[:, 2].max() if len(h) else 0.0, top)
    else:
        text, g.ENGRAVE_TEXT = g.ENGRAVE_TEXT, None
        plain = g.build_lid()
        g.ENGRAVE_TEXT = text
        dv, want = (plain.volume - lid.volume) / 1000.0, geom.area * g.ENGRAVE_DEPTH / 1000.0
        rep.check("engraving removes text area x depth (and < 1 cm3)",
                  abs(dv - want) <= 0.05 * want and dv < 1.0, f"{dv:.3f} cm3 (want {want:.3f})")
        pt = geom.representative_point()
        h = hits(lid, (pt.x, pt.y, top + 5.0), (0.0, 0.0, -1.0))
        rep.near("engraving depth", top - (h[:, 2].max() if len(h) else 0.0), g.ENGRAVE_DEPTH)
        rep.check("engraving cap height <= ENGRAVE_H (auto-shrink)", cap <= g.ENGRAVE_H + TOL, f"{cap:.2f} mm")
        bb = shp_box(*geom.bounds)
        inside = shp_box(-g.OUT_W / 2 + g.WALL, -g.OUT_L / 2 + g.WALL, g.OUT_W / 2 - g.WALL,
                         g.OUT_L / 2 - g.WALL).contains(bb)
        rep.check("engraving inside the plate footprint", inside, f"bbox {[round(v, 1) for v in geom.bounds]}")
        clear = min([bb.distance(Point(xy)) - g.CAP_HOLE_D / 2 for xy in g.TACT_XY]
                    + [bb.distance(shp_box(g.WIN_XY[0] - g.WIN_W / 2, g.WIN_XY[1] - g.WIN_L / 2,
                                           g.WIN_XY[0] + g.WIN_W / 2, g.WIN_XY[1] + g.WIN_L / 2))])
        rep.at_least("engraving clear of the cap holes and window by 2", clear, 2.0)

    for name, cap in seated_caps.items():
        rep.scope = name
        stem = max(section(cap, g.Z_TOP + g.LID_T / 2), key=lambda p: p.area)
        stem_d = width_of(stem)[0]
        rep.check("stem diameter < lid hole", stem_d < hole_d - TOL,
                  f"stem {stem_d:.3f} vs hole {hole_d:.3f}")
        flange = max(section(cap, g.PCB_TOP + g.TACT_H + g.CAP_FLANGE_T / 2), key=lambda p: p.area)
        rep.near("flange diameter", width_of(flange)[0], g.CAP_FLANGE_D, tol=0.05)
        rep.near("flange top below the lid plate", g.Z_TOP - (cap.bounds[0][2] + g.CAP_FLANGE_T), 0.3)
        rep.near("stem proud of the lid", cap.bounds[1][2] - g.SYMBOL_H - (g.Z_TOP + g.LID_T), 1.0)
        v = overlap(lid, cap)
        rep.check("seated cap does not intersect the lid", v < 1e-6, f"{v:.3f} mm3 overlap")
    rep.scope = "caps"
    rep.check("plus cap has more material than minus (two bars vs one)",
              parts["cap-plus"].volume > parts["cap-minus"].volume + 1.0,
              f"{parts['cap-plus'].volume:.1f} vs {parts['cap-minus'].volume:.1f} mm3")

    rep.scope = "snap"
    # against the no-snap twins built in-process: the detents must add exactly
    # the four bump prisms to the lid and take exactly the four grooves out of
    # the base, nothing else — and with --snap-bite 0 both parts must be
    # identical to the plain build (to 1e-3 mm3 = 1e-6 cm3)
    bite = g.SNAP_BITE
    g.SNAP_BITE = 0.0
    g.derive()
    plain_lid, plain_base = g.build_lid(), g.build_base()
    g.SNAP_BITE = bite
    g.derive()
    sites = g.SNAP_SITES if bite > 0 else ()
    depth_want = bite + g.SNAP_GROOVE_CLEAR
    bump_v = (g.SNAP_P + g.SNAP_CREST) * g.SNAP_P * g.SNAP_LEN  # trapezoid profile x length
    groove_v = depth_want * (g.SNAP_LEN + 1.0) * (g.SNAP_Z[1] - g.SNAP_Z[0] + 0.4)
    for what, dv, want in (("lid - no-snap lid = the bumps", lid.volume - plain_lid.volume, len(sites) * bump_v),
                           ("no-snap base - base = the grooves", plain_base.volume - base.volume,
                            len(sites) * groove_v)):
        rep.check(what if sites else what.split(" = ")[0] + " = 0 (identical)",
                  abs(dv - want) <= max(0.01 * want, 1e-3), f"{dv:.3f} mm3 (want {want:.3f})")
    # per site: a horizontal section through the crest gives the bump (what the
    # lid has beyond its skirt face) and the groove (what the frame lacks behind
    # its inner face); a vertical section across the wall gives their Z ranges
    z_mid = sum(g.SNAP_Z) / 2
    lid_cut = unary_union(section(lid, z_mid)) if sites else None
    base_cut = unary_union(section(base, z_mid)) if sites else None
    for n, c in sites:
        side = "XY"[n[0] == 0] + "-+"[n[0] + n[1] > 0]
        n3, c3 = np.array([*n, 0.0]), np.array([*c, 0.0])
        face = n3 @ c3  # the frame's inner face, measured along n
        along = 1 if n[0] else 0  # the axis running along this wall
        bump = lid_cut.intersection(wall_strip(c, n, -g.CLEAR_FRICTION + 0.02, g.SNAP_P + 1.0, g.SNAP_LEN))
        groove = wall_strip(c, n, 0.02, depth_want + 1.0, g.SNAP_LEN).difference(base_cut)
        behind = base_cut.intersection(wall_strip(c, n, depth_want + 0.02, 20.0, g.SNAP_LEN))
        depth = reach(groove, n) - face
        rep.near(f"{side} bump crest = CLEAR_FRICTION + SNAP_BITE", reach(bump, n) - (face - g.CLEAR_FRICTION),
                 g.SNAP_P, tol=0.02)
        rep.near(f"{side} groove depth = SNAP_BITE + SNAP_GROOVE_CLEAR", depth, depth_want, tol=0.02)
        rep.at_least(f"{side} wall behind the groove >= SNAP_MIN_WALL", reach(behind, n) - face - depth,
                     g.SNAP_MIN_WALL)
        b_lo, b_hi = bump.bounds[along], bump.bounds[along + 2]
        g_lo, g_hi = groove.bounds[along], groove.bounds[along + 2]
        rep.at_least(f"{side} seated: bump inside the groove along the wall by >= 0.5",
                     min(b_lo - g_lo, g_hi - b_hi), 0.5)
        # vertical section (plane normal = along the wall) through the centre.
        # Points off the skirt face lie on the bump's 45 deg ramps or crest, so
        # z - u / z + u are its lower / upper roots on the face (exact at the
        # crest corners); points on the face itself are triangulation noise
        pts = cut(lid, c3, np.cross(n3, [0.0, 0.0, 1.0]))
        u, z = pts @ n3 - (face - g.CLEAR_FRICTION), pts[:, 2]
        sel = (u > 1e-3) & (u < g.SNAP_P + 1.0) & (z > g.PCB_TOP + 0.01) & (z < g.Z_TOP - 0.01)
        bz = ((z - u)[sel].min(), (z + u)[sel].max()) if sel.any() else (0.0, 0.0)
        pts = cut(base, c3, np.cross(n3, [0.0, 0.0, 1.0]))
        u, z = pts @ n3 - face, pts[:, 2]
        wall = (u > -1e-3) & (u < depth_want + 1.0) & (z > g.Z_LEDGE + 0.01)
        sel = wall & (u > 1e-3) & (z < g.Z_TOP - 0.01)  # the groove's bottom face
        gz = (z[sel].min(), z[sel].max()) if sel.any() else (0.0, 0.0)
        top = z[wall].max() if wall.any() else 0.0  # Z_TOP, or the pry notch floor
        rep.at_least(f"{side} groove closed: solid above it >= 1.5", top - gz[1], 1.5)
        rep.at_least(f"{side} groove top >= 3 below Z_TOP", g.Z_TOP - gz[1], 3.0)
        rep.check(f"{side} groove bottom above the PCB top", gz[0] > g.PCB_TOP + TOL,
                  f"Z {gz[0]:.2f} vs PCB top {g.PCB_TOP:.2f}")
        rep.at_least(f"{side} seated: bump Z {bz[0]:.2f}..{bz[1]:.2f} inside groove Z "
                     f"{gz[0]:.2f}..{gz[1]:.2f} by >= 0.15", min(bz[0] - gz[0], gz[1] - bz[1]), 0.15)
        if n[1] < 0:  # the Y- wall carries the ESP32 USB-C relief and the skirt notch
            notch = g.ESP_X + g.SKIRT_NOTCH_W / 2
            rep.at_least("Y- groove clear of the USB relief by >= 1", g_lo - notch, 1.0)
            rep.at_least("Y- bump clear of the skirt notch by >= 1", b_lo - notch, 1.0)
            rep.at_least("Y- bump clear of the skirt corner by >= 1", g.SKIRT_W / 2 - b_hi, 1.0)
    return rep.rows


def main(argv=None):
    own = argparse.ArgumentParser(add_help=False)
    own.add_argument("-v", "--verbose", action="store_true")
    opts, gen_args = own.parse_known_args(argv)
    if "-h" in gen_args or "--help" in gen_args:
        print(__doc__)
    g.apply_printer_args(gen_args)  # the overrides (also answers --help)
    missing = [m for m in ("rtree", "scipy", "networkx") if importlib.util.find_spec(m) is None]
    if missing:
        sys.exit(f"verify.py needs {', '.join(missing)}: pip install -r requirements-dev.txt")
    print(f"tolerances — {g.tolerance_summary()}")
    print(f"shell — {g.shell_summary()}\n")
    started = time.time()
    rows = verify()
    failed = 0
    for scope in dict.fromkeys(r[0] for r in rows):
        mine = [r for r in rows if r[0] == scope]
        bad = [r for r in mine if not r[2]]
        failed += len(bad)
        print(f"  {scope:12s} {'FAIL' if bad else 'PASS'}  {len(mine) - len(bad)}/{len(mine)}")
        for _, name, ok, detail in (mine if opts.verbose else bad):
            print(f"      {'ok  ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
    print(f"\nverify: {len(rows)} checks — {'ALL PASS' if not failed else f'{failed} FAILED'} "
          f"({time.time() - started:.0f} s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
