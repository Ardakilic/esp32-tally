# CLAUDE.md — ESP32 Tally Counter

Handheld tally counter: ESP32-C3 Super Mini + 0.91" SSD1306 OLED + two 6 × 6 tact
switches + TP4056 + 503450 LiPo + SS12D00 slide switch on an 18 × 20-hole
perfboard, in a 58.0 × 58.4 × 22.1 mm printed case. Two firmwares (plain
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
  src/main.cpp                 pins, U8g2, Preferences/NVS (flush 2 s after change), deep sleep
  test/tally_logic_test.cpp    assert self-test, runs in gcc:14 — the committed test
  Dockerfile                   python:3.12-slim + platformio 6.2.0 + git, PLATFORMIO_CORE_DIR=/pio
  build/tally-plain.factory.bin  output (gitignored with .pio/)
firmware/esphome/tally.yaml    ESPHome 2026.9.1, esp-idf; secrets.yaml (gitignored) from .example
  .esphome/build/tally/build/firmware.{factory,ota}.bin   outputs (gitignored)
case/generate.py               constants with why-comments + derive() + build(part) -> 4 STLs
                               + build_preview() -> case/preview.html + build_index() -> index.html
case/preview_template.html     template for the self-contained three.js preview (filtarr's)
case/tools/render_docs.py      README images (matplotlib software renders), same flags
case/tools/verify.py           59 checks on in-memory builds, exit 1 on failure, same flags
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
```

Expected results: verify `59 checks — ALL PASS`; plain RAM 4.6 % / Flash 25.2 %;
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
  are reproducible. No fonts: the "+"/"−" symbols are rectangles.
- **Friction lid** (no screws, no magnets): the skirt slides *inside* the frame and
  clamps the perfboard on the ledge. 0.28 mm/side is filtarr's calibrated value.
- **Perfboard-driven geometry**: every placement is `hole(col, row)`; cavity,
  ledge, window and cap holes derive from PCB_COLS/ROWS. No custom PCB — Arda
  solders on perfboard.
- **The ESP32's USB-C is hidden under the lid on purpose**: `5V` is VBUS, so
  plugging it in with the switch ON back-feeds the TP4056 output. Opening the lid
  is the reminder. The slot is open-top in the wall and closed by the lid skirt's
  19 mm notch; the TP4056's USB-C (charging) is the one exposed at floor level.

## Verified data (do not re-derive)

- **Pins**: BTN_UP GPIO3, BTN_DOWN GPIO4 (to GND, internal pull-ups, active low);
  OLED SDA GPIO6, SCL GPIO7, address 0x3C, 128 × 32. BOOT button = GPIO9.
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
  34 × 50 × 5 → envelope 34 × 52 × 6.
- **Behaviour contract** (both firmwares, tested in `tally_logic_test.cpp`): click
  counts on release, 20 ms debounce, 0…99999, both held ≥ 1 s → 0 and the two
  releases are swallowed, 60 s idle → OLED off + deep sleep, the wake press is not
  counted.

## Design map (case)

Frame: X = width (left/right as held), Y = length (Y− = bottom end with both
USB-C, Y+ = display end), Z up, Z = 0 = outer bottom face, XY origin = cavity
centre. Everything is modelled closed; the lid is flipped at export only.

Derived (from `derive()`, defaults): PCB 45.72 × 50.8; cavity CAV 54.0 × 54.4
(width from battery 34 + TP 17 + rib/gaps 3; length from PCB + 2 × (0.3 + 1.5)
ledge); frame opening OPEN 46.32 × 51.4 (PCB + 0.3/side); outer 58.0 × 58.4;
Z_LEDGE 11.0 (FLOOR 2 + PCB_Z 9), PCB_TOP 12.6, Z_TOP 20.1 (+ LID_CLEAR 7.5),
closed 22.1; lid 9.5 tall = LID_T 2 + 7.5 skirt; SKIRT 45.76 × 50.84 (opening −
2 × 0.28), SKIRT_NOTCH_W 19.0 over the ESP32 end.

- **Under the ledge** (lower cavity): battery bay at X− (BAT_X0 −26.5, 34 wide,
  0.5 air); TP4056 against the X+ wall (TP_X0 10, TP_X 18.5), USB end sunk 1 mm
  into the Y− wall (TP_Y0 −28.2), RIB_T 1.2 divider at RIB_X 8.75, stop block
  behind; TP4056 USB-C window in the Y− wall at floor level; slide switch on the
  X+ wall at SW_Y 14 between two ribs (SW_RIB 1.2 × 4.5), slot 4.0 × 2.0.
- **On the ledge**: perfboard; ESP32 at ESP_X −6.35 (cols 3/9), its PCB starts at
  ESP_Y0 −26.49 and overhangs the opening by ESP_POCKET 1.29 into a wall pocket;
  its USB-C goes through an open-top slot (USB_CUT_W 10) that the lid skirt notch
  closes. Tacts at TACT_XY (±12.7, 6.35) = `hole(3.5|13.5, 12)`. OLED header in
  col 1 rows 15…18 → OLED_X −2.05, OLED_Y 17.78; window WIN 27 × 9 at
  WIN_XY (1.65, 17.78) = OLED centre + OLED_AA_DX 3.7.
- **Lid**: plate 2.0, skirt 1.2 inside the frame, cap holes Ø8.4 at TACT_XY, pry
  notch 10 × 1.5 in the Y+ wall top edge. Caps: stem Ø8.0, flange Ø11 × 2.2
  (LID_CLEAR − TACT_H − 0.3), stem 5.5 (1 mm proud), Ø3.8 × 0.5 recess centres on
  the plunger, 0.5 mm embossed symbol.
- `apply_printer_args` validates: `--tact-height` + 1.5 ≤ LID_CLEAR (→ ≤ 6.0),
  battery T + 2 ≤ PCB_Z (→ ≤ 7), then re-runs `derive()`. `verify.py` and
  `render_docs.py` import `generate` and call the same function, so the three
  always agree on GEN_ARGS.

## Conventions & gotchas

- **Docker only**, no local pip/pio/esphome (Arda's rule). Named volumes
  `esp32-tally-pio` (`/pio`, PLATFORMIO_CORE_DIR) and `esp32-tally-esphome-cache`
  (`/cache`) hold the toolchains; `make clean` keeps them.
- **Context7** for library docs (ESPHome components, U8g2, trimesh); don't guess
  YAML keys.
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
- The Makefile mounts the **repo root** at `/app` and runs in `/app/case`, so
  `generate.py` can write `../index.html`; `python3 generate.py` with only
  `case/` mounted would drop index.html into the container's `/`.
- Headless check without a GPU: `docker run --rm -v "$PWD":/work:ro -v <out>:/shots
  zenika/alpine-chrome --headless --disable-gpu --no-sandbox --use-gl=swiftshader
  --enable-unsafe-swiftshader --virtual-time-budget=6000 --screenshot=/shots/p.png
  --window-size=1400,900 file:///work/case/preview.html` renders WebGL in software.
- `GEN_ARGS` must be identical across `make case` and `make case-verify` (and
  `render_docs.py`): the Makefile passes the same variable to all three scripts.
- ESPHome: GPIO3 is both `binary_sensor` and `deep_sleep.wakeup_pin` →
  `allow_other_uses: true` on **both** uses. The C3 has no ext1, so GPIO4 is added
  with `esp_deep_sleep_enable_gpio_wakeup(1ULL << 4, …)` in a lambda right before
  `deep_sleep.enter` (IDF ORs the mask; ESPHome adds GPIO3 after).
- `deep_sleep.enter` **bypasses `deep_sleep.prevent`** — that's why "Keep Awake"
  is checked inside `idle_timer` rather than via prevent/allow.
- The wake press is already ON at boot → its release is ignored by
  `millis() > 1500` in both `on_release` lambdas (plain build: `setup()` waits
  until both buttons are up instead). `combo` global swallows the releases after
  a both-held reset; it is cleared when the *other* button is already up.
- `wifi`/`api` `reboot_timeout: 0s`: never reboot for lack of network.
- Plain build: `Serial.setTxTimeoutMs(0)` — USB CDC with no host must not stall
  the loop. NVS is written 2 s after the last change and on sleep, not per click.
- gfonts Roboto is downloaded at ESPHome compile time → the container needs
  internet on a cold cache.
- **No USB passthrough in Docker Desktop on macOS**: flash via web.esphome.io in
  Chrome/Edge with the `.factory.bin`; switch OFF first (5V = VBUS). Hold BOOT
  (GPIO9) while plugging in if the port is missing.
- `make esphome` depends on `firmware/esphome/secrets.yaml` as a file target whose
  recipe prints the fix and exits 1.

## User context

- Arda (ardakilicdagi@gmail.com, GitHub `Ardakilic`). Same house style as his
  filtarr repo (Makefile/Docker/README/verify pattern); projects are published
  dual-licensed MIT + CC BY 4.0.
- No custom PCB — perfboard only; everything (case, images, docs numbers) must be
  generated programmatically from constants, not drawn by hand.
- Working style: delegate research / edits / checks to subagents, Docker only,
  Context7 for docs, ask before open design choices, show results before
  committing or pushing. Do not `git init`/commit unless asked.
- Hardware status: **nothing flashed or printed yet** (see README → Not yet
  verified on hardware). First real-world feedback will decide
  `--clear-friction`, `OLED_AA_DX`, the OLED header order and the 1.5 s wake guard.
