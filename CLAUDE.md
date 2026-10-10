# CLAUDE.md — ESP32 Tally Counter

Handheld tally counter: ESP32-C3 Super Mini + 0.91" SSD1306 OLED + two 6 × 6 tact
switches + TP4056 + 503450 LiPo + SS12D00 slide switch on a 50 × 50 mm Özdisan
single-sided 18 × 19-hole perfboard (used whole), in a 58.0 × 57.6 × 22.1 mm
printed case with "Grindarr" engraved in the lid. Two firmwares (plain
PlatformIO, ESPHome) implement identical behaviour. Everything — STLs, README
images, the 3D preview, the Pages index, both binaries — is **generated** through
Docker + make; nothing is installed on the host and no generated file is ever
hand-edited. License: MIT for code (`LICENSE`), CC BY 4.0 for models/images
(`LICENSE-MODELS`). GitHub Pages (`ardakilic.github.io/esp32-tally`) republishes
the whole checkout on every push to `main` via `.github/workflows/pages.yml`
(configure-pages/upload-pages-artifact/deploy-pages; Pages source = Actions,
enabled once by hand).

## Layout

```
Makefile                       canonical build: every target is a `docker run`
firmware/plain/                PlatformIO + Arduino 3.3.12 (pioarduino 55.03.312-1), U8g2 2.36.18
  src/tally_logic.h            pure C++ state machine (debounce, clamp, both-held reset)
  src/main.cpp                 pins, U8g2, Preferences/NVS (written per click), deep sleep,
                               seeded button state, GPIO8 boot blink, serial boot banner
  test/tally_logic_test.cpp    assert self-test, runs in gcc:14 — the committed test
  Dockerfile                   python:3.12-slim + platformio 6.2.0 + git, PLATFORMIO_CORE_DIR=/pio
  build/tally-plain.factory.bin  output (gitignored with .pio/)
firmware/esphome/tally.yaml    ESPHome 2026.9.1, esp-idf; secrets.yaml (gitignored) from .example
  .esphome/build/tally/build/firmware.{factory,ota}.bin   outputs (gitignored)
case/generate.py               constants with why-comments + derive() + build(part) -> 4 STLs
                               + build_preview() -> case/preview.html + build_index() -> index.html
case/Dockerfile                python:3.14-slim + fonts-liberation (engraving font) + requirements.txt
case/preview_template.html     template for the self-contained three.js preview (filtarr's)
case/tools/render_docs.py      README images (matplotlib software renders), same flags
case/tools/verify.py           105 checks on in-memory builds (70 with --snap-bite 0, 101 with
                               --omit-engraving), exit 1 on failure, same flags
case/tools/fetch_three.py      stdlib-only three.js downloader (`make vendor`, bare python image)
case/vendor/                   three.module.min.js + three.core.min.js + THREE_VERSION (committed)
case/stl/, case/docs/          COMMITTED outputs — regenerate, never edit
case/preview.html, index.html  COMMITTED outputs too (preview + Pages landing page) — never edit
.github/workflows/pages.yml    publishes the whole checkout to GitHub Pages on push to main
case/requirements*.txt         pinned (==) — a floating stack re-triangulates every STL
```

## Commands

```bash
make                 # case + plain + esphome
make case            # image-case, generate.py, render_docs.py -> case/stl, case/preview.html,
                     # index.html, case/docs
make case-verify     # verify.py in a throwaway container (requirements-dev.txt extras)
make vendor          # refresh both three.js files in case/vendor/ (bare python:3.14-slim)
make plain           # pio run -> firmware/plain/build/tally-plain.factory.bin (403 KiB)
make plain-test      # host self-test, prints OK
make esphome         # compile; fails with a message if secrets.yaml is missing
make esphome-config  # validate only
make esphome-ota     # DEVICE ?= tally.local — turn on "Keep Awake" in HA first
make clean           # case/stl case/docs case/preview.html index.html .pio build .esphome (volumes stay)
make case GEN_ARGS="--clear-friction 0.32 --tact-height 4.3 --battery 30x40x5"
make case GEN_ARGS="--snap-bite 0.3"   # PLA lid; 0 = no detents (plain friction fit)
make case ENGRAVING="My Text"   # appends --engraving "My Text" to GEN_ARGS
make case OMIT_ENGRAVING=1      # appends --omit-engraving (plain lid top)
```

