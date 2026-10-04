"""MCP server: CO2 at berth and Brazilian port statistics for Claude.

Tools
- estimate_berth_co2      one call, OPS-avoidable CO2 (maritime-co2 library)
- estimate_calls_co2      many calls at once, totals by size band
- find_installation       search ANTAQ installations by name, complex or code
- port_profile            cargo, navigation mix, berthings and port times by year
- compare_ports           one indicator, several installations, one year
- explain_method          method, parameters and sources behind the numbers
"""
from __future__ import annotations

from typing import Literal

import pandas as pd
from maritime_co2 import AUX_PROFILE, CARBON_FACTORS, DEFAULT_SFOC, auxiliary_emissions, band_for_dwt
from mcp.server.mcpserver import MCPServer

from . import data

INSTRUCTIONS = """\
Tools for at-berth CO2 of liquid-bulk vessels and for Brazilian port statistics
(ANTAQ, aggregated by Brazil Port Data). Always report the source and the year of
the data, say when a year is partial, and remind the user that the CO2 defaults
are illustrative IMO-aligned values, not vessel-specific measurements."""

mcp = MCPServer(name="port-emissions", instructions=INSTRUCTIONS, version="0.1.0")

SOURCE_STATS = "ANTAQ Estatístico Aquaviário, aggregated by Brazil Port Data (brazilportdata.com), licence ODbL 1.0"
SOURCE_CO2 = "maritime-co2 v0.1.0 (doi:10.5281/zenodo.20708090), IMO Fourth GHG Study 2020 method"


def _year_note(year: int) -> str | None:
    if year > data.LAST_FULL_YEAR:
        return f"{year} is a partial year (not all months); do not compare it with full years."
    return None


def _meta() -> dict:
    d = data.load()
    meta = {"source": SOURCE_STATS, "dataset": d.source}
    if d.source == "synthetic example":
        meta["warning"] = "SYNTHETIC example data: numbers are invented. Set PORT_DATA_DIR to use real data."
    return meta


@mcp.tool()
def estimate_berth_co2(
    dwt: float,
    berth_hours: float,
    fuel: Literal["MDO", "MGO", "HFO"] = "MDO",
    sfoc_g_per_kwh: float = DEFAULT_SFOC,
) -> dict:
    """Estimate the at-berth CO2 of ONE liquid-bulk (tanker) call from the auxiliary engine,
    i.e. the CO2 that Onshore Power Supply (shore power) would avoid. Boilers are excluded.

    Args:
        dwt: deadweight tonnage of the vessel.
        berth_hours: hours at berth (from berthing to unberthing).
        fuel: fuel burnt by the auxiliary engine.
        sfoc_g_per_kwh: specific fuel oil consumption, default 215 g/kWh.
    """
    band = band_for_dwt(dwt)
    p = AUX_PROFILE[band]
    r = auxiliary_emissions(p["aux_power_kw"], p["load_factor"], berth_hours, fuel, sfoc_g_per_kwh)
    return {
        "size_band": band,
        "aux_power_kw": p["aux_power_kw"],
        "load_factor": p["load_factor"],
        "energy_kwh": round(r.energy_kwh, 1),
        "fuel_tonnes": round(r.fuel_tonnes, 3),
        "co2_tonnes": round(r.co2_tonnes, 3),
        "formula": "CO2 = aux_kW x load_factor x hours x SFOC / 1e6 x Cf",
        "carbon_factor": CARBON_FACTORS[fuel],
        "source": SOURCE_CO2,
        "caveat": "Auxiliary power and load factor are illustrative defaults by DWT band, not vessel-specific.",
    }


@mcp.tool()
def estimate_calls_co2(calls: list[dict], fuel: Literal["MDO", "MGO", "HFO"] = "MDO") -> dict:
    """Estimate at-berth (OPS-avoidable) CO2 for MANY liquid-bulk calls and sum it.

    Args:
        calls: list of objects with keys "dwt" and "berth_hours" (optional "call_id").
        fuel: fuel burnt by the auxiliary engine.
    """
    rows = []
    for i, c in enumerate(calls, 1):
        out = estimate_berth_co2(float(c["dwt"]), float(c["berth_hours"]), fuel)
        rows.append({"call_id": c.get("call_id", i), "size_band": out["size_band"], "co2_tonnes": out["co2_tonnes"]})
    df = pd.DataFrame(rows)
    by_band = df.groupby("size_band")["co2_tonnes"].agg(["count", "sum"]).round(2).reset_index()
    return {
        "n_calls": len(df),
        "total_co2_tonnes": round(df["co2_tonnes"].sum(), 2),
        "by_size_band": by_band.to_dict("records"),
        "source": SOURCE_CO2,
    }


@mcp.tool()
def find_installation(query: str) -> dict:
    """Search Brazilian port installations (public ports and private terminals) by name,
    port complex or ANTAQ code, e.g. "Itaqui", "Ponta da Madeira", "Paranagua", "BRSSZ".
    Returns ANTAQ codes to use in the other tools."""
    hits = data.search(query, limit=15)
    return {"matches": hits.to_dict("records"), **_meta()}


