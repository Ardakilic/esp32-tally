#!/usr/bin/env python3
"""Render the README images — software renderer via matplotlib, no GPU/browser:

  docs/renders.png           closed case + exploded view with ghost electronics
  docs/perfboard-layout.png  the 50 x 50 (18 x 19 hole) perfboard from above
                             with every component, pin name and wire
  docs/wiring.png            block schematic (power path + signals)

Usage:  python3 tools/render_docs.py [generate.py flags]
"""

import os
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import generate as g  # noqa: E402  (has a __main__ guard — importing is free)

DOCS = os.path.join(ROOT, "docs")
GRAY, BLUE, CAP = "#9aa2ad", "#5f8cc4", "#e0a040"
GHOSTS = {  # component box -> translucent colour
    "perfboard": (0.75, 0.55, 0.20, 0.45), "battery": (0.35, 0.65, 0.85, 0.45),
    "tp4056": (0.85, 0.35, 0.35, 0.55), "tp4056-usb": (0.4, 0.4, 0.4, 0.7),
    "esp32": (0.2, 0.2, 0.2, 0.55), "esp32-usb": (0.4, 0.4, 0.4, 0.7),
    "oled": (0.2, 0.3, 0.6, 0.55), "oled-glass": (0.1, 0.1, 0.1, 0.7),
    "switch": (0.9, 0.9, 0.9, 0.9),
}


def show(ax, meshes_cols, elev=28, azim=-55):
    """Flat-shaded render with global painter depth sort (RGBA colours ok)."""
    tris, cols = [], []
    light = np.array([0.35, -0.45, 0.82])
    light /= np.linalg.norm(light)
    for mesh, color in meshes_cols:
        v, f = trimesh.remesh.subdivide_to_size(
            mesh.vertices.astype(np.float64), mesh.faces, max_edge=8.0)
        m = trimesh.Trimesh(v, f)
        shade = 0.5 + 0.5 * np.clip(m.face_normals.astype(np.float64) @ light, 0, 1)
        rgba = np.array(matplotlib.colors.to_rgba(color))
        c = np.tile(rgba, (len(m.faces), 1))
        c[:, :3] = np.clip(shade[:, None] * rgba[None, :3], 0, 1)
        tris.append(m.vertices[m.faces])
        cols.append(c)
    tri, col = np.concatenate(tris), np.concatenate(cols)
    e, a = np.radians(elev), np.radians(azim)
    view = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    order = np.argsort(tri.mean(axis=1) @ view)
    ax.add_collection3d(
        Poly3DCollection(tri[order], facecolors=col[order], edgecolors="none"))
    lo, hi = tri.reshape(-1, 3).min(0), tri.reshape(-1, 3).max(0)
    c, r = (lo + hi) / 2, (hi - lo).max() / 2 * 0.9
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))
    ax.set_proj_type("ortho")
    ax.set_axis_off()
    ax.view_init(elev=elev, azim=azim)


def moved(m, dx=0.0, dy=0.0, dz=0.0):
    c = m.copy()
    c.apply_translation([dx, dy, dz])
    return c


def box_mesh(b):
    return g.bbox(*b)


def render_case(out_path):
    base, lid = g.build_base(), g.build_lid()
    caps = [moved(g.build_cap(s), *xy) for s, xy in zip(("minus", "plus"), g.TACT_XY)]
    closed = [(base, GRAY), (lid, BLUE)] + [(c, CAP) for c in caps]
    ghosts = [(box_mesh(b), GHOSTS[n]) for n, b in g.component_boxes().items() if n in GHOSTS]
    exploded = ([(base, GRAY)] + ghosts + [(moved(c, dz=12.0), CAP) for c in caps]
                + [(moved(lid, dz=25.0), BLUE)])
    fig = plt.figure(figsize=(11, 6), dpi=130)
    ax = fig.add_subplot(1, 2, 1, projection="3d")
    show(ax, closed)
    ax.set_title(f"closed — {g.OUT_W:.0f} x {g.OUT_L:.0f} x {g.Z_TOP + g.LID_T:.1f} mm "
                 "(USB-C ports at the near end)", fontsize=10)
    ax = fig.add_subplot(1, 2, 2, projection="3d")
    show(ax, exploded)
    ax.set_title("exploded — lid +25, caps +12; perfboard, battery, TP4056, "
                 "ESP32, OLED as ghosts", fontsize=10)
    fig.patch.set_facecolor("white")
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print("saved", out_path)


