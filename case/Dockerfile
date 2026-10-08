# Build image for the tally case generator — all commands run in here, nothing
# is installed on the host (see README -> Case).
# python:3.14-slim = Python 3.14 on Debian slim (pre-built wheels work, small
# footprint). Pinned to the minor on purpose, together with requirements.txt:
# a floating `python:3-slim` + unpinned wheels silently re-triangulate every
# published STL (same geometry, different bytes) on the next image rebuild.
FROM python:3.14-slim

# Liberation Sans: metric-compatible Arial substitute for the lid engraving.
# The one input left unpinned on purpose (a hard apt pin would break the build
# at the next Debian point release). The canonical output was built with
# fonts-liberation 1:2.1.5-3, LiberationSans-Bold.ttf md5
# 3073c99843570b858634c66019a17b7f — a changed font re-triangulates only the
# engraved lid (tally-lid.stl), nothing else.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
