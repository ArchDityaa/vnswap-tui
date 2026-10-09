"""Tes PWA web: manifest, ikon, service worker, dan rute statis."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def test_manifest_valid_dan_lengkap():
    m = json.loads((HERE / "web" / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["short_name"] and m["start_url"] == "/"
    assert m["display"] == "standalone"
    assert m["theme_color"] and m["background_color"]
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any("maskable" in i.get("purpose", "") for i in m["icons"])
    for icon in m["icons"]:
        assert (HERE / "web" / icon["src"].lstrip("/")).is_file()


def test_html_menautkan_manifest_dan_mendaftarkan_sw():
    html = (HERE / "web" / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in html
    assert "apple-touch-icon" in html
    js = (HERE / "web" / "app.js").read_text(encoding="utf-8")
    assert 'navigator.serviceWorker.register("/sw.js")' in js


def test_sw_tidak_pernah_cache_api():
    sw = (HERE / "web" / "sw.js").read_text(encoding="utf-8")
    assert 'startsWith("/api/")' in sw
    assert "skipWaiting" in sw


def test_rute_pwa_disajikan_server():
    import vnswap_web as web

    server = web.run_server("127.0.0.1", 0, HERE, [HERE])
    base = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.2)
    try:
        for p in ("/manifest.webmanifest", "/sw.js", "/icon-192.png",
                  "/icon-512.png", "/apple-touch-icon.png"):
            with urllib.request.urlopen(base + p) as r:
                assert r.status == 200, p
                assert r.headers.get("Cache-Control") == "no-store", p
        with urllib.request.urlopen(base + "/manifest.webmanifest") as r:
            assert json.loads(r.read())["short_name"]
    finally:
        server.shutdown()
        server.server_close()
