# CLAUDE.md — ESP32 Tally Counter

Handheld tally counter: ESP32-C3 Super Mini + 0.91" SSD1306 OLED + two 6 × 6 tact
switches + TP4056 + 503450 LiPo + SS12D00 slide switch on a 50 × 50 mm Özdisan
single-sided 18 × 19-hole perfboard (used whole), in a 58.0 × 57.6 × 22.1 mm
printed case with "Grindarr" engraved in the lid. Variant: a Waveshare
RP2040-Zero on the same perfboard holes (`--mcu rp2040-zero`: own base + lid,
same caps). Three firmwares (plain PlatformIO and ESPHome on the ESP32,
PlatformIO + Arduino-Pico on the RP2040-Zero) implement identical behaviour.
Everything — STLs, README images, the 3D preview, the Pages index, all three
binaries — is **generated** through
Docker + make; nothing is installed on the host and no generated file is ever
hand-edited. License: MIT for code (`LICENSE`), CC BY 4.0 for models/images
(`LICENSE-MODELS`). GitHub Pages (`ardakilic.github.io/esp32-tally`) republishes
the whole checkout on every push to `main` via `.github/workflows/pages.yml`
(configure-pages/upload-pages-artifact/deploy-pages; Pages source = Actions,
enabled once by hand).

## Layout

```
Makefile                       canonical build: every target is a `docker run`
firmware/common/grind_chart.h  shared brew table GRIND_CHART + GRIND_MAX_LINES + grind_matches();
                               plain/rp2040 `-I ../common` (build_flags), ESPHome `esphome: includes:`
firmware/plain/                PlatformIO + Arduino 3.3.12 (pioarduino 55.03.312-1), U8g2 2.36.18
  src/tally_logic.h            pure C++ state machine (debounce, clamp, both-held
                               reset) + `struct SaveDelay` (touch/due: one save per burst)
  src/main.cpp                 pins, U8g2 (big digits, brew labels stacked to their right, drawn
                               on a click only), Preferences/NVS (SaveDelay, flush in sleepNow()),
                               deep sleep, seeded button state, GPIO8 boot blink, serial boot banner
  test/tally_logic_test.cpp    assert self-test: state machine, SaveDelay, grind chart (table
                               sanity, match oracle 0..100, max 0 / max 1 cap, one shipped-table
                               spot check), runs in gcc:14 — the committed test
  Dockerfile                   python:3.12-slim + platformio 6.2.0 + git, PLATFORMIO_CORE_DIR=/pio
  build/tally-plain.factory.bin  output (gitignored with .pio/)
firmware/rp2040/               Waveshare RP2040-Zero: PlatformIO + Arduino-Pico 6.1.0 (maxgerhardt
                               platform @5d4561a + release-zip override), U8g2 2.36.18, NeoPixel 1.15.5
  platformio.ini               env `zero`, filesystem_size 64k, -D SAVE_DELAY_MS=2000
                               -I ../plain/src (tally_logic.h, shared on purpose) -I ../common
  src/main.cpp                 pins, U8g2 on Wire1 (draw() = copy of plain's, keep in sync),
                               LittleFS /count (SaveDelay, flush in sleepNow()), DORMANT + watchdog
                               reboot on wake, WS2812 (GP16) boot blink, serial boot banner
  build/tally-rp2040.uf2       output (gitignored with .pio/); no Dockerfile: reuses image-plain
firmware/esphome/tally.yaml    ESPHome 2026.9.1, esp-idf; secrets.yaml (gitignored) from .example
  .esphome/build/tally/build/firmware.{factory,ota}.bin   outputs (gitignored)
case/generate.py               constants with why-comments + MCUS table (--mcu) + derive() +
                               build(part) -> 4 STLs + build_preview() -> case/preview.html +
                               build_index() -> index.html; --mcu rp2040-zero -> stl/rp2040-zero/
                               base + lid only, no web pages
case/Dockerfile                python:3.14-slim + fonts-liberation (engraving font) + requirements.txt
case/preview_template.html     template for the self-contained three.js preview (filtarr's)
case/tools/render_docs.py      README images (matplotlib software renders), same flags; MODULES
                               table (pins, wires, blocks, texts) -> docs/ or docs/rp2040-zero/
case/tools/verify.py           105 checks on in-memory builds (70 with --snap-bite 0, 101 with
                               --omit-engraving; rp2040-zero 104 / 69 / 100), exit 1 on failure,
                               same flags
case/tools/fetch_three.py      stdlib-only three.js downloader (`make vendor`, bare python image)
case/vendor/                   three.module.min.js + three.core.min.js + THREE_VERSION (committed)
case/stl/, case/docs/          COMMITTED outputs — regenerate, never edit
case/stl/rp2040-zero/          COMMITTED variant tally-base.stl + tally-lid.stl (caps: the default ones)
case/docs/rp2040-zero/         COMMITTED variant renders / perfboard-layout / wiring PNGs
case/preview.html, index.html  COMMITTED outputs too (preview + Pages landing page) — never edit
.github/workflows/pages.yml    publishes the whole checkout to GitHub Pages on push to main
.github/workflows/firmware.yml builds all three firmwares in Docker on push to main + PRs
                                (read-only build job); on main a separate publish job
                                updates the rolling `latest` release in place
                                (tally-plain.factory.bin, tally-rp2040.uf2,
                                tally-esphome.factory.bin, .ota.bin),
                                linked as direct downloads from index.html (generated from
                                REPO_URL in generate.py)
case/requirements*.txt         pinned (==) — a floating stack re-triangulates every STL
```

