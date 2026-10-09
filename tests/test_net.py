"""Tes URL akses + error bind ramah (hanya stdlib, tanpa browser)."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import vnswap_web as web


def test_lan_ips_returns_list_of_ipv4_or_empty():
    ips = web.lan_ips()
    assert isinstance(ips, list)
    for ip in ips:
        socket.inet_aton(ip)
        assert not ip.startswith("127.")


def test_access_urls_loopback_has_no_token_leak_and_no_wildcard():
    urls = web.access_urls("127.0.0.1", 8000, None)
    assert urls == ["http://127.0.0.1:8000/"]


def test_access_urls_never_prints_wildcard_host():
    urls = web.access_urls("0.0.0.0", 8000, "RAHASIA")
    assert urls, "mode LAN harus mencetak minimal URL loopback"
    assert all("0.0.0.0" not in u for u in urls)
    assert urls[0] == "http://127.0.0.1:8000/?token=RAHASIA"
    assert all("token=RAHASIA" in u for u in urls)


def test_access_urls_explicit_lan_host_included_after_loopback():
    urls = web.access_urls("192.168.1.50", 8000, None)
    assert urls[0] == "http://127.0.0.1:8000/"
    assert "http://192.168.1.50:8000/" in urls
    assert all("0.0.0.0" not in u for u in urls)


def test_run_server_port_conflict_friendly(tmp_path: Path):
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    busy = blocker.getsockname()[1]
    try:
        with pytest.raises(OSError, match="sudah dipakai"):
            web.run_server("127.0.0.1", busy, tmp_path, [tmp_path])
    finally:
        blocker.close()


def test_main_port_conflict_returns_1(capsys, tmp_path: Path):
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    busy = blocker.getsockname()[1]
    try:
        rc = web.main(["--host", "127.0.0.1", "--port", str(busy),
                       "--shared", str(tmp_path)])
    finally:
        blocker.close()
    assert rc == 1
    assert "sudah dipakai" in capsys.readouterr().out
