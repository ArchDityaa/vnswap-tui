"""Tes pemeriksaan kesehatan awal (hanya stdlib, tanpa perlu perangkat)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vnswap_core as core
from vnswap import resolve_mode, run_health, split_subcommand
import argparse


def _sidecar(d: Path, name: str = "aVisualization.data") -> None:
    (d / name).write_bytes(bytes([10]) * 20)


def test_check_health_ids_lengkap(tmp_path: Path):
    checks = core.check_health(tmp_path, [tmp_path])
    ids = {c.id for c in checks}
    assert {"ffmpeg", "shared_exists", "shared_read", "shared_write",
            "storage", "targets", "media", "textual", "python"} <= ids
    for c in checks:
        assert c.label and c.detail


def test_check_health_shared_hilang_beri_perintah(tmp_path: Path):
    missing = tmp_path / "hilang"
    checks = {c.id: c for c in core.check_health(missing, [])}
    assert checks["shared_exists"].ok is False
    assert "termux-setup-storage" in (checks["shared_exists"].fix or "")
    assert checks["targets"].ok is False


def test_check_health_ffmpeg_hilang(monkeypatch, tmp_path: Path):
    _sidecar(tmp_path)
    monkeypatch.setattr(core, "find_ffmpeg", lambda: None)
    checks = {c.id: c for c in core.check_health(tmp_path, [tmp_path])}
    assert checks["ffmpeg"].ok is False
    assert "pkg install ffmpeg" in (checks["ffmpeg"].fix or "")


def test_check_health_semua_ok_bila_env_bagus(monkeypatch, tmp_path: Path):
    import sys
    import types
    _sidecar(tmp_path)
    monkeypatch.setattr(core, "find_ffmpeg", lambda: "/usr/bin/ffmpeg")
    monkeypatch.setitem(sys.modules, "textual", types.ModuleType("textual"))
    checks = {c.id: c for c in core.check_health(tmp_path, [tmp_path])}
    assert checks["shared_exists"].ok is True
    assert checks["shared_read"].ok is True
    assert checks["shared_write"].ok is True
    assert checks["targets"].ok is True
    assert checks["media"].ok is True


def test_health_failed_dan_format(tmp_path: Path):
    checks = core.check_health(tmp_path / "hilang", [])
    failed = core.health_failed(checks)
    assert failed
    text = core.format_health_report(checks)
    assert "[XX]" in text
    assert "Perbaiki:" in text


def test_subcommand_health_terdaftar():
    assert split_subcommand(["health"]) == ("health", [])
    ns = argparse.Namespace(web=False, cli=False)
    assert resolve_mode("health", ns) == "health"


def test_run_health_kode_kembali(monkeypatch, tmp_path: Path, capsys):
    import sys
    import types
    _sidecar(tmp_path)
    monkeypatch.setattr(core, "find_ffmpeg", lambda: "/usr/bin/ffmpeg")
    monkeypatch.setitem(sys.modules, "textual", types.ModuleType("textual"))
    assert run_health(tmp_path, [tmp_path]) == 0
    assert "semua pemeriksaan lolos" in capsys.readouterr().out
    assert run_health(tmp_path / "hilang", []) == 1
    assert "pemeriksaan gagal" in capsys.readouterr().out


def test_api_health_memuat_checks():
    import json
    import threading
    import time
    import urllib.request
    import vnswap_web as web

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "tVisualization.data").write_bytes(bytes([10]) * 20)
        server = web.run_server("127.0.0.1", 0, root, [root])
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        time.sleep(0.2)
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/health") as r:
                h = json.loads(r.read())
            assert "checks" in h and isinstance(h["checks"], list)
            ids = {c["id"] for c in h["checks"]}
            assert "ffmpeg" in ids and "shared_exists" in ids
            for c in h["checks"]:
                assert {"id", "label", "ok", "detail", "fix"} <= set(c)
        finally:
            server.shutdown()
            server.server_close()