## Commands

```bash
make                 # case + plain + rp2040 + esphome
make case            # image-case, then generate.py + render_docs.py for --mcu rp2040-zero, then
                     # for --mcu esp32-c3 (same GEN_ARGS, --mcu last) -> case/stl (+ rp2040-zero/),
                     # case/preview.html, index.html, case/docs (+ rp2040-zero/)
make case-verify     # verify.py --mcu esp32-c3, then --mcu rp2040-zero, in one throwaway
                     # container (requirements-dev.txt extras); exit 1 if either fails
make vendor          # refresh both three.js files in case/vendor/ (bare python:3.14-slim)
make plain           # pio run -> firmware/plain/build/tally-plain.factory.bin (407 KiB)
make plain-test      # host self-test, firmware/ at /work, -Isrc -I../common; prints OK
                     # (also covers the RP2040 build's logic: same tally_logic.h)
make rp2040          # pio run (image-plain + esp32-tally-pio volume, workdir firmware/rp2040)
                     # -> firmware/rp2040/build/tally-rp2040.uf2
make esphome         # compile; fails with a message if secrets.yaml is missing
make esphome-config  # validate only
make esphome-ota     # DEVICE ?= tally.local — turn on "Keep Awake" in HA first
make clean           # case/stl case/docs case/preview.html index.html, plain + rp2040 .pio/build,
                     # .esphome (volumes stay)
make case GEN_ARGS="--clear-friction 0.32 --tact-height 5 --battery 30x40x5"
make case GEN_ARGS="--snap-bite 0.3"   # PLA lid; 0 = no detents (plain friction fit)
make case ENGRAVING="My Text"   # appends --engraving "My Text" to GEN_ARGS
make case OMIT_ENGRAVING=1      # appends --omit-engraving (plain lid top)
```

Expected results: verify `verify (esp32-c3): 105 checks — ALL PASS` (70 with
`--snap-bite 0`, 101 with `--omit-engraving`) and `verify (rp2040-zero): 104 checks —
ALL PASS` (69 / 100; one fewer: its three thin-wall/recess checks become two);
plain RAM 4.6 % / Flash 25.5 %, factory bin 407 KiB (416640 bytes);
rp2040 RAM 3.9 % (10096 of 262144 B) / Flash 4.2 % (85016 of 2027520 B), firmware.bin
97048 bytes, uf2 190 KiB (194560 bytes), no warnings;
ESPHome Flash 51.5 % / RAM 33.1 %, factory bin 987 KB (1011104 bytes).

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
- **RP2040-Zero: Arduino-Pico on maxgerhardt's platform, pinned by commit**: the
  official `platformio/raspberrypi` has only the mbed core.
  `maxgerhardt/platform-raspberrypi#5d4561a` (2026-09-10, its HEAD; its tags are far
  older) brings the earlephilhower core and board `waveshare_rp2040_zero`
  (`board_build.core = earlephilhower` explicit, so a platform change can't swap in
  mbed). The platform pins arduino-pico by git (6.1.0 + 4 docs/tools-only commits,
  a ~1.4 GB recursive submodule clone); `platform_packages` points at the 6.1.0
  release zip (~130 MB), byte-identical firmware (sha256-checked, arm64 and amd64),
  which matters in volume-less CI. 6.1.0 bundles pico-sdk 2.3.0, littlefs v2.11,
  GCC 16.1 (pqt 5.0.0). 6.4.0's LowPower `dormantUntilPin()` takes one pin: not used.
  Same image and volume as plain (`RUN_RP2040` = `RUN_PLAIN` with workdir
  `/app/firmware/rp2040`; pio fetches the platform per project, ~1 GB on a cold volume).
