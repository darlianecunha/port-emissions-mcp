"""Loading of aggregated ANTAQ port statistics.

The server never ships the consolidated ANTAQ tables. It reads them from the
folder named in the environment variable PORT_DATA_DIR, or from the tables
downloaded from Zenodo with `port-emissions-mcp download`. Otherwise it falls back to the small SYNTHETIC example in example_data/, so the
server can be installed and tested by anyone without the real data.
"""
from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
from mcp.server.mcpserver.exceptions import ToolError

EXAMPLE_DIR = Path(__file__).resolve().parent / "example_data"
# Where `port-emissions-mcp download` puts the Zenodo tables.
CACHE_DIR = Path(os.environ.get("PORT_DATA_CACHE", Path.home() / ".cache" / "port-emissions-mcp"))

FILES = {
    "cargo": "cargo_by_installation_2010_2026.csv",
    "navigation": "cargo_by_navigation_2010_2026.csv",
    "berthings": "berthings_by_installation_2010_2026.csv",
    "times": "port_times_by_installation_2010_2026.csv",
    "installations": "installations_2023_2025.csv",
}

# Last year with complete data. Rows after it are partial and flagged.
LAST_FULL_YEAR = int(os.environ.get("PORT_LAST_FULL_YEAR", "2025"))


def _norm(text: str) -> str:
    """Lower case, no accents, single spaces (for name search)."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().split())


@dataclass
class PortData:
    source: str  # "real" or "synthetic example"
    folder: Path
    cargo: pd.DataFrame
    navigation: pd.DataFrame
    berthings: pd.DataFrame
    times: pd.DataFrame
    names: pd.DataFrame  # columns: codigo, installation, complexo


def _build_names(cargo: pd.DataFrame, inst: pd.DataFrame) -> pd.DataFrame:
    """Link installation names to ANTAQ codes.

    installations_2023_2025.csv has names but no codes. Names are linked to
    codes by matching rounded tonnage in 2024 AND 2025; only one-to-one matches
    are kept, so a wrong link is very unlikely. Codes without a name keep the
    complex name.
    """
    wide = (
        cargo[cargo["ano"].isin([2024, 2025])]
        .assign(t=lambda d: d["toneladas"].round().astype("int64"))
        .pivot_table(index=["codigo", "complexo"], columns="ano", values="t", aggfunc="first")
        .reset_index()
    )
    wide.columns = [str(c) for c in wide.columns]
    if {"2024", "2025"} <= set(wide.columns):
        m = inst.merge(wide, left_on=["tonnes_2024", "tonnes_2025"], right_on=["2024", "2025"], how="inner")
        m = m[~m["codigo"].duplicated(keep=False) & ~m["installation"].duplicated(keep=False)]
        named = m[["codigo", "installation", "complexo"]]
    else:
        named = pd.DataFrame(columns=["codigo", "installation", "complexo"])
    codes = cargo[["codigo", "complexo"]].drop_duplicates("codigo")
    out = codes.merge(named[["codigo", "installation"]], on="codigo", how="left")
    out["installation"] = out["installation"].fillna(out["complexo"])
    out["_key"] = (out["installation"] + " " + out["complexo"] + " " + out["codigo"]).map(_norm)
    return out


@lru_cache(maxsize=1)
def load() -> PortData:
    # Order: PORT_DATA_DIR, then the Zenodo download cache, then synthetic data.
    env = os.environ.get("PORT_DATA_DIR")
    if env:
        folder, source = Path(env).expanduser(), "real"
    elif (CACHE_DIR / FILES["cargo"]).exists():
        folder, source = CACHE_DIR, "real (Zenodo download)"
    else:
        folder, source = EXAMPLE_DIR, "synthetic example"
    missing = [f for f in FILES.values() if not (folder / f).exists()]
    if missing:
        raise FileNotFoundError(f"Missing files in {folder}: {missing}")
    read = {k: pd.read_csv(folder / f) for k, f in FILES.items()}
    return PortData(
        source=source,
        folder=folder,
        cargo=read["cargo"],
        navigation=read["navigation"],
        berthings=read["berthings"],
        times=read["times"],
        names=_build_names(read["cargo"], read["installations"]),
    )


def search(query: str, limit: int = 10) -> pd.DataFrame:
    """Find installations whose name, complex or code contains all query words."""
    d = load()
    words = _norm(query).split()
    mask = d.names["_key"].map(lambda k: all(w in k for w in words))
    return d.names.loc[mask, ["codigo", "installation", "complexo"]].head(limit)


def resolve(code_or_name: str) -> str:
    """Return an ANTAQ code from a code or an unambiguous name."""
    d = load()
    code = code_or_name.strip().upper()
    if code in set(d.names["codigo"]):
        return code
    # An exact name wins, e.g. "Paranaguá" is the public port, not Cattalini.
    exact = d.names[d.names["installation"].map(_norm) == _norm(code_or_name)]
    if len(exact) == 1:
        return exact.iloc[0]["codigo"]
    hits = search(code_or_name)
    if len(hits) == 1:
        return hits.iloc[0]["codigo"]
    # ToolError messages reach Claude, so it can correct itself.
    if hits.empty:
        raise ToolError(f"No installation matches '{code_or_name}'. Use find_installation first.")
    options = "; ".join(f"{r.codigo} ({r.installation})" for r in hits.itertuples())
    raise ToolError(f"'{code_or_name}' is ambiguous: {options}. Pass the ANTAQ code.")


def label(code: str) -> str:
    row = load().names.set_index("codigo").loc[code]
    return f"{row['installation']} ({code}, complex {row['complexo']})"
