# AGENTS.md

Instructions for AI coding agents working in this repo live in
**[CLAUDE.md](CLAUDE.md)** — read it first. The essentials:

- Everything (case STLs, README images, `case/preview.html`, `index.html`, both
  firmware binaries) is **generated**; never edit `case/stl/*`, `case/docs/*`,
  `case/preview.html`, `index.html`, `case/vendor/*` or any build output by hand.
  All builds run in Docker via `make` — nothing is installed on the host, no
  local venv/pio. GitHub Pages publishes the checkout as-is on push to `main`.
- Two firmwares, one behaviour contract: `firmware/plain/` (PlatformIO, pioarduino,
  U8g2) and `firmware/esphome/tally.yaml` (ESPHome 2026.9.1, esp-idf). Pins:
  UP GPIO3, DOWN GPIO4, OLED SDA GPIO6 / SCL GPIO7 @0x3C. The ESP32's `5V` pin is
  USB VBUS — the case hides that port on purpose; don't "fix" it.
- Case fit parameters are CLI flags, not constants to edit: `--clear-friction`
  0.28, `--tact-height` 5.0, `--battery 34x52x6`, passed as
  `make case GEN_ARGS="..."` — the same `GEN_ARGS` must go to `make case-verify`.
  Lid text likewise: `make case ENGRAVING="My Text"` / `OMIT_ENGRAVING=1` (they
  append `--engraving` / `--omit-engraving` to `GEN_ARGS`).
- The perfboard is an Özdisan 5 × 5 cm single-sided board used whole (50 × 50 mm,
  18 × 19 holes); every placement is `hole(col, row)` in `case/generate.py`.
- Toolchains are pinned (`python:3.14-slim` + `case/requirements.txt`,
  `python:3.12-slim` + platformio 6.2.0, `ghcr.io/esphome/esphome:2026.9.1`);
  bumping a pin re-triangulates every STL — regenerate, verify, commit together.

```bash
make case-verify     # 68 geometry checks (64 with --omit-engraving), exit 1 on failure — run before committing case changes
make case            # regenerate case/stl + case/preview.html + index.html + case/docs
make case ENGRAVING="My Text"   # other lid text; OMIT_ENGRAVING=1 for a plain lid
make vendor          # refresh three.js in case/vendor/ (only when you want a newer release)
make plain-test      # state-machine self-test (gcc:14) — run before committing firmware/plain changes
make plain           # -> firmware/plain/build/tally-plain.factory.bin
make esphome-config  # validate tally.yaml (needs firmware/esphome/secrets.yaml, from .example)
make esphome         # -> firmware/esphome/.esphome/build/tally/build/firmware.factory.bin
```

Keep README.md (BOM, wiring table, fit-tuning table, part sizes), CLAUDE.md and
this file in sync with the constants in `case/generate.py` and the two firmwares.
