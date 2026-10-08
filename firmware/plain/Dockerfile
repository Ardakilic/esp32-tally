# Build image for the plain firmware — see ../../Makefile. Pinned like the CAD image: a floating
# platformio or esptool silently changes the produced binary.
FROM python:3.12-slim
# pioarduino's platform.py refuses to run without git, even when installed from a release zip
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir platformio==6.2.0
ENV PLATFORMIO_CORE_DIR=/pio
WORKDIR /work