- **`tally_logic.h` included from `../plain/src` on purpose** (`-I ../plain/src`), not
  copied: one state machine + SaveDelay for both PlatformIO builds, so `make
  plain-test` covers the RP2040 logic too. Open PR #7 edits `firmware/plain/src/
  main.cpp`, `tally_logic.h` and the test, which is why the RP2040 work touched nothing
  under `firmware/plain/`; after any change there, rebuild `make rp2040` (main.cpp uses
  `Tally::MAX`, `update()`, `up/down.raw/stable`, `combo`, `last_activity_ms`,
  `SaveDelay` `touch`/`due`/`dirty`). `draw()` is a copy of plain's (marked keep in sync).
- **LittleFS over EEPROM** for the RP2040 count: one 4-byte `/count` file,
  `filesystem_size = 64k` (the smallest). Copy-on-write: open `"r+"` + write + close
  rewrites it in place as one commit, a power cut keeps the previous value, wear spreads
  (~1 erase per 16 saves over 14 blocks). Two Arduino-Pico 6.1.0 wrapper defaults would
  break that, so `loadCount()` calls `LittleFS.setTimeCallback(nullptr)` before `begin()`
  and `storeCount()` opens `"w"` only to create the file: `"w"` = O_TRUNC, and
  `LittleFSImpl::open()` runs `lfs_file_sync()` right after opening, which commits an
  *empty* file before the write (a cut there reads back as 0); the default time callback
  adds a `'t'` setattr commit per close. Host replay of the wrapper's call sequence on
  littlefs v2.11 at the core's geometry (256/256/4096 × 16, block_cycles 16), with a
  power cut after every prog/erase: `"w"` + callback 3 commits, ~1 erase per 3.7 saves,
  1 empty-file cut point per save; callback off alone 2 / 8.0 / still 1; `"r+"` + no
  callback 1 / 15.9 / none. EEPROM emulation erases + reprograms one 4 KB sector per
  commit: a cut in that 45–400 ms window loses the whole count, all wear on one sector.
  Costs +26.9 KB flash, irrelevant on 2 MB. Both regions survive UF2 uploads.
- **RP2040 sleep = DORMANT + watchdog reboot on wake**, the ESP32 deep-sleep model:
  DORMANT would resume in place, but rebooting makes every wake a fresh `setup()`
  (button seeding, wake-press swallowing, banner) with nothing to restore (clocks, USB,
  I2C). Sequence after pico-extras sleep.c: flush, OLED power-save, WS2812 black +
  `delay(1)`, `noInterrupts()`, arm both pins, clk_ref → XOSC, clk_sys → clk_ref, stop
  clk_usb/adc/rtc, clk_peri from clk_sys, `pll_deinit` both (DORMANT doesn't halt PLLs),
  save + disable ROSC CTRL, `xosc_dormant()`; on wake restore ROSC CTRL + wait STABLE,
  `watchdog_hw->scratch[0] = 0x7a11d0e5` (wake flag; scratch[1..2] = the unsaved-count
  stash; bootrom/SDK use only scratch[4..7], the core none),
  `rp2040.reboot()`. **Level wake, not edge**: `armWake()` clears all four dormant
  enables, then arms `GPIO_IRQ_LEVEL_LOW` on a released (high) pin or `LEVEL_HIGH` on a
  held/stuck one (datasheet 2.11.3: level or edge). Levels aren't latched (2.19.3), so no
  stale awake-period event fires and a change between `gpio_get()` and the enable wakes
  at once; there is always a wake source (none = the XOSC never restarts).
- **Adafruit NeoPixel for the RP2040 boot blink**: Arduino-Pico 6.1.0 has no WS2812
  driver; NeoPixel 1.15.5 drives GP16 through a PIO state machine (+2 KB flash). Dim blue
  (0, 0, 16) is the third byte in GRB and RGB alike, so the colour order can't matter.
- **U8g2 as the single plain-build dependency**: one lib for SSD1306 128 × 32 over
  hardware I2C plus its fonts — `logisoso28_tn` (count), `6x10_tf` (1–3 brew labels),
  `5x8_tf` (4 labels); no GFX + BusIO pair. `setBusClock(400000)` before `begin()`: a
  512-byte frame takes ~13 ms instead of ~50 ms at the 100 kHz default, so the redraw
  after a click blocks button polling less.
- **One shared grind-chart header** (`firmware/common/grind_chart.h`: `GRIND_CHART`,
  `GRIND_MAX_LINES`, `grind_matches()`): one place for users to edit the brew table,
  and all three builds plus the host test compile the same file, so they cannot drift.
  `RUN_PLAIN`/`RUN_RP2040`/`RUN_ESPHOME` mount the repo root at `/app` (workdir
  `/app/firmware/plain` / `rp2040` / `esphome`) so `..` resolves; plain and rp2040 add
  `-I ../common` to `build_flags`, ESPHome lists `../common/grind_chart.h` under
  `esphome: includes:` (accepts `..`, copies it into the build's `src/`).
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
  floor level. The RP2040-Zero variant can't keep this: its port face lands past the
  frame's inner face, so its end is an open window (Design map) and the switch-OFF
  rule rests on the docs alone (its `5V` is VBUS too, with no diode at all).

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
- **RP2040-Zero pins in the case frame** (USB at Y−, viewed from above; Waveshare
  pinout graphic, silkscreen photos, schematic P1, arduino-pico variant and STEP agree;
  Waveshare's USB-up view rotated 180° in plane, not mirrored): col 3 rows 0→8 =
  GP0…GP8; col 9 = 5V, GND, 3V3, GP29, GP28, GP27, GP26, GP15, GP14 — **power on col 9,
  the mirror of the Super Mini**; the only side-header GND is (9,1). Far-edge pads
  GP9…GP13 = row 8, cols 4…8 (leave unpopulated; the -M's factory header there crowds
  the SCL wire, 0.21 mm from (8,8) — buy the plain Zero). Underside SMD pads GND,
  GP25…GP17 (1.27 pitch) ≈1.7 mm inboard of col 9, Y −17.46…−5.73, facing the
  perfboard. GP16 = WS2812 DIN only (no pad). BOOT = QSPI_SS_N via 1 kΩ (not a GPIO),
  RESET = RUN. No strapping GPIOs; every GPIO resets with its pull-DOWN on; GP26–29
  are not fault-tolerant.
- **RP2040-Zero chosen pins** (exhaustive crossing-free search): UP GP26 (9,6), DOWN
  GP8 (3,8), OLED SDA GP14 (9,8) / SCL GP15 (9,7) on I2C1 = `Wire1` (RP2040 pairs are
  fixed: I2C0 SDA 4k / SCL 4k+1, I2C1 SDA 4k+2 / SCL 4k+3). Wires, hole (col,row):
  OLED VCC (1,15) → 3V3 (9,2); OLED GND (1,14) → (2,12); SCL (1,16) → (9,7); SDA
  (1,17) → (9,8); DOWN (2,10) → (3,8); (2,12) → GND (9,1); UP (12,10) → (9,6);
  (15,12) → GND (9,1); TP4056 OUT+ → switch → 5V (9,0); OUT− → GND (9,1) = star.
  Tact leg pairing (same-row legs joined, signal row 10 / GND row 12) is inferred from
  the working ESP32 build — README tells builders to beep it.
- **RP2040-Zero dimensions** (Waveshare drawing + STEP model read with OCP): 18 × 23.5,
  R1 corners, PCB 1.09 (STEP only, no document states it), 9 pins a side 15.24 apart,
  first pin 1.59 from the USB edge (drawing; STEP 1.60); USB-C 8.94 wide (drawing
  implies 8.66 — conflict), shell 0.09…3.25 above the PCB, overhang 1.21 (STEP). Top:
  BOOT/RESET SMD 3.0 × 4.65 × 2.5 at Y ≈ −10.8…−6.1 once mounted, WS2812 1.0, flash 0.6;
  bottom: RP2040 QFN 0.85, 12 MHz crystal 1.0 (tallest), LDO. Stack above the perfboard
  2.54 + 1.09 + 3.25 = 6.88 (ESP32 6.74).
- **RP2040-Zero power** (schematic + wiki FAQ): `5V` = USB VBUS = VSYS directly (no
  diode, no fuse) → LDO (EN = VIN) → 3V3 — same back-feed hazard as the Super Mini.
  LDO: schematic RT9013-33 (Iq 25 µA, 250 mV @ 500 mA), product page ME6217C33M5G (Iq
  100 µA) — read the marking. No power LED. WS2812B on 3V3 permanently, ≈0.45–1 mA dark
  (V5 datasheet 0.6 mA centre value; PJRC ~1 mA) = the dominant sleep term; RP2040
  DORMANT 0.18 mA typ (datasheet Table 637, 4.2 mA max-avg), flash standby 10 µA → board
  ≈0.85 mA with the LED / ≈0.25 mA without (estimated, unmeasured). 3V3 = 3.30 V down to
  Vbat ≈3.35 V, then Vbat − 10–20 mV; RP2040 IOVDD 1.63–3.63 V; W25Q16JV ≥ 2.7 V is the
  real floor (above the DW01's 2.4 V); SSD1306 charge pump wants ≥ 3.3 V.
- **Behaviour contract** (all three firmwares, tested in `tally_logic_test.cpp`): click
  counts on release, 20 ms debounce, 0…99999, both held ≥ 1 s → 0 and the two
  releases are swallowed, 30 s idle → OLED off + deep sleep (RP2040: DORMANT), the wake
  press is not counted.
- **OLED rows** (128 × 32; the count sits at the same rows with or without labels, the
  labels are stacked to its right, block centred vertically). Plain and RP2040 (same
  `draw()`; explicit baselines, default U8g2 font position): `logisoso28_tn` baseline 30 → digits rows 2..29;
  `6x10_tf` (7 px caps, 10 px pitch) for 1–3 lines → caps 12..18 (1), 7..13 / 17..23
  (2), 2..8 / 12..18 / 22..28 (3, descenders to 30); `5x8_tf` (6 px caps, 8 px pitch)
  for 4 → caps 1..6 / 9..14 / 17..22 / 25..30, descenders on 7, 15, 23, 31 — from a
  host render of the real U8g2 2.36.18 C library (frame-buffer dump); widest shipped
  group = count 26, right edge at column 120, nothing clips. ESPHome: `big` Roboto
  700/28 at y 26, `BASELINE_LEFT` (labels) / `BASELINE_CENTER` (none) → digits rows
  6..25 in both branches; `label` Roboto 400/10 (`TOP_LEFT`, −2 px, 10 px pitch) for
  1–3, `label4` Roboto 400/8 (−1 px, 8 px pitch) for 4 → the same cap rows as plain.
  Size-10 lines touch (10 px ink in a 10 px pitch) but don't overlap; a descender on a
  4th line would fall on row 32 and be cut (no shipped name has one). Old bug (up to
  9344739): `setFontPosCenter()` + y 16 with `logisoso28_tn`, whose header has
  ascent 28 / descent −7 (glyphs the counter never prints) → baseline 26, digits
  rows −2..25: two rows cut off the top, six blank below — matched Arda's photo.

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
  +X, upright toward Y+. Caps: stem Ø8.0, flange Ø11 × 2.9 (LID_CLEAR − TACT_H −
  0.3), stem 6.2 (1 mm proud), Ø3.8 × 0.5 recess centres on the plunger, 0.5 mm
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
- **Module (`--mcu esp32-c3|rp2040-zero`)**: `MCUS` table, applied with
  `globals().update(MCUS[MCU])` in `apply_printer_args` before `derive()`; the `ESP_*`
  names describe the **selected** module. Per module (ESP32 / Zero): MCU_NAME,
  MCU_SHORT (labels), ESP_L 22.5 / 23.5, ESP_PIN_END 2.36 / 1.59, ESP_USB_OVERHANG
  1.5 / 1.21, ESP_USB_W 9.0 / 8.94, ESP_USB_H 3.2 / 3.25, ESP_PCB_T 1.0 / 1.09,
  USB_WALL_T 1.4 / 0. ESP_W 18, ESP_PIN_ROW_GAP 15.24, ESP_STANDOFF 2.54, ESP_X and so
  SNAP_SITES are shared. Zero derived: ESP_Y0 −24.45 (PCB ends 0.85 inside the opening)
  → ESP_POCKET 0 (pocket cutter `None`, filtered out — the ESP32 cutter list and order
  are unchanged, its STLs byte-identical); USB_RELIEF_Y −25.3 (= −OPEN_L/2); port face
  Y −25.66; ESP_USB_RECESS −0.36 (0.36 PAST the frame's inner face, 1.06 further in
  than the ESP32's −26.72). No wall fits (recess ≤ 0.3 → a ≤ 0.66 sliver; wall ≥ 1.2 → a
  0.84 recess that stops the plug), hence USB_WALL_T 0: the outer plug relief
  (SKIRT_NOTCH_W 19, from PCB_TOP + 2) cuts through to 1 mm into the opening (no face
  coplanar with the frame cutter), the lid plate notch ends at −OPEN_L/2 → an **open
  19 × 7.5 mm end window**, the receptacle is the plug stop. The variant pass writes
  only `stl/rp2040-zero/tally-{base,lid}.stl` (`VARIANT_PARTS`; its caps are
  byte-identical to the default ones) and no preview/index: base 17.12 cm³, lid
  7.38 cm³, outer sizes unchanged; summary shell line "RP2040-Zero USB-C in the open end
  relief (no wall in front), face 0.36 past the frame's inner face"; a console-only
  "module — …" line (the summary list feeds preview.html). `verify.py` with USB_WALL_T 0
  swaps the three thin-wall/recess checks for two: a 5 × 5 ray grid along +Y over the
  receptacle face hits no base/lid before it, and an ASSUMED `PLUG_OVERMOLD` 12 × 6.4
  envelope reaching `PLUG_GAP` 0.05 short of the face (Type-C R1.3 Fig 3-73) overlaps
  neither part; "lid clears the RP2040-Zero USB-C" 7.18 ≤ 7.5. Not in verify: the Zero's
  BOOT/RESET (not in `component_boxes()`) sit 1.37 under the lid; the "−" cap flange
  clears the module's far edge (Y −0.95) by 0.53 in plan, 0.67 above its PCB.
  `render_docs.py` `MODULES`/`use_module()`: pin lists, wires (optional 6th field =
  label nudge dx/dy + text kwargs, used by "DOWN -> GP8"), blocks, links, texts; the
  GP9…GP13 pads are not drawn (they'd hit the GP8/GP14 labels), the layout title says
  to leave them empty. `build_index()` adds an "RP2040-Zero variant" card (renders,
  layout, wiring, the two STLs with sizes — no size, no crash if missing) and an
  "RP2040 .uf2" release button.
- `apply_printer_args` validates: `--tact-height` + 1.5 ≤ LID_CLEAR (→ ≤ 6.0),
  battery T + 2 ≤ PCB_Z (→ ≤ 7), `--snap-bite` ≥ 0 with ≥ SNAP_MIN_WALL 1.0 of
  frame wall left behind the grooves and the Y− bump ≥ 1 mm from the skirt notch
  and the corner, `--engraving` non-empty with an outline for every glyph (else
  `p.error`; `--omit-engraving` sets ENGRAVE_TEXT None); it applies `MCUS[--mcu]`
  right before re-running `derive()`, and the snap margins are checked after that, on
  the selected module's geometry.
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
  `ESP32_LEFT`/`ESP32_RIGHT` (the Zero's: `ZERO_LEFT`/`ZERO_RIGHT`; `use_module()`
  copies the selected pair into `ESP_LEFT`/`ESP_RIGHT`).
- Outputs are committed (`case/stl` incl. `rp2040-zero/`, `case/docs` incl.
  `rp2040-zero/`, `case/preview.html`, `index.html`, `case/vendor/`) and never
  hand-edited; firmware binaries are gitignored and rebuilt. Bumping any pin
  re-triangulates every STL: regenerate, `make case-verify`, commit together.
- **Two case passes**: `make case` runs the `--mcu rp2040-zero` pass first so the
  default pass's `build_index()` can print the variant STL sizes (missing files → no
  size, no crash). `--mcu` comes after `$(GEN_ARGS)`, so it wins over one inside
  GEN_ARGS; fit flags and the engraving apply to both modules. Only the default pass
  writes `preview.html` / `index.html`. Any change to the shared geometry must keep
  the ESP32 STLs byte-identical unless intended — the module-specific cutters are
  guarded (`if ESP_POCKET > 0`, `USB_WALL_T > 0`).
- `case/docs/renders.png` drift: in the current case image (2026-11-18) the default
  `renders.png` regenerates 163 px different from the committed one (anti-aliasing,
  ≤ 9 % intensity, closed view only) even from HEAD's own code; the committed bytes
  were restored. Don't commit that drift on its own (`git checkout case/docs/renders.png`).
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
  The `case-verify` recipe runs pip + both verify passes in one `sh -c '...'` and
  hands `$(GEN_ARGS)` to it as positional args (`sh -c '... "$$@" ...' sh $(GEN_ARGS)`),
  so the host shell parses them as in `case`: a multi-word `--engraving "My Text"`
  survives, and so does an apostrophe (inside the quoted script it would end it).
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
  `CONFIG_ESP_SLEEP_GPIO_ENABLE_INTERNAL_RESISTORS=y`). RP2040 build: the same
  seeding (every wake is a reboot); instead of dropping a LOW pin it arms it as a
  `LEVEL_HIGH` wake (its release), so there is always a wake source. ESPHome `combo` global
  swallows the releases after a both-held reset; it is cleared when the *other*
  button is already up.
- `wifi`/`api` `reboot_timeout: 0s`: never reboot for lack of network.
- Plain build: `Serial.setTxTimeoutMs(0)` — USB CDC with no host must not stall
  the loop. Boot prints `boot reset=<esp_reset_reason> wake=<wakeup cause>` and
  the restored count. GPIO8 (`LED_PIN`, blue LED, active-LOW, 10 k pull-up,
  strapping pin) is driven LOW for the length of `setup()` (≈0.3 s, mostly U8g2's
  2 × 100 ms + 100 ms SSD1306 reset delays) then returned to INPUT — a blink with
  a dark OLED means MCU alive, display dead. One save rule, all three
  firmwares: every click restarts a 2 s timer, gaps under 2 s never write, the pause
  after the last click writes the final count once (one write per burst); sleep
  flushes a pending count first; a power cut during a burst or within 2 s of the last
  click loses the clicks since the previous write. Plain: `struct SaveDelay` in
  `tally_logic.h` (`touch(now)` on a change, `due(now, delay_ms)`), `SAVE_DELAY_MS`
  (build flag, 2000, 0 = every click); `main.cpp` flushes when due (`putInt` commits
  itself) and in `sleepNow()`; `make plain-test` covers burst → one write 2 s after
  the last click, 60 s of clicks at 1.5 s gaps → none then one, millis wrap, delay 0,
  flush before sleep. RP2040: the same `SaveDelay`; `flush()` → `storeCount()`
  (LittleFS open `"r+"` + write + close = one commit; `"w"` only creates the file), also first thing in `sleepNow()`.
  `File::close()` drops littlefs's return code, so `storeCount()` reads the value back and
  `dirty` clears only on a match; a failed save is retried `SAVE_DELAY_MS` later, `SAVE_TRIES`
  (3) per burst (a click resets them), and `sleepNow()` stays awake while tries remain, then
  sleeps anyway. Unsaved-count stash: every count change `stash()`es it in
  `watchdog_hw->scratch[1]` with `scratch[2] = [1] ^ 0x5a7ec0de` (survive DORMANT, the watchdog
  reboot and any soft reset; POR/RUN clear them); only a successful `flush()` clears it.
  `setup()` takes a valid stash (≤ MAX) over the file and `save.touch()`es it, keeping the stash
  until the save lands (banner `(unsaved, kept over sleep)`). Sleeping with a failed save is
  **on purpose** (CodeRabbit asked for "no sleep while unsaved"): awake on a broken FS the cell
  reaches the DW01 cut-off in days and the power loss clears scratch too, so staying up loses
  the count as well, plus the device; DORMANT keeps the stash for as long as the cell lasts.
- **I2C 400 kHz** on all three builds: plain and RP2040 `setBusClock`, ESPHome
  `i2c: frequency: 400kHz` (default 50 kHz ≈ 90 ms/frame), so a click's redraw blocks
  the loop less. OLED misbehaving at 400 kHz on esp-idf → try `i2c: timeout: 10ms`
  first. RP2040: `Wire.begin()` enables the 50–80 kΩ internal pull-ups, too weak for
  400 kHz alone — the bus relies on the OLED module's own pull-ups.
- **RP2040 I2C pins**: `Wire1.setSDA(14)` / `setSCL(15)` must run **before**
  `u8g2.begin()` (which calls `Wire1.begin()`); a pin outside I2C1's set, or a change
  after begin(), `panic()`s at boot (the WS2812 then stays lit). U8g2 2.36.18 passes
  constructor clock/data pins to `Wire.begin(sda, scl)` only on ESP cores, so on
  Arduino-Pico they'd be ignored: `U8G2_SSD1306_128X32_UNIVISION_F_2ND_HW_I2C` (Wire1;
  enabled because `WIRE_INTERFACES_COUNT` = 2) takes only rotation + reset.
- **RP2040 DORMANT pitfalls**: the SDK's watchdog reboot (PSM WDSEL spares ROSC/XOSC)
  resets CLOCKS (clk_ref back on the ROSC) but **not the ROSC itself** — reboot with
  it disabled and the chip locks up; restore the saved CTRL (keeps FREQ_RANGE;
  `rosc_restart()` would zero it) and wait for STABLE first. `rp2040.reboot()` (10 ms
  watchdog timer) reports SOFT_RESET (3); `watchdog_reboot(0,0,0)` would fall through
  to PWRON_RESET (1). `rp2040.reboot()` is not `[[noreturn]]` → endless loop after it
  in the `[[noreturn]]` function. Flush, OLED power-save and the WS2812 latch
  (`clear` + `show` + `delay(1)`, > 280 µs low) must finish before clk_sys/clk_peri
  change. Pull-ups hold in DORMANT (a stuck-low button costs 41–66 µA); don't use
  pico_low_power's pin parking (turns pulls off). Don't put the flash into deep
  power-down (0xB9): unverified that boot releases it after a watchdog reboot. RP2040
  pins reset with the pull-DOWN on → `INPUT_PULLUP` explicitly.
- **PlatformIO LDF chain mode ignores `#ifdef`**: keep library includes unconditional in
  `firmware/rp2040/src/main.cpp` (or switch to `lib_ldf_mode = chain+`).