# ESP32-C3 Super Mini pin names with the USB at Y-, board viewed from above.
# Left = col 3, right = col 9, rows 0..7 (0 = USB end). Verify on the silkscreen.
ESP_LEFT = ["GPIO5", "GPIO6", "GPIO7", "GPIO8", "GPIO9", "GPIO10", "GPIO20", "GPIO21"]
ESP_RIGHT = ["5V", "GND", "3V3", "GPIO4", "GPIO3", "GPIO2", "GPIO1", "GPIO0"]
OLED_PINS = ["GND", "VCC", "SCL", "SDA"]  # rows 14..17, the usual order — check
OLED_ROWS = range(14, 18)
TACT_ROWS = (10, 12)  # tact pins straddle the body on row 11
ESP_PIN = {**{n: (3, r) for r, n in enumerate(ESP_LEFT)},
           **{n: (9, r) for r, n in enumerate(ESP_RIGHT)}}
# wires: (from hole, to hole, label, colour, label position along the wire 0..1)
WIRES = [
    ((1, 15), ESP_PIN["3V3"], "VCC -> 3V3", "#d33", 0.5),
    ((1, 14), ESP_PIN["GND"], "GND", "#222", 0.5),
    ((1, 16), ESP_PIN["GPIO7"], "SCL -> GPIO7", "#2a2", 0.72),
    ((1, 17), ESP_PIN["GPIO6"], "SDA -> GPIO6", "#36c", 0.45),
    ((5, 10), ESP_PIN["GPIO4"], "DOWN -> GPIO4", "#a3c", 0.5),
    ((5, 12), ESP_PIN["GND"], "GND", "#222", 0.5),
    ((12, 10), ESP_PIN["GPIO3"], "UP -> GPIO3", "#c73", 0.5),
    ((12, 12), ESP_PIN["GND"], "GND", "#222", 0.5),
]


