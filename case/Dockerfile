# Build image for the tally case generator — all commands run in here, nothing
# is installed on the host (see README -> Case).
# python:3.14-slim = Python 3.14 on Debian slim (pre-built wheels work, small
# footprint). Pinned to the minor on purpose, together with requirements.txt:
# a floating `python:3-slim` + unpinned wheels silently re-triangulate every
# published STL (same geometry, different bytes) on the next image rebuild.
# No fonts: the only "text" on the parts is the + / - cap symbols, built from
# rectangles.
FROM python:3.14-slim

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