- **RP2040 Serial**: `Serial.begin(115200)` only (the baud is ignored). With no host,
  or DTR low, writes return at once and are dropped; do NOT call
  `Serial.ignoreFlowControl(true)` (writes could then spin up to 1 s); no
  `setTxTimeoutMs` equivalent is needed. A dormant Zero drops off USB and re-enumerates
  after the wake reboot, so the first banner is usually gone before a terminal opens.
  Banner `boot reset=<getResetReason> wake=<scratch[0] flag>`: expected `reset=3
  wake=1` after a button wake, `reset=1 wake=0` from the slide switch, `reset=2` from
  RESET.
- **`board_build.filesystem_size` moves the FS start**: changing it makes the next
  mount fail → LittleFS autoformats → the count is lost. UF2 uploads leave the FS (and
  the EEPROM sector) alone. Flash writes run with interrupts off and XIP stalled: a
  save is ~1 ms (every ~15th adds a ~45 ms sector erase), harmless 2 s after the last
  click; the first boot formats 64 KB (≈0.7 s longer blink, once).
- **Grind chart**: `GRIND_CHART` rows `{from, to, "Name"}`, inclusive;
  `grind_matches(count, out, max)` fills up to `max` names in table order and returns
  the total match count (may exceed `max`); all three builds pass `GRIND_MAX_LINES` (4) and
  draw at most that many — extra matches are simply not shown. An empty
  `GRIND_CHART[] = {}` (zero-length array) turns the labels off and compiles under
  g++ 14 `-Wall -Wextra -Werror`; only `-Wpedantic` rejects it, so don't add that.
  Layout: digits + 6 px gap + widest label centred as a group,
  `x0 = max(0, (128 − (nw + 6 + lw)) / 2)`, so with no label the digits are centred as
  before (plain `draw()` is one path, n = 0 zeroes gap and label width; ESPHome has a
  `BASELINE_CENTER` branch); an over-long user name clips at the right edge. Side by
  side, not stacked: 28 px digits + a 7 px cap-height line exceed 32 rows, and Arda
  found the 21 px-digit stacked version cramped on the device. Static screen: plain
  and RP2040 redraw from `loop()` on a count change, ESPHome display `update_interval: never` +
  the `refresh` script on a click. The test's oracle recomputes the names from the
  table (survives edits); the one literal spot check (7 → Turkish, Espresso; 0 and
  41 → none) under "shipped table; update if you edit it" **must be updated** whenever
  the shipped rows change (an empty table fails only that check).
