# ESP32 Tally Counter — every command runs inside Docker; nothing is installed
# on the host. Requires only Docker and make.
#
#   make                 # everything: case STLs + README images + all three firmwares
#   make case            # case/stl/*.stl + case/docs/*.png + case/preview.html
#                        # + index.html, and the RP2040-Zero variant's
#                        # case/stl/rp2040-zero/ + case/docs/rp2040-zero/
#                        # (builds the image first)
#   make case-verify     # measure every part in memory (ray casts, sections),
#                        # both modules: exit 1 on any failure — takes GEN_ARGS too
#   make plain           # PlatformIO build -> firmware/plain/build/tally-plain.factory.bin
#   make plain-test      # host self-test of the button/count state machine (gcc:14)
#   make rp2040          # RP2040-Zero build -> firmware/rp2040/build/tally-rp2040.uf2
#                        # (hold BOOT, plug in, copy to the RPI-RP2 drive)
#   make esphome         # ESPHome compile -> firmware/esphome/.esphome/build/tally/build/
#                        # firmware.factory.bin (needs firmware/esphome/secrets.yaml)
#   make esphome-config  # validate tally.yaml only
#   make esphome-ota     # compile + OTA to DEVICE (default tally.local); turn on
#                        # the "Keep Awake" switch in HA first
#   make vendor          # fetch the latest three.js module build into case/vendor/
#   make image-case      # (re)build the case Docker image
#   make image-plain     # (re)build the PlatformIO Docker image
#   make clean           # delete all generated outputs (Docker volumes stay)
#
# Fit tolerances can be overridden per run (see README -> Fit tuning):
#   make case GEN_ARGS="--clear-friction 0.32 --tact-height 4.3"
# Lid engraving (default "Grindarr"):
#   make case ENGRAVING="My Text"     # -> --engraving "My Text"
#   make case OMIT_ENGRAVING=1        # -> --omit-engraving (plain lid top)

IMAGE_CASE    := esp32-tally-case
IMAGE_PLAIN   := esp32-tally-plain
ESPHOME_IMAGE := ghcr.io/esphome/esphome:2026.9.1
GCC_IMAGE     := gcc:14
VOL_PIO       := esp32-tally-pio
VOL_ESPHOME   := esp32-tally-esphome-cache
GEN_ARGS      ?=
ENGRAVING     ?=          # make case ENGRAVING="My Text"   -> --engraving "My Text"
OMIT_ENGRAVING ?=         # make case OMIT_ENGRAVING=1      -> --omit-engraving
override GEN_ARGS += $(if $(ENGRAVING),--engraving "$(ENGRAVING)") $(if $(OMIT_ENGRAVING),--omit-engraving)
DEVICE        ?= tally.local

# the whole repo is mounted (generate.py writes the Pages index.html to the root)
RUN         := docker run --rm -v "$(CURDIR)":/app -w /app/case
RUN_CASE    := $(RUN) $(IMAGE_CASE)
RUN_PLAIN   := docker run --rm -v "$(CURDIR)":/app -w /app/firmware/plain -v $(VOL_PIO):/pio $(IMAGE_PLAIN)
# same PlatformIO image and package volume: only the platform differs, which pio fetches per project
RUN_RP2040  := docker run --rm -v "$(CURDIR)":/app -w /app/firmware/rp2040 -v $(VOL_PIO):/pio $(IMAGE_PLAIN)
RUN_ESPHOME := docker run --rm -v "$(CURDIR)":/app -w /app/firmware/esphome -v $(VOL_ESPHOME):/cache $(ESPHOME_IMAGE)
SECRETS     := firmware/esphome/secrets.yaml

.PHONY: all case case-verify vendor image-case plain plain-test image-plain \
        rp2040 esphome esphome-config esphome-ota clean

all: case plain rp2040 esphome

# ---- case ------------------------------------------------------------------

image-case:
	docker build -t $(IMAGE_CASE) case

