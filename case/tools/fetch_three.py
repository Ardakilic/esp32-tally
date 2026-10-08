#!/usr/bin/env python3
"""Download the latest three.js ES-module build into vendor/.

Stdlib only, so it runs in a bare python:3.14-slim container (see Makefile's
`vendor` target). three.js dropped its UMD build after r160 — the previews
embed the module build and load it via a blob dynamic import.
"""

import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(os.path.dirname(HERE), "vendor")


def main():
    meta = json.load(urllib.request.urlopen(
        "https://registry.npmjs.org/three/latest"))
    version = meta["version"]
    print(f"downloading three.js {version} …")

    os.makedirs(VENDOR, exist_ok=True)
    # since r167 the module build is split in two: three.module.min.js does
    # `import ... from "./three.core.min.js"` — the previews embed both and
    # patch that specifier to a blob URL at load time
    # jsdelivr, not unpkg: since r186 the npm package ships no .min.js files
    # any more, and jsdelivr minifies the plain build on the fly (the module
    # then imports "./three.core.js" — the template patches both spellings)
    for name in ("three.module.min.js", "three.core.min.js"):
        url = f"https://cdn.jsdelivr.net/npm/three@{version}/build/{name}"
        data = urllib.request.urlopen(url).read()
        out = os.path.join(VENDOR, name)
        with open(out, "wb") as f:
            f.write(data)
        print(f"saved {out} ({len(data) / 1e6:.2f} MB)")

    with open(os.path.join(VENDOR, "THREE_VERSION"), "w") as f:
        f.write(version + "\n")


if __name__ == "__main__":
    main()