- `make plain-test` mounts `firmware/` at `/work` and runs in `/work/plain` with
  `-Isrc -I../common`; the old one-dir `firmware/plain:/work` mount no longer finds
  `grind_chart.h` (likewise the old `/work` / `/config` mounts of `RUN_PLAIN` /
  `RUN_ESPHOME`).
- ESPHome save rule: `save_later` script (`mode: restart`, `delay: ${save_delay}`,
  `global_preferences->sync()`), run from `refresh` (every count change goes through
  it: both releases, the both-held reset, the HA number, Reset Tally).
  `preferences: flash_write_interval: never` so nothing writes mid-burst; the syncer
  component still exists, so its shutdown hook flushes before `deep_sleep.enter`.
  `global_preferences->sync()` is an ESPHome internal (pinned 2026.9.1; re-check on
  upgrade). `update_interval: 1ms` on `count` is RAM-only (restoring globals poll every
  1 s by default, then queue in RAM).
- gfonts Roboto is downloaded at ESPHome compile time → the container needs
  internet on a cold cache.
- **No USB passthrough in Docker Desktop on macOS**: flash via web.esphome.io in
  Chrome/Edge with the `.factory.bin`; switch OFF first (5V = VBUS). Hold BOOT
  (GPIO9) while plugging in if the port is missing. The RP2040-Zero needs neither:
  switch OFF, lid off, hold BOOT while plugging in (or hold BOOT, tap RESET) → the
  bootrom's `RPI-RP2` drive → copy `tally-rp2040.uf2`. The 1200-bps-touch / picotool
  upload needs an awake (not dormant) sketch and host USB access — not usable from
  Docker; UF2 copy is the documented path.