# one pass per module, the same GEN_ARGS each, the --mcu flag last (it wins
# over one in GEN_ARGS). The RP2040-Zero pass (stl/rp2040-zero/ base + lid,
# docs/rp2040-zero/) runs first, so the default pass's index.html can list
# the variant STL sizes; only the default pass writes preview.html + index.html
case: image-case
	$(RUN_CASE) python3 generate.py $(GEN_ARGS) --mcu rp2040-zero
	$(RUN_CASE) python3 tools/render_docs.py $(GEN_ARGS) --mcu rp2040-zero
	$(RUN_CASE) python3 generate.py $(GEN_ARGS) --mcu esp32-c3
	$(RUN_CASE) python3 tools/render_docs.py $(GEN_ARGS) --mcu esp32-c3

# the ray-cast extras go into the throwaway container only, never the image;
# both modules are verified (the second runs even if the first fails)
case-verify: image-case
	$(RUN_CASE) sh -c 'pip install -q --root-user-action=ignore \
		-r requirements-dev.txt && { python3 tools/verify.py $(GEN_ARGS) --mcu esp32-c3; s=$$?; \
		python3 tools/verify.py $(GEN_ARGS) --mcu rp2040-zero || s=1; exit $$s; }'

# stdlib-only fetcher, so the bare image does (vendor/ is committed)
vendor:
	$(RUN) python:3.14-slim python3 tools/fetch_three.py

# ---- plain firmware (PlatformIO, no network) -------------------------------

image-plain:
	docker build -t $(IMAGE_PLAIN) firmware/plain

# pioarduino already emits firmware.factory.bin (bootloader 0x0 + partitions
# 0x8000 + boot_app0 0xe000 + app 0x10000), so a copy is all it takes
plain: image-plain
	$(RUN_PLAIN) pio run
	$(RUN_PLAIN) sh -c 'mkdir -p build && cp .pio/build/supermini/firmware.factory.bin build/tally-plain.factory.bin'
	@echo "-> firmware/plain/build/tally-plain.factory.bin"

plain-test:
	docker run --rm -v "$(CURDIR)/firmware":/work -w /work/plain $(GCC_IMAGE) sh -c \
		'g++ -std=c++17 -Wall -Wextra -Werror -Isrc -I../common test/tally_logic_test.cpp -o /tmp/t && /tmp/t'

# ---- RP2040-Zero firmware (PlatformIO, Arduino-Pico, no network) -----------

# every pio run emits firmware.uf2 (picotool uf2 convert) next to the .elf;
# it shares tally_logic.h with the plain build, so plain-test covers its logic
rp2040: image-plain
	$(RUN_RP2040) pio run
	$(RUN_RP2040) sh -c 'mkdir -p build && cp .pio/build/zero/firmware.uf2 build/tally-rp2040.uf2'
	@echo "-> firmware/rp2040/build/tally-rp2040.uf2"

# ---- ESPHome firmware (Home Assistant) -------------------------------------

$(SECRETS):
	@echo "$(SECRETS) is missing: cp $(SECRETS).example $(SECRETS) and fill in" \
	     "wifi_ssid / wifi_password / api_key / ap_password (README -> ESPHome)"; exit 1

esphome: $(SECRETS)
	$(RUN_ESPHOME) compile tally.yaml
	@echo "-> firmware/esphome/.esphome/build/tally/build/firmware.factory.bin (first flash over USB)"
	@echo "-> firmware/esphome/.esphome/build/tally/build/firmware.ota.bin     (OTA)"

esphome-config: $(SECRETS)
	$(RUN_ESPHOME) config tally.yaml

esphome-ota: $(SECRETS)
	$(RUN_ESPHOME) run tally.yaml --device $(DEVICE)

clean:
	rm -rf case/stl case/docs firmware/plain/.pio firmware/plain/build firmware/esphome/.esphome \
	       firmware/rp2040/.pio firmware/rp2040/build
	rm -f case/preview.html index.html