def render_layout(out_path):
    fig, ax = plt.subplots(figsize=(9, 10), dpi=130)
    hw, hl = g.PCB_W / 2, g.PCB_L / 2
    ax.add_patch(Rectangle((-hw, -hl), g.PCB_W, g.PCB_L, fc="#f3e6c4", ec="#8a6d2a", lw=1.5))
    for c in range(g.PCB_COLS):
        for r in range(g.PCB_ROWS):
            ax.add_patch(Circle(g.hole(c, r), 0.5, fc="white", ec="#b09a6a", lw=0.6))
    for c in range(g.PCB_COLS):
        ax.text(g.hole(c, 0)[0], -hl - 1.2, str(c), ha="center", va="top", fontsize=6, color="#777")
    for r in range(g.PCB_ROWS):
        ax.text(hw + 1.0, g.hole(0, r)[1], str(r), ha="left", va="center", fontsize=6, color="#777")
    boxes = g.component_boxes()

    def rect(name, **kw):
        x0, y0, _, x1, y1, _ = boxes[name]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, **kw))

    # ESP32 + its pins
    rect("esp32", fc=(0.2, 0.2, 0.2, 0.15), ec="#333", lw=1.2)
    rect("esp32-usb", fc=(0.5, 0.5, 0.5, 0.5), ec="#333", lw=0.8, hatch="///")
    for names, col, dx, ha in ((ESP_LEFT, 3, 1.1, "left"), (ESP_RIGHT, 9, -1.1, "right")):
        for r, n in enumerate(names):
            x, y = g.hole(col, r)
            ax.add_patch(Circle((x, y), 0.7, fc="#ffd", ec="#333", lw=1.0))
            ax.text(x + dx, y, n, ha=ha, va="center", fontsize=6.5, fontweight="bold")
    ax.text(g.ESP_X, boxes["esp32-usb"][1] - 1.0, "ESP32-C3 Super Mini (USB-C pokes through the wall)",
            ha="center", va="top", fontsize=7, color="#333")
    # tact switches: body + 4 pins (cols 2/5 and 12/15, rows 10/12)
    for side, cols, name in (("left", (2, 5), "DOWN (-)"), ("right", (12, 15), "UP (+)")):
        rect(f"tact-{side}", fc=(0.9, 0.6, 0.2, 0.35), ec="#a60", lw=1.2)
        for c in cols:
            for r in TACT_ROWS:
                ax.add_patch(Circle(g.hole(c, r), 0.7, fc="#fff", ec="#a60", lw=1.0))
        x, y = g.TACT_XY[0 if side == "left" else 1]
        ax.text(x, y - 4.5, name, ha="center", va="top", fontsize=7, fontweight="bold", color="#a60")
    # OLED: PCB, glass, active area, header
    rect("oled", fc=(0.2, 0.3, 0.6, 0.15), ec="#248", lw=1.2)
    rect("oled-glass", fc=(0.1, 0.1, 0.1, 0.5), ec="#111", lw=0.8)
    ax.add_patch(Rectangle((g.WIN_XY[0] - g.OLED_AA[0] / 2, g.WIN_XY[1] - g.OLED_AA[1] / 2),
                           *g.OLED_AA, fc="#9cf", ec="none", alpha=0.9))
    ax.text(g.WIN_XY[0], g.WIN_XY[1], "0.91\" OLED active area", ha="center", va="center", fontsize=6.5)
    for r, n in zip(OLED_ROWS, OLED_PINS):
        x, y = g.hole(1, r)
        ax.add_patch(Circle((x, y), 0.7, fc="#ffd", ec="#248", lw=1.0))
        ax.text(x + 1.1, y, n, ha="left", va="center", fontsize=6, fontweight="bold", color="#248")
    x, y = g.hole(1, OLED_ROWS[-1])
    ax.text(x, y + 1.6, "OLED header\n(check order)", ha="left", va="bottom", fontsize=6, color="#248")
    # wires
    for a, b, label, color, f in WIRES:
        (x0, y0), (x1, y1) = g.hole(*a), g.hole(*b)
        ax.plot([x0, x1], [y0, y1], color=color, lw=1.6, alpha=0.8, solid_capstyle="round")
        if label != "GND":
            ax.text(x0 + f * (x1 - x0), y0 + f * (y1 - y0) + 0.6, label, fontsize=6, color=color,
                    ha="center", va="bottom", rotation=np.degrees(np.arctan2(y1 - y0, x1 - x0)),
                    bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.5))
    # off-board power stubs (to the X+ edge; the TP4056 + switch live under the board)
    for pin, label in (("5V", "5V <- switch <- TP4056 OUT+"), ("GND", "GND <- TP4056 OUT-")):
        x, y = g.hole(*ESP_PIN[pin])
        ax.plot([x, hw + 4.0], [y, y], color="#d33" if pin == "5V" else "#222", lw=1.6, ls="--")
        ax.text(hw + 4.5, y, label, ha="left", va="center", fontsize=6.5, fontweight="bold")
    ax.set_xlim(-hw - 4, hw + 30)
    ax.set_ylim(-hl - 7, hl + 4)
    ax.set_aspect("equal")
    ax.set_xlabel("X (mm) — viewed from above, component side (the bare face; solder pads underneath)")
    ax.set_ylabel("Y (mm) — Y+ = display end")
    ax.set_title(f"Perfboard layout — {g.PCB_W:.0f} x {g.PCB_L:.0f} mm single-sided board, "
                 f"{g.PCB_COLS} x {g.PCB_ROWS} holes (Özdisan 5x5 perfboard, used whole).\n"
                 "GND wires black. ESP32 pin names: verify against your board's silkscreen", fontsize=9)
    ax.text(-hw, -hl - 5.5, f"Özdisan 5x5 perfboard: {g.PCB_URL}", fontsize=6, color="#777", va="top")
    ax.grid(alpha=0.15)
    fig.patch.set_facecolor("white")
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print("saved", out_path)