@mcp.tool()
def port_profile(installation: str, start_year: int = 2019, end_year: int = 2025) -> dict:
    """Year-by-year profile of one installation: cargo handled (tonnes), split by navigation
    type, number of cargo berthings and mean port times (waiting, operation, at berth).

    Args:
        installation: ANTAQ code (e.g. BRIQI) or an unambiguous name.
        start_year, end_year: period, inclusive (data from 2010).
    """
    code = data.resolve(installation)
    d = data.load()
    sel = lambda df: df[(df["codigo"] == code) & df["ano"].between(start_year, end_year)]  # noqa: E731
    out = (
        sel(d.cargo)[["ano", "toneladas"]]
        .merge(sel(d.navigation)[["ano", "longo_curso_t", "cabotagem_t", "vias_interiores_t"]], on="ano", how="left")
        .merge(sel(d.berthings)[["ano", "atracacoes"]], on="ano", how="left")
        .merge(
            sel(d.times)[["ano", "t_espera_atracacao_h", "t_operacao_h", "t_atracado_h", "t_estadia_h"]],
            on="ano",
            how="left",
        )
        .sort_values("ano")
        .round(1)
    )
    notes = [n for y in out["ano"] if (n := _year_note(int(y)))]
    return {
        "installation": data.label(code),
        "columns": {
            "toneladas": "cargo handled, tonnes",
            "longo_curso_t / cabotagem_t / vias_interiores_t": "tonnes by navigation type (deep sea, cabotage, inland)",
            "atracacoes": "berthings with authorised cargo operations",
            "t_espera_atracacao_h": "mean hours from anchorage to berth",
            "t_atracado_h": "mean hours at berth",
            "t_estadia_h": "mean total stay, hours",
        },
        "rows": out.to_dict("records"),
        "notes": notes,
        **_meta(),
    }


INDICATORS = {
    "tonnes": ("cargo", "toneladas"),
    "berthings": ("berthings", "atracacoes"),
    "waiting_hours": ("times", "t_espera_atracacao_h"),
    "hours_at_berth": ("times", "t_atracado_h"),
    "total_stay_hours": ("times", "t_estadia_h"),
}


@mcp.tool()
def compare_ports(
    installations: list[str],
    indicator: Literal["tonnes", "berthings", "waiting_hours", "hours_at_berth", "total_stay_hours"],
    year: int = 2025,
) -> dict:
    """Compare several installations on one indicator in one year, ranked high to low.

    Args:
        installations: ANTAQ codes or unambiguous names.
        indicator: tonnes, berthings, waiting_hours, hours_at_berth or total_stay_hours.
        year: reference year.
    """
    table, col = INDICATORS[indicator]
    df = getattr(data.load(), table)
    rows = []
    for item in installations:
        code = data.resolve(item)
        v = df[(df["codigo"] == code) & (df["ano"] == year)][col]
        rows.append({"installation": data.label(code), indicator: None if v.empty else round(float(v.iloc[0]), 1)})
    rows.sort(key=lambda r: (r[indicator] is None, -(r[indicator] or 0)))
    return {"year": year, "indicator": indicator, "rows": rows, "notes": [n for n in [_year_note(year)] if n], **_meta()}


@mcp.tool()
def explain_method(topic: Literal["berth_co2", "port_statistics", "port_times"]) -> str:
    """Explain the method, parameters and sources behind a tool's numbers."""
    if topic == "berth_co2":
        bands = "; ".join(f"{k}: up to {v['max_dwt']:,.0f} DWT, {v['aux_power_kw']} kW, LF {v['load_factor']}" for k, v in AUX_PROFILE.items())
        return (
            "At-berth CO2 of liquid-bulk vessels, auxiliary engine only (the load that Onshore Power "
            "Supply replaces; boilers keep running for cargo heating and are excluded). "
            "energy_kWh = aux_power_kW x load_factor x berth_hours; fuel_t = energy_kWh x SFOC / 1e6; "
            f"CO2_t = fuel_t x Cf. Cf: {CARBON_FACTORS}. SFOC default {DEFAULT_SFOC} g/kWh. "
            f"Size bands: {bands}. Sources: IMO Fourth GHG Study 2020; IMO MEPC.391(81). "
            f"Implementation: {SOURCE_CO2}. Power and load factor are illustrative defaults."
        )
    if topic == "port_statistics":
        return (
            "Cargo is ANTAQ's port movement: gross weight (tonnes) handled in authorised operations "
            "(FlagAutorizacao = S) that count as movement (FlagMCOperacaoCarga = 1), the same filter as "
            "ANTAQ's public panel. Berthings count distinct berthing records with authorised cargo "
            "operations, so they are lower than raw ANTAQ berthing counts. Coverage 2010 onwards; "
            f"years after {data.LAST_FULL_YEAR} are partial. Source: {SOURCE_STATS}."
        )
    return (
        "Port times are annual means per installation, in hours: waiting = anchorage to berth; "
        "operation = cargo operation; at berth = berthing to unberthing; stay = arrival to departure. "
        f"Source: {SOURCE_STATS}."
    )


def main() -> None:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "download":
        from .download import cli

        cli(sys.argv[2:])
        return
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
