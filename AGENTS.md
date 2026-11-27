# AGENTS.md

Instructions for AI coding agents working in this repo live in
**[CLAUDE.md](CLAUDE.md)** — read it first. The essentials:

- Everything (case STLs, README images, `case/preview.html`, `index.html`, all
  three firmware binaries) is **generated**; never edit `case/stl/*` (incl.
  `case/stl/rp2040-zero/`), `case/docs/*` (incl. `case/docs/rp2040-zero/`),
  `case/preview.html`, `index.html`, `case/vendor/*` or any build output by hand.
  All builds run in Docker via `make` — nothing is installed on the host, no
  local venv/pio. GitHub Pages publishes the checkout as-is on push to `main`.
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:a3e684ce3c6334093460d2b1645d088370de9fb888173b37c86720d9ded119b5 -->

- Three firmwares, one behaviour contract:
  - `firmware/plain/` (PlatformIO, pioarduino, U8g2) and
    `firmware/esphome/tally.yaml` (ESPHome 2026.9.1, esp-idf) on the ESP32-C3 Super
    Mini: UP GPIO3, DOWN GPIO4, OLED SDA GPIO6 / SCL GPIO7 @0x3C.
  - `firmware/rp2040/` (PlatformIO + Arduino-Pico 6.1.0 on maxgerhardt's platform
    @5d4561a, U8g2, LittleFS, DORMANT + reboot on wake) on the Waveshare RP2040-Zero:
    UP GP26, DOWN GP8, OLED SDA GP14 / SCL GP15 on I2C1 (`Wire1`) @0x3C. It includes
    `firmware/plain/src/tally_logic.h` on purpose (one state machine, covered by
    `make plain-test`).
  - Every build keeps a wake source armed while asleep: plain re-checks a button that
    is down at sleep time with a 10 s timer (`deepSleep()`), ESPHome waits for UP
    (`KEEP_AWAKE`), the RP2040 wakes on its release. Plain only: `r<reset reason>` in
    the OLED's top-left corner after any boot that is not a deep-sleep wake.
  - A dark OLED alone is inconclusive. For ESP32 troubleshooting and recovery,
    follow [README → Field notes](README.md#field-notes).
  - Both modules' `5V` pin is USB VBUS — the ESP32 case hides that port on purpose
    (don't "fix" it); the RP2040-Zero case leaves it in an open end window because
    no wall fits in front of it.

<!-- /coderabbit-ai-generated:v1 -->
- The RP2040-Zero sits on the same perfboard holes (cols 3 and 9, rows 0…8) but its
  pinout is mirrored: 5V/GND/3V3 are on col 9. The case variant is `--mcu
  rp2040-zero` (an `MCUS` table in `case/generate.py`; base + lid only, caps shared).
- Case fit parameters are CLI flags, not constants to edit: `--clear-friction`
  0.28, `--snap-bite` 0.4 (PLA ~0.3, `0` = friction-only lid), `--tact-height`
  4.3, `--battery 34x52x6`, passed as `make case GEN_ARGS="..."` — the same
  `GEN_ARGS` must go to `make case-verify` (both apply them to both modules).
  Lid text likewise: `make case ENGRAVING="My Text"` / `OMIT_ENGRAVING=1` (they
  append `--engraving` / `--omit-engraving` to `GEN_ARGS`).
- The perfboard is an Özdisan 5 × 5 cm single-sided board used whole (50 × 50 mm,
  18 × 19 holes); every placement is `hole(col, row)` in `case/generate.py`.
- Toolchains are pinned (`python:3.14-slim` + `case/requirements.txt`,
  `python:3.12-slim` + platformio 6.2.0 for both PlatformIO builds,
  `ghcr.io/esphome/esphome:2026.9.1`); bumping a pin re-triangulates every STL —
  regenerate, verify, commit together.

```bash
make case-verify     # both modules: 105 + 104 geometry checks (70 + 69 with --snap-bite 0, 101 + 100 with OMIT_ENGRAVING=1), exit 1 on failure — run before committing case changes
make case            # regenerate case/stl (+ rp2040-zero/) + case/preview.html + index.html + case/docs (+ rp2040-zero/)
make case ENGRAVING="My Text"   # other lid text; OMIT_ENGRAVING=1 for a plain lid
make vendor          # refresh three.js in case/vendor/ (only when you want a newer release)
make plain-test      # state-machine self-test (gcc:14) — run before committing firmware/plain or firmware/rp2040 changes
make plain           # -> firmware/plain/build/tally-plain.factory.bin
make rp2040          # -> firmware/rp2040/build/tally-rp2040.uf2 (flash: hold BOOT, plug in, copy to RPI-RP2)
make esphome-config  # validate tally.yaml (needs firmware/esphome/secrets.yaml, from .example)
make esphome         # -> firmware/esphome/.esphome/build/tally/build/firmware.factory.bin
```

Keep README.md (BOM, wiring tables, fit-tuning table, part sizes), CLAUDE.md and
this file in sync with the constants in `case/generate.py` and the three firmwares.