# block schematic: id -> (label, x, y, w, h, [(pin, side, frac)...]); frac runs 0..1 along the side
BLOCKS = {
    "Battery": ("Battery\n503450 LiPo", 2, 22, 14, 14, [("+", "r", 0.7), ("-", "r", 0.3)]),
    "TP4056": ("TP4056\nUSB-C charger", 24, 20, 18, 18, [("B+", "l", 0.72), ("B-", "l", 0.28),
                                               ("OUT+", "r", 0.72), ("OUT-", "r", 0.28),
                                               ("USB-C", "b", 0.5)]),
    "Slide switch": ("Slide switch\nSS12D00", 50, 30, 12, 8, [("in", "l", 0.5), ("out", "r", 0.5)]),
    "ESP32-C3": ("ESP32-C3\nSuper Mini", 70, 12, 18, 34, [("5V", "l", 0.92), ("GND", "l", 0.78),
                                              ("3V3", "l", 0.60), ("GPIO6 SDA", "l", 0.46),
                                              ("GPIO7 SCL", "l", 0.34), ("GPIO3", "r", 0.40),
                                              ("GPIO4", "r", 0.20), ("USB-C", "b", 0.5)]),
    "OLED": ("OLED 0.91\"\nSSD1306 I2C", 40, 2, 20, 10, [("VCC", "t", 0.2), ("GND", "t", 0.4),
                                                 ("SCL", "t", 0.6), ("SDA", "t", 0.8)]),
    "UP (+)": ("UP (+)", 96, 28, 10, 7, [("a", "l", 0.5), ("b", "r", 0.5)]),
    "DOWN (-)": ("DOWN (-)", 96, 14, 10, 7, [("a", "l", 0.5), ("b", "r", 0.5)]),
}
LINKS = [  # (block.pin, block.pin, colour)
    ("Battery.+", "TP4056.B+", "#d33"), ("Battery.-", "TP4056.B-", "#222"),
    ("TP4056.OUT+", "Slide switch.in", "#d33"), ("Slide switch.out", "ESP32-C3.5V", "#d33"),
    ("TP4056.OUT-", "ESP32-C3.GND", "#222"),
    ("ESP32-C3.3V3", "OLED.VCC", "#d33"), ("ESP32-C3.GND", "OLED.GND", "#222"),
    ("ESP32-C3.GPIO7 SCL", "OLED.SCL", "#2a2"), ("ESP32-C3.GPIO6 SDA", "OLED.SDA", "#36c"),
    ("ESP32-C3.GPIO3", "UP (+).a", "#c73"), ("ESP32-C3.GPIO4", "DOWN (-).a", "#a3c"),
]


def render_wiring(out_path):
    fig, ax = plt.subplots(figsize=(11, 6), dpi=130)
    pins = {}
    for name, (label, x, y, w, h, plist) in BLOCKS.items():
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4", fc="#eef2f7", ec="#334", lw=1.3))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=8.5, fontweight="bold")
        for pin, side, f in plist:
            px, py = {"l": (x, y + f * h), "r": (x + w, y + f * h),
                      "t": (x + f * w, y + h), "b": (x + f * w, y)}[side]
            pins[f"{name}.{pin}"] = (px, py)
            ax.plot(px, py, "o", ms=4, color="#334")
            off = {"l": (-0.8, 0, "right", "center"), "r": (0.8, 0, "left", "center"),
                   "t": (0, 0.8, "center", "bottom"), "b": (0, -0.8, "center", "top")}[side]
            ax.text(px + off[0], py + off[1], pin, ha=off[2], va=off[3], fontsize=7)
    for a, b, color in LINKS:
        (x0, y0), (x1, y1) = pins[a], pins[b]
        ax.plot([x0, x1], [y0, y1], color=color, lw=1.8, alpha=0.85)
    # the buttons' other legs go to GND
    for btn in ("UP (+)", "DOWN (-)"):
        x, y = pins[f"{btn}.b"]
        ax.plot([x, x + 3, x + 3], [y, y, 10], color="#222", lw=1.8, alpha=0.85)
    ax.text(pins["UP (+).b"][0] + 3, 9, "GND", ha="center", va="top", fontsize=7)
    ax.text(79, 6, "USB-C: flash / debug\n(5V pin = VBUS!)", ha="center", va="top", fontsize=7, color="#a00")
    ax.text(33, 16, "USB-C: charge", ha="center", va="top", fontsize=7)
    ax.text(55, 49, "Power: Battery -> TP4056 B+/B- ; OUT+ -> switch -> ESP32 5V ; OUT- -> GND\n"
            "Signals: 3V3/GND/GPIO6 SDA/GPIO7 SCL -> OLED ; GPIO3 (UP) and GPIO4 (DOWN) -> "
            "buttons -> GND (internal pull-ups)", ha="center", va="bottom", fontsize=8)
    ax.text(55, -6, "WARNING: switch OFF before plugging the ESP32's own USB-C — its 5V pin is "
            "wired straight to USB VBUS,\nso with the switch ON the PC's 5 V would back-feed "
            "the TP4056 output.", ha="center", va="center", fontsize=8.5, fontweight="bold",
            color="#a00", bbox=dict(boxstyle="round,pad=0.6", fc="#fff3f3", ec="#a00", lw=1.5))
    ax.set_xlim(-2, 112)
    ax.set_ylim(-12, 56)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title("Tally counter wiring", fontsize=11)
    fig.patch.set_facecolor("white")
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print("saved", out_path)


def main():
    g.apply_printer_args()
    os.makedirs(DOCS, exist_ok=True)
    render_case(os.path.join(DOCS, "renders.png"))
    render_layout(os.path.join(DOCS, "perfboard-layout.png"))
    render_wiring(os.path.join(DOCS, "wiring.png"))


if __name__ == "__main__":
    main()
