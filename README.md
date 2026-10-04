# port-emissions-mcp

**An MCP server that lets Claude estimate the at-berth CO₂ of tankers and answer questions about Brazilian ports (247 ANTAQ installations, 2010 to 2026), with the source and the method behind every number**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![MCP](https://img.shields.io/badge/Model_Context_Protocol-server-6E56CF)](https://modelcontextprotocol.io)
[![Built on maritime-co2](https://img.shields.io/badge/built_on-maritime--co2-2ea44f)](https://github.com/darlianecunha/maritimeco2)

<!-- Add docs/gallery/demo.gif: a 30-60 s recording of a conversation in Claude Desktop -->

## What this is

The [Model Context Protocol](https://modelcontextprotocol.io) (MCP) lets an AI assistant call external tools. This server gives Claude six tools that join two pieces of my work: the **maritime-co2** library (at-berth CO₂ of liquid-bulk vessels, IMO Fourth GHG Study 2020 method) and the **Brazil Port Data** tables (ANTAQ statistics aggregated with the same filter as the agency's public panel).

With it, Claude can answer questions such as:

- *"How long did ships wait to berth at Itaqui, Paranaguá, Santos and Ponta da Madeira in 2025? Rank them."*
- *"Give me the cargo profile of Itaqui since 2019, split by deep sea and cabotage."*
- *"A 45,000 DWT tanker stayed 67 hours at berth. How much CO₂ would shore power have avoided?"*
- *"Here are 40 calls with DWT and hours at berth. What is the total OPS-avoidable CO₂ by size band?"*

| Tool | What it does |
|---|---|
| `find_installation` | Searches installations by name, port complex or ANTAQ code ("Ponta da Madeira" → `BRMA002`) |
| `port_profile` | Year-by-year cargo (tonnes), navigation mix, berthings and port times for one installation |
| `compare_ports` | Ranks several installations on tonnes, berthings, waiting time, hours at berth or total stay |
| `estimate_berth_co2` | At-berth CO₂ of one tanker call (auxiliary engine, the load shore power replaces) |
| `estimate_calls_co2` | The same for a list of calls, with totals by size band |
| `explain_method` | Formula, parameters and sources behind the numbers |

Design choices that matter when an LLM is the user:

- **Every answer carries its source**, and the server instructions tell Claude to cite it and to flag partial years (2026 rows cover only part of the year).
- **Names resolve to codes safely.** An exact name wins ("Paranaguá" is the public port, not the Cattalini terminal); an ambiguous name returns the candidate codes so Claude can ask or choose, instead of guessing.
- **Errors are written for the model.** "No installation matches 'xyz'. Use find_installation first." lets Claude correct itself in the next step.
- **Caveats travel with the CO₂ numbers.** Auxiliary power and load factor are illustrative defaults by DWT band, and the tool says so.

## Data

The server looks for the port tables in this order:

1. **The folder in `PORT_DATA_DIR`**, if set (for your own copy or a newer extraction).
2. **The open dataset on Zenodo**, after one command:
   ```bash
   port-emissions-mcp download
   ```
   This fetches *Brazil Port Data: consolidated ANTAQ port statistics, 2010-2026* (doi:[10.5281/zenodo.XXXXXXX](https://doi.org/10.5281/zenodo.XXXXXXX), ODbL 1.0) into `~/.cache/port-emissions-mcp`.
3. **A small synthetic dataset** bundled in `src/port_emissions_mcp/example_data/` (three fictitious installations), so the tests run offline. Every answer based on it carries a warning that the numbers are invented.

| File | Grain |
|---|---|
| `cargo_by_installation_2010_2026.csv` | year × installation, tonnes |
| `cargo_by_navigation_2010_2026.csv` | year × installation, tonnes by navigation type |
| `berthings_by_installation_2010_2026.csv` | year × installation, berthings |
| `port_times_by_installation_2010_2026.csv` | year × installation, mean hours waiting, operating, at berth, total stay |
| `installations_2023_2025.csv` | installation names (linked to ANTAQ codes by tonnage in 2024 and 2025, one-to-one matches only) |

## Installing

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/) (or pip).

```bash
git clone https://github.com/darlianecunha/port-emissions-mcp
cd port-emissions-mcp
uv venv && uv pip install -e ".[test]"
uv run pytest                      # 9 tests, offline, synthetic data
uv run port-emissions-mcp download # real data from Zenodo
```

### Claude Code

```bash
claude mcp add --transport stdio --env PORT_DATA_DIR=/path/to/dados-consolidados \
  port-emissions -- /path/to/port-emissions-mcp/.venv/bin/port-emissions-mcp
```

Leave out `--env ...` if you ran `port-emissions-mcp download`. Check with `claude mcp list`.

### Claude Desktop

Add to `claude_desktop_config.json` (Settings → Developer → Edit Config) and restart the app:

```json
{
  "mcpServers": {
    "port-emissions": {
      "command": "/path/to/port-emissions-mcp/.venv/bin/port-emissions-mcp",
      "env": {}
    }
  }
}
```

## Repository map

| Path | Content |
|---|---|
| `src/port_emissions_mcp/server.py` | The six MCP tools and the server instructions |
| `src/port_emissions_mcp/data.py` | Loading, name-to-code linking, search and resolution |
| `src/port_emissions_mcp/download.py` | Fetches the open dataset from the Zenodo API (standard library only) |
| `src/port_emissions_mcp/example_data/` | Synthetic data (invented numbers) |
| `tests/test_tools.py` | pytest suite: tools, name resolution, MCP exposure, and a download from a local mock of the Zenodo API |
| `docs/demo-prompts.md` | Prompts used to test the server with Claude |

## Method notes

- **At-berth CO₂** (via [maritime-co2](https://github.com/darlianecunha/maritimeco2), doi:[10.5281/zenodo.20708090](https://doi.org/10.5281/zenodo.20708090)): `CO₂ = aux_kW × load_factor × hours × SFOC / 10⁶ × Cf`, auxiliary engine only (boilers excluded because they keep running for cargo heating). Cf from the IMO Fourth GHG Study 2020: MDO/MGO 3.206, HFO 3.114 t CO₂/t fuel; SFOC 215 g/kWh. Scope: liquid-bulk (tanker) vessels.
- **Data licence.** The port tables are ODbL 1.0, derived from ANTAQ open data; cite the Zenodo record. The code is MIT.
- **Cargo** follows ANTAQ's definition of port movement (authorised operations that count as movement), so national totals match the agency's panel.
- **Berthings** count distinct records with authorised cargo operations, so they are lower than raw ANTAQ berthing counts.
- **Port times** are annual means per installation.
- **Limitations.** Size-band parameters are illustrative, not vessel-specific. 2026 is partial. 71 of 247 codes have no linked name and are labelled with their port complex.

## Related projects

- [maritimeco2](https://github.com/darlianecunha/maritimeco2): the CO₂ library this server calls
- [decarbport.com](https://www.decarbport.com): interactive calculator using the same method
- [brazilportdata.com](https://brazilportdata.com): public panels built from the same ANTAQ tables
- [MCP_DadosPublicosANTAQ](https://github.com/opedrosoares/MCP_DadosPublicosANTAQ): a broad MCP server over many ANTAQ and trade archives. This project is narrower by design: curated annual series that match ANTAQ's official totals, plus at-berth CO₂ and method caveats in every answer

## How to cite

> Cunha, D. R. (2026). *port-emissions-mcp: an MCP server for at-berth CO₂ and Brazilian port statistics* (Version 0.1.0) [Software]. https://github.com/darlianecunha/port-emissions-mcp

## Author and licence

**Darliane Ribeiro Cunha, PhD**. [ribeirocunha.com](https://ribeirocunha.com) · [ORCID 0000-0003-2548-1237](https://orcid.org/0000-0003-2548-1237)

[MIT](LICENSE).
