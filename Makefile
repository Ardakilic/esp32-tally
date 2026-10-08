# ESP32 Tally Counter — every command runs inside Docker; nothing is installed
# on the host. Requires only Docker and make.
#
#   make                 # everything: case STLs + README images + both firmwares
#   make case            # case/stl/*.stl + case/docs/*.png + case/preview.html
#                        # + index.html (builds the image first)
#   make case-verify     # measure every part in memory (ray casts, sections):
#                        # exit 1 on any failure — takes GEN_ARGS too
#   make plain           # PlatformIO build -> firmware/plain/build/tally-plain.factory.bin
#   make plain-test      # host self-test of the button/count state machine (gcc:14)
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
RUN_PLAIN   := docker run --rm -v "$(CURDIR)/firmware/plain":/work -v $(VOL_PIO):/pio $(IMAGE_PLAIN)
RUN_ESPHOME := docker run --rm -v "$(CURDIR)/firmware/esphome":/config -v $(VOL_ESPHOME):/cache $(ESPHOME_IMAGE)
SECRETS     := firmware/esphome/secrets.yaml

.PHONY: all case case-verify vendor image-case plain plain-test image-plain \
        esphome esphome-config esphome-ota clean

all: case plain esphome

# ---- case ------------------------------------------------------------------

image-case:
	docker build -t $(IMAGE_CASE) case

case: image-case
	$(RUN_CASE) python3 generate.py $(GEN_ARGS)
	$(RUN_CASE) python3 tools/render_docs.py $(GEN_ARGS)

# the ray-cast extras go into the throwaway container only, never the image
case-verify: image-case
	$(RUN_CASE) sh -c 'pip install -q --root-user-action=ignore \
		-r requirements-dev.txt && python3 tools/verify.py $(GEN_ARGS)'

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
	docker run --rm -v "$(CURDIR)/firmware/plain":/work -w /work $(GCC_IMAGE) sh -c \
		'g++ -std=c++17 -Wall -Wextra -Werror -Isrc test/tally_logic_test.cpp -o /tmp/t && /tmp/t'

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
	rm -rf case/stl case/docs firmware/plain/.pio firmware/plain/build firmware/esphome/.esphome
	rm -f case/preview.html index.html