Expected results: verify `105 checks — ALL PASS` (70 with `--snap-bite 0`, 101 with
`--omit-engraving`);
plain RAM 4.6 % / Flash 25.2 %;
ESPHome Flash 51 % / RAM 33 %, factory bin 983 KB.

## Technology decisions (and why)

- **pioarduino, not `platformio/espressif32`**: the official platform is still
  Arduino 2.x and has no `nologo_esp32c3_super_mini` board; pioarduino
  55.03.312-1 = Arduino core 3.3.12 on ESP-IDF 5.5. Pinned by release-zip URL.
  `board_build.flash_mode = dio` — the default qio fails to boot on some clones.
  pioarduino emits `firmware.factory.bin` (bootloader 0x0 + partitions 0x8000 +
  boot_app0 0xe000 + app 0x10000) itself; `make plain` only copies it.
- **ESPHome on `esp-idf`**: ESPHome's recommended framework for the C3; the
  deep-sleep/GPIO-wake code calls IDF directly anyway, and it builds smaller than
  the Arduino wrapper. `reboot_timeout: 0s` on wifi and api — the counter must
  keep working with no Wi-Fi/HA.
- **U8g2 as the single plain-build dependency**: one lib for SSD1306 128 × 32 over
  hardware I2C plus a 28 px numeric font (`logisoso28_tn`); no GFX + BusIO pair.
- **shapely + trimesh + manifold3d, not CadQuery/OpenSCAD**: the filtarr stack —
  2D outlines → extrude → booleans, same Dockerfile pattern, pinned so STL bytes
  are reproducible. The "+"/"−" cap symbols are rectangles; the only text is the
  lid engraving, Liberation Sans Bold via matplotlib's `TextPath` (filtarr's
  mechanism), the font from the image's `fonts-liberation` — the one apt package
  left unpinned, so a font change re-triangulates only `tally-lid.stl`.