- `make esphome` depends on `firmware/esphome/secrets.yaml` as a file target whose
  recipe prints the fix and exits 1. CI has no real secrets: firmware.yml builds
  ESPHome from the `.example` with a throwaway generated `api_key`, so the released
  ESPHome binary ships placeholder Wi-Fi/API credentials (counts standalone, Wi-Fi
  via captive portal; rebuild with real secrets for HA) — README → Flashing says so.
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
  (README → Assembly, Field notes). Top-clipped digits on the first flash were a
  software bug (`setFontPosCenter`, see Verified data → OLED rows), fixed
  2026-10-11. Open points: USB-C alignment (1.4 mm wall, plug seating), snap feel
  (`--snap-bite`, `--clear-friction`, the PLA 0.3 guess), OLED window offset
  `OLED_AA_DX`, engraving legibility, the ESPHome variant (untested on hardware,
  incl. the 1.5 s wake guard), the brew-label layout (labels one per line right of
  the digits) and 400 kHz I2C (both ESP32 builds, untested on hardware; the stacked
  digits-over-label layout was rejected by Arda on 2026-10-11 as cramped), and the
  100 mAh cell needs R_PROG ≥ 12 kΩ (default 1.2 kΩ = 1 A).
- RP2040-Zero variant (added 2026-11-18 on branch `rp2040-zero`): **untested on
  hardware, unprinted** — builds clean, case verify passes. Open: DORMANT entry/exit
  and the ROSC-restart-then-`rp2040.reboot()` path (lock-up risk), level wake on both
  pins incl. a held/stuck one waking on release, a quick wake tap not counting, banner
  values, sleep current (≈0.85 mA est. with the WS2812 / ≈0.25 mA desoldered), plug
  seating in the open end window (12 × 6.4 overmold assumed) and the window itself
  (look, dust — an open design choice), 400 kHz I2C on GP14/15 with module pull-ups
  only, OLED at low cell voltage, which LDO is fitted (RT9013 vs ME6217), WS2812 colour
  order, first-boot LittleFS format, count surviving a UF2 re-flash, the STEP-only
  numbers (PCB 1.09, USB overhang 1.21 / width 8.94 — calipers), tact leg pairing.
  Optional hardware fix not taken: a Schottky/ideal diode between switch and `5V`.
