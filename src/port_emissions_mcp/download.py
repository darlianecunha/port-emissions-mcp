"""Download the Brazil Port Data tables from Zenodo into a local cache.

    port-emissions-mcp download              # uses the default record
    port-emissions-mcp download --record ID  # a specific Zenodo record

Only the Python standard library is used. Files go to the cache folder
(see data.CACHE_DIR); the server uses them automatically when PORT_DATA_DIR
is not set.
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

ZENODO_API = os.environ.get("ZENODO_API", "https://zenodo.org/api")
# Concept record of "Brazil Port Data: consolidated ANTAQ port statistics"
# (doi:10.5281/zenodo.23158267). It always resolves to the latest version.
DEFAULT_RECORD = os.environ.get("PORT_DATA_ZENODO_RECORD", "23158267")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "port-emissions-mcp"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def file_links(record: str) -> dict[str, str]:
    """Map file name -> download URL for the latest version of a Zenodo record."""
    try:
        meta = json.loads(_get(f"{ZENODO_API}/records/{record}/versions/latest"))
    except Exception:
        meta = json.loads(_get(f"{ZENODO_API}/records/{record}"))
    links = {}
    for f in meta.get("files", []):
        name = f.get("key") or f.get("filename")
        url = (f.get("links") or {}).get("self") or (f.get("links") or {}).get("download")
        if name and url:
            links[Path(name).name] = url
    return links


def download(record: str, dest: Path) -> list[str]:
    from .data import FILES  # local import keeps this module light

    if not record:
        raise SystemExit(
            "No Zenodo record set. Pass --record ID or set PORT_DATA_ZENODO_RECORD."
        )
    links = file_links(record)
    needed = list(FILES.values())
    dest.mkdir(parents=True, exist_ok=True)
    if all(n in links for n in needed):  # files uploaded one by one
        for name in needed:
            (dest / name).write_bytes(_get(links[name]))
    else:  # GitHub-integration records hold one zip of the repository
        zips = [u for n, u in links.items() if n.endswith(".zip")]
        if not zips:
            raise SystemExit(f"Record {record} has neither the tables nor a zip.")
        with zipfile.ZipFile(io.BytesIO(_get(zips[0]))) as z:
            members = {Path(m).name: m for m in z.namelist() if not m.endswith("/")}
            missing = [n for n in needed if n not in members]
            if missing:
                raise SystemExit(f"Record {record} does not contain: {missing}")
            for name in needed:
                (dest / name).write_bytes(z.read(members[name]))
    (dest / "SOURCE.txt").write_text(f"Zenodo record {record}\n", encoding="utf-8")
    return needed


def cli(argv: list[str]) -> None:
    from .data import CACHE_DIR

    record = DEFAULT_RECORD
    if "--record" in argv:
        record = argv[argv.index("--record") + 1]
    files = download(record, CACHE_DIR)
    print(f"Downloaded {len(files)} files from Zenodo record {record} to {CACHE_DIR}")
    print("The server will use them automatically (unless PORT_DATA_DIR is set).")


if __name__ == "__main__":
    cli(sys.argv[1:])