- **Snap-fit lid** (no screws, no magnets, no hardware): the skirt slides *inside*
  the frame (0.28 mm/side, filtarr's calibrated value) and clamps the perfboard on
  the ledge; four 8 mm detents on the skirt's outer face click into closed grooves
  in the frame, so a handheld counter picked up by the lid or turned over keeps
  it on. Snaps over magnets/screws: nothing to buy, glue or thread into a 2 mm
  wall, and with 45° ramps both ways the lid still releases at the existing pry
  notch. `--snap-bite 0` is the pre-snap friction-only lid, byte-identical STLs.
- **Perfboard-driven geometry**: the board is a specific part used whole (Özdisan
  5 × 5, `PCB_URL`, 50 × 50, 18 × 19 holes centred — no cutting), every placement
  is `hole(col, row)`, and cavity, ledge, window and cap holes derive from
  PCB_W/L and PCB_COLS/ROWS. Single-sided: pads face down, components on the bare
  face; the layout drawing is the component-side view (mirrored when soldering).
  No custom PCB — Arda solders on perfboard.
- **The ESP32's USB-C is hidden under the lid on purpose**: `5V` is VBUS, so
  plugging it in with the switch ON back-feeds the TP4056 output. Opening the lid
  is the reminder. The slot is open-top in the wall and closed by the lid skirt's
  19 mm notch; because row 0 is only 2.14 mm from the board edge the port face
  reaches just 1.72 mm past the perfboard, so the wall's outer face is relieved
  there to `USB_WALL_T` 1.4 (the lid plate is notched over the relief) and the
  port ends 0.2 mm behind it. The TP4056's USB-C (charging) is the one exposed at
  floor level.

## Verified data (do not re-derive)

- **Pins**: BTN_UP GPIO3, BTN_DOWN GPIO4 (to GND, internal pull-ups, active low);
  OLED SDA GPIO6, SCL GPIO7, address 0x3C, 128 × 32. BOOT button = GPIO9.
  Header columns in the layout (USB at Y−, viewed from above, rows 0→7 from the
  USB end): col 3 = 5V, GND, 3V3, GPIO4, GPIO3, GPIO2, GPIO1, GPIO0; col 9 =
  GPIO5, GPIO6, GPIO7, GPIO8, GPIO9, GPIO10, GPIO20, GPIO21 — mischianti photo
  pinout, confirmed on the assembled board 2026-10-10.
- **Super Mini power** (mischianti schematic, 2025-07): `5V` header pin = USB VBUS
  net before BAT60J diode → ME6211 3.3 V LDO. Battery path Vbat → BAT60J
  (≈0.2–0.3 V) → ME6211 → 3V3: regulation to ≈3.6–3.7 V, 3V3 sags below ≈3.4 V
  (plain OK, Wi-Fi may brown out); DW01 cuts at 2.4 V. Red power LED ≈1–3 mA in
  deep sleep when fed through `5V`. TP4056 OUT− is the switched node (low-side
  protection) → star grounds at OUT−. Default R_PROG 1.2 kΩ = 1 A.
- **Module dimensions** (sources linked in README → Verified part geometry):
  Super Mini 18 × 22.5, pin rows 15.24 apart, first pin 2.36 from the USB edge,
  USB-C 9 × 3.2 overhanging 1.5; B3F tact 6 × 6, plunger Ø3.5, heights
  4.3/5/6/7; SS12D00 8.8 × 3.9 × 3.5, handle 1.5, travel 2.0; OLED 38 × 12 PCB,
  glass 30 × 11.5, active area 22.4 × 5.6 offset 3.7 (`OLED_AA_DX`, unmeasured),
  6.9 tall; TP4056 17 × 28 × 1.0, USB 9 × 3.2 overhanging 1.0; battery 503450
  34 × 50 × 5 → envelope 34 × 52 × 6; Özdisan 5 × 5 perfboard 50 × 50 × 1.6,
  18 × 19 holes at 2.54 centred (outer rows 2.14 from the Y edges, outer columns
  3.41 from the X edges), single-sided.
- **Behaviour contract** (both firmwares, tested in `tally_logic_test.cpp`): click
  counts on release, 20 ms debounce, 0…99999, both held ≥ 1 s → 0 and the two
  releases are swallowed, 60 s idle → OLED off + deep sleep, the wake press is not
  counted.

## Design map (case)

Frame: X = width (left/right as held), Y = length (Y− = bottom end with both
USB-C, Y+ = display end), Z up, Z = 0 = outer bottom face, XY origin = cavity
centre. Everything is modelled closed; the lid is flipped at export only.

Derived (from `derive()`, defaults): PCB 50 × 50 (19 holes along Y, 18 along X,
`hole()` centred on the board); cavity CAV 54.0 × 53.6 (width from battery 34 +
TP 17 + rib/gaps 3; length from PCB + 2 × (0.3 + 1.5) ledge); frame opening OPEN
50.6 × 50.6 (PCB + 0.3/side); outer 58.0 × 57.6; Z_LEDGE 11.0 (FLOOR 2 + PCB_Z 9),
PCB_TOP 12.6, Z_TOP 20.1 (+ LID_CLEAR 7.5), closed 22.1; lid 9.5 tall = LID_T 2 +
7.5 skirt; SKIRT 50.04 × 50.04 (opening − 2 × 0.28), SKIRT_NOTCH_W 19.0 over the
ESP32 end; USB_RELIEF_Y −26.92 (= −OPEN_L/2 − ESP_POCKET − USB_WALL_T),
ESP_USB_RECESS 0.20; SNAP_P 0.68 (= CLEAR_FRICTION + SNAP_BITE 0.4), SNAP_Z
13.10..15.26 (PCB_TOP + SNAP_Z0 0.5, + 2 × SNAP_P + SNAP_CREST 0.8), SNAP_SITES
as (outward normal, XY on the frame's inner face): X− (−25.3, 0), X+ (25.3, 0),
Y+ (0, 25.3), Y− (14.225, −25.3) = midpoint of the skirt remnant right of the
notch, (ESP_X + SKIRT_NOTCH_W/2 + OPEN_W/2)/2.

- **Under the ledge** (lower cavity): battery bay at X− (BAT_X0 −26.5, 34 wide,
  0.5 air); TP4056 against the X+ wall (TP_X0 10, TP_X 18.5), USB end sunk 1 mm
  into the Y− wall (TP_Y0 −28.2), RIB_T 1.2 divider at RIB_X 8.75, stop block
  behind; TP4056 USB-C window in the Y− wall at floor level; slide switch on the
  X+ wall at SW_Y 14 between two ribs (SW_RIB 1.2 × 4.5), slot 4.0 × 2.0.
- **On the ledge**: perfboard, pads down; ESP32 at ESP_X −6.35 (cols 3/9), its
  PCB starts at ESP_Y0 −25.22 and overhangs the opening by ESP_POCKET 0.22 into a
  shallow wall pocket; its USB-C goes through an open-top slot (USB_CUT_W 10) that
  the lid skirt notch closes. The port face sits only 1.72 past the perfboard
  edge, so the Y− wall is relieved from the OUTSIDE (SKIRT_NOTCH_W 19 wide, from
  PCB_TOP + 2 up through the lid plate, which is notched over it) down to
  USB_WALL_T 1.4 at USB_RELIEF_Y; the port ends ESP_USB_RECESS 0.20 behind that
  face. Tacts at TACT_XY (±12.7, 5.08) = `hole(3.5|13.5, 11)` (row 12 would hit
  the OLED). OLED header in col 1 rows 14…17 → OLED_X −2.05, OLED_Y 16.51; window
  WIN 27 × 9 at WIN_XY (1.65, 16.51) = OLED centre + OLED_AA_DX 3.7.
- **Lid**: plate 2.0, skirt 1.2 inside the frame (snap bumps on its outer face,
  next bullet), cap holes Ø8.4 at TACT_XY, pry notch 10 × 1.5 in the Y+ wall top
  edge, plate notch over the USB relief.
  Engraving: ENGRAVE_TEXT "Grindarr" (None = omitted) recessed ENGRAVE_DEPTH 0.6
  into the top face, ENGRAVE_H 6.0 cap height (auto-shrunk to the free band),
  centred ENGRAVE_XY (0, −13), ENGRAVE_FONT Liberation Sans Bold, reading along
  +X, upright toward Y+. Caps: stem Ø8.0, flange Ø11 × 2.2 (LID_CLEAR − TACT_H −
  0.3), stem 5.5 (1 mm proud), Ø3.8 × 0.5 recess centres on the plunger, 0.5 mm
  embossed symbol.
- **Snap detents** (one per SNAP_SITES entry; `snap_bump()` unions onto the lid,
  `snap_groove()` is a base cutter, both stood against the wall by
  `wall_frame(n, xy)` — a 4×4 mapping (u = out of the wall, v = Z, s = along the
  wall) onto a site; both skipped when SNAP_BITE is 0). Bump: (u, z) profile
  45° lead-in out to SNAP_P, SNAP_CREST 0.8 flat, 45° release ramp back to the
  face, extruded SNAP_LEN 8 along the wall, sunk 0.5 into the skirt (no coplanar
  seam); the crest bites SNAP_BITE 0.4 past the frame's inner face; Z 13.10..15.26
  with the lid seated. Groove: SNAP_BITE + SNAP_GROOVE_CLEAR 0.1 = 0.5 deep, 9
  long, Z 12.90..15.46 (1 mm / 0.2 mm beyond the bump), closed above by a solid
  band to Z_TOP; remaining frame wall 3.2 (X sides) / 3.0 (Y sides), the Y−
  groove starts 6.6 from the USB relief. Volumes: lid 7.4 cm³ (+0.03), base
  17.2 cm³ (−0.05); outer sizes unchanged.
- `apply_printer_args` validates: `--tact-height` + 1.5 ≤ LID_CLEAR (→ ≤ 6.0),
  battery T + 2 ≤ PCB_Z (→ ≤ 7), `--snap-bite` ≥ 0 with ≥ SNAP_MIN_WALL 1.0 of
  frame wall left behind the grooves and the Y− bump ≥ 1 mm from the skirt notch
  and the corner, `--engraving` non-empty with an outline for every glyph (else
  `p.error`; `--omit-engraving` sets ENGRAVE_TEXT None), then re-runs `derive()`.
  `verify.py` and `render_docs.py` import `generate` and call the same function,
  so the three always agree on GEN_ARGS. The summary line prints
  `snap bite 0.4 (4 detents)` or `no snap (friction only)` and
  `Engraving: "Grindarr" (6 mm, 0.6 deep)` or `omitted`; `build_index()` writes
  "snap-fit lid" / "friction-fit lid" accordingly.

## Conventions & gotchas

- **Docker only**, no local pip/pio/esphome (Arda's rule). Named volumes
  `esp32-tally-pio` (`/pio`, PLATFORMIO_CORE_DIR) and `esp32-tally-esphome-cache`
  (`/cache`) hold the toolchains; `make clean` keeps them.
- **Context7** for library docs (ESPHome components, U8g2, trimesh); don't guess
  YAML keys.
- Super Mini pinout images disagree on mirroring; the photo-based mischianti
  pinout and the real board are the reference, see `render_docs.py`
  `ESP_LEFT`/`ESP_RIGHT`.
- Outputs are committed (`case/stl`, `case/docs`, `case/preview.html`,
  `index.html`, `case/vendor/`) and never hand-edited; firmware binaries are
  gitignored and rebuilt. Bumping any pin re-triangulates every STL: regenerate,
  `make case-verify`, commit together.
- **Preview = filtarr's mechanism** (`case/preview_template.html`, placeholders
  `/*__THREE_B64__*/`, `/*__THREE_CORE_B64__*/`, `/*__DATA__*/null`): both
  three.js files are base64-embedded and loaded via blob dynamic imports; the
  module's relative `./three.core[.min].js` specifier is regex-patched to the
  core's blob URL in `boot()` (relative specifiers can't resolve from blob URLs).
  Parts are world-frame base64 binary STL (`DATA.parts`: `attach` base/lid/cap
  drives the Explode slider, `ghost: true` = component_boxes() boxes); the
  Dimensions panel takes `DATA.dims` filtered by the template's `ROWS` — a new
  key is silently dropped unless added there. Light intensities are on the
  r155+ physical scale. Since three.js r186 the npm package ships no `.min.js`,
  so `fetch_three.py` pulls from jsdelivr (serves the shipped min when it
  exists, Terser-minifies on the fly otherwise).
- **Snap detents**: both ramps are 45° **on purpose** (symmetric) — a steeper
  release ramp would hold harder but defeat the pry notch and need support on the
  flipped lid. The groove top stays **closed** (solid band to Z_TOP; a slot open to
  the rim retains nothing). The Y− site is **derived** from the skirt notch
  (`(ESP_X + SKIRT_NOTCH_W/2 + OPEN_W/2)/2`), so moving the ESP32 moves it and
  `apply_printer_args` re-checks its 1 mm margins. `--snap-bite 0` must keep
  producing **byte-identical** lid/base STLs to the pre-snap case: keep the
  `if SNAP_BITE > 0` guards in `build_base()`/`build_lid()`; `verify.py`'s `snap`
  scope rebuilds the no-snap twins in-process and diffs volumes against the
  analytic bump/groove volumes.
- The Makefile mounts the **repo root** at `/app` and runs in `/app/case`, so
  `generate.py` can write `../index.html`; `python3 generate.py` with only
  `case/` mounted would drop index.html into the container's `/`.
- Headless check without a GPU: `docker run --rm -v "$PWD":/work:ro -v <out>:/shots
  zenika/alpine-chrome --headless --disable-gpu --no-sandbox --use-gl=swiftshader
  --enable-unsafe-swiftshader --virtual-time-budget=6000 --screenshot=/shots/p.png
  --window-size=1400,900 file:///work/case/preview.html` renders WebGL in software.
- `GEN_ARGS` must be identical across `make case` and `make case-verify` (and
  `render_docs.py`): the Makefile passes the same variable to all three scripts.
  `ENGRAVING=` / `OMIT_ENGRAVING=1` are appended with **`override GEN_ARGS +=`** —
  a plain `+=` is silently ignored when GEN_ARGS is given on the command line.
  The `case-verify` recipe wraps its pip + verify in a single-quoted `sh -c '...'`
  so a multi-word `--engraving "My Text"` survives the shell.
- The engraving font lives in the **case image** (`fonts-liberation`, see
  `case/Dockerfile`); `generate.py` `p.error`s if `ENGRAVE_FONT` is missing, so
  run it through `make`. `make vendor` uses the bare `python:3.14-slim` image,
  which has no fonts and needs none.
- ESPHome: GPIO3 is both `binary_sensor` and `deep_sleep.wakeup_pin` →
  `allow_other_uses: true` on **both** uses. The C3 has no ext1, so GPIO4 is added
  with `esp_deep_sleep_enable_gpio_wakeup(1ULL << 4, …)` in a lambda right before
  `deep_sleep.enter` (IDF ORs the mask; ESPHome adds GPIO3 after).
- `deep_sleep.enter` **bypasses `deep_sleep.prevent`** — that's why "Keep Awake"
  is checked inside `idle_timer` rather than via prevent/allow.
- The wake press is already ON at boot → its release is ignored by
  `millis() > 1500` in both `on_release` lambdas. Plain build: `setup()` seeds
  `tally.up/down.raw/stable` from the pins and sets `tally.combo` if either is
  held, so the wake press's release is swallowed and a stuck-LOW button cannot
  block boot; `sleepNow()` leaves a LOW pin out of the GPIO wake mask (it would
  re-wake instantly; IDF pulls up the wake pins itself,
  `CONFIG_ESP_SLEEP_GPIO_ENABLE_INTERNAL_RESISTORS=y`). ESPHome `combo` global
  swallows the releases after a both-held reset; it is cleared when the *other*
  button is already up.
- `wifi`/`api` `reboot_timeout: 0s`: never reboot for lack of network.
- Plain build: `Serial.setTxTimeoutMs(0)` — USB CDC with no host must not stall
  the loop. Boot prints `boot reset=<esp_reset_reason> wake=<wakeup cause>` and
  the restored count. GPIO8 (`LED_PIN`, blue LED, active-LOW, 10 k pull-up,
  strapping pin) is driven LOW for the length of `setup()` (≈0.3 s, mostly U8g2's
  2 × 100 ms + 100 ms SSD1306 reset delays) then returned to INPUT — a blink with
  a dark OLED means MCU alive, display dead. NVS is written on every click
  (`putInt` commits itself; log-structured, tens of millions of clicks before
  wear matters) — a power cut never loses one.
- ESPHome: restoring `globals` only poll for changes every 1 s (`PollingComponent(1000)`)
  → `update_interval: 1ms` on `count` **and** `preferences: flash_write_interval: 1ms`
  (`0s` is coerced to 1 ms plus a validator warning; the syncer is itself a poller
  since 2026.9); either alone leaves a window.
- gfonts Roboto is downloaded at ESPHome compile time → the container needs
  internet on a cold cache.
- **No USB passthrough in Docker Desktop on macOS**: flash via web.esphome.io in
  Chrome/Edge with the `.factory.bin`; switch OFF first (5V = VBUS). Hold BOOT
  (GPIO9) while plugging in if the port is missing.
- `make esphome` depends on `firmware/esphome/secrets.yaml` as a file target whose
  recipe prints the fix and exits 1.
- Single-sided perfboard: the solder side faces the battery; insulation is part of
  the build, not optional (README → Assembly steps 5–6).

## User context

- Arda (ardakilicdagi@gmail.com, GitHub `Ardakilic`). Same house style as his
  filtarr repo (Makefile/Docker/README/verify pattern); projects are published
  dual-licensed MIT + CC BY 4.0.
- No custom PCB — perfboard only; everything (case, images, docs numbers) must be
  generated programmatically from constants, not drawn by hand.
- Working style: delegate research / edits / checks to subagents, Docker only,
  Context7 for docs, ask before open design choices, show results before
  committing or pushing. Do not `git init`/commit unless asked.
- Hardware status: **printed, assembled on the Özdisan board, plain firmware
  flashed via web.esphome.io (2026-10-10)**; wiring corrected after the
  mirrored-pinout bug (d957647). Field incident: a hot-glued cell/TP4056 under
  the board shorted/stressed the solder side and kept the OLED dark until the glue
  came off → insulate the solder side and mount both to the floor with foam tape
  (README → Assembly, Field notes). Open points: USB-C alignment (1.4 mm wall,
  plug seating), snap feel (`--snap-bite`, `--clear-friction`, the PLA 0.3
  guess), OLED window offset `OLED_AA_DX`, engraving legibility, the ESPHome
  variant (untested on hardware, incl. the 1.5 s wake guard), and the 100 mAh cell
  needs R_PROG ≥ 12 kΩ (default 1.2 kΩ = 1 A).
