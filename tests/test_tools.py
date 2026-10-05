"""Tests run on the bundled synthetic data unless PORT_DATA_DIR is set."""
import asyncio
import os

import pytest

from port_emissions_mcp import data, server


@pytest.fixture(autouse=True)
def _synthetic(monkeypatch, tmp_path):
    if not os.environ.get("KEEP_REAL"):
        monkeypatch.delenv("PORT_DATA_DIR", raising=False)
        monkeypatch.setattr(data, "CACHE_DIR", tmp_path / "empty-cache")
    data.load.cache_clear()
    yield
    data.load.cache_clear()


def test_berth_co2_matches_library():
    # medium band: 1000 kW x 0.5 x 40 h x 215 g/kWh / 1e6 x 3.206
    out = server.estimate_berth_co2(dwt=45000, berth_hours=40)
    assert out["size_band"] == "medium"
    assert out["co2_tonnes"] == pytest.approx(1000 * 0.5 * 40 * 215 / 1e6 * 3.206, rel=1e-3)


def test_calls_sum():
    out = server.estimate_calls_co2([{"dwt": 10000, "berth_hours": 30}, {"dwt": 90000, "berth_hours": 30}])
    assert out["n_calls"] == 2
    assert out["total_co2_tonnes"] == pytest.approx(sum(r["sum"] for r in out["by_size_band"]), abs=0.02)


def test_find_and_resolve_by_name():
    hits = server.find_installation("terminal privado")["matches"]
    assert hits[0]["codigo"] == "BRXX002"
    assert data.resolve("brxx001") == "BRXX001"


def test_ambiguous_name_raises():
    with pytest.raises(Exception, match="ambiguous"):
        data.resolve("exemplo")


def test_profile_flags_partial_year_and_synthetic():
    out = server.port_profile("BRXX001", 2024, 2026)
    assert [r["ano"] for r in out["rows"]] == [2024, 2025, 2026]
    assert any("partial" in n for n in out["notes"])
    assert "SYNTHETIC" in out["warning"]


def test_compare_ranks_high_to_low():
    out = server.compare_ports(["BRXX001", "BRXX002", "BRYY001"], "tonnes", 2025)
    values = [r["tonnes"] for r in out["rows"]]
    assert values == sorted(values, reverse=True)


def test_tools_registered_over_mcp():
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {"estimate_berth_co2", "estimate_calls_co2", "find_installation",
                     "port_profile", "compare_ports", "explain_method"}


def test_download_from_zenodo_api(monkeypatch, tmp_path):
    """Serve a fake Zenodo record over HTTP and check the server switches to it."""
    import http.server
    import json
    import shutil
    import threading

    from port_emissions_mcp import download

    files_dir = tmp_path / "record"
    shutil.copytree(data.EXAMPLE_DIR, files_dir)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(files_dir), **k)

        def do_GET(self):  # /api/records/123 -> JSON in the Zenodo format
            if self.path == "/api/records/123":
                base = f"http://127.0.0.1:{self.server.server_port}"
                body = json.dumps({"files": [
                    {"key": f.name, "links": {"self": f"{base}/{f.name}"}} for f in files_dir.glob("*.csv")
                ]}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)
            else:
                super().do_GET()

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(download, "ZENODO_API", f"http://127.0.0.1:{srv.server_port}/api")
        cache = tmp_path / "cache"
        got = download.download("123", cache)
        assert len(got) == len(data.FILES)
        monkeypatch.setattr(data, "CACHE_DIR", cache)
        data.load.cache_clear()
        assert data.load().source == "real (Zenodo download)"
        assert "warning" not in server.find_installation("exemplo")
    finally:
        srv.shutdown()


def test_download_needs_record():
    from port_emissions_mcp import download

    with pytest.raises(SystemExit, match="No Zenodo record"):
        download.download("", data.CACHE_DIR)


def test_download_from_zip_record(monkeypatch, tmp_path):
    """GitHub-integration records hold one zip with the tables in a subfolder."""
    import io
    import zipfile

    from port_emissions_mcp import download

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for f in data.EXAMPLE_DIR.glob("*.csv"):
            z.write(f, f"user-repo-abc123/data/{f.name}")
    payload = buf.getvalue()

    monkeypatch.setattr(download, "file_links", lambda rec: {"repo-v1.zip": "http://x/zip"})
    monkeypatch.setattr(download, "_get", lambda url: payload)
    got = download.download("1", tmp_path / "cache")
    assert sorted(got) == sorted(data.FILES.values())
    assert (tmp_path / "cache" / "cargo_by_installation_2010_2026.csv").exists()
