"""Tes Paket Keamanan LAN: sandbox path, upload streaming, TTL, rate limit."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vnswap_web as web


@pytest.fixture()
def srv(tmp_path):
    root = tmp_path / "shared"
    root.mkdir()
    (root / "tVisualization.data").write_bytes(bytes([40] * 60))
    (root / "t.opus").write_bytes(b"fake-opus-audio-content-12345")
    (root / "song.mp3").write_bytes(b"x" * 5000)
    outside = tmp_path / "outside.mp3"
    outside.write_bytes(b"rahasia-di-luar-root" * 100)
    server = web.run_server("127.0.0.1", 0, root, [root])
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.2)
    web._rate_hits.clear()
    yield f"http://127.0.0.1:{port}", root, outside
    server.shutdown()
    server.server_close()
    web._rate_hits.clear()


def _req(base, path, data=None, headers=None, method=None):
    req = urllib.request.Request(base + path, data=data,
                                 headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _get(base, path):
    return _req(base, path)


def test_audio_sandbox_luar_root_403(srv):
    base, root, outside = srv
    q = "/api/audio?path=" + urllib.parse.quote(str(outside))
    status, _, body = _get(base, q)
    assert status == 403
    assert "di luar folder" in json.loads(body)["error"]
    q2 = "/api/audio?path=" + urllib.parse.quote(str(root / "t.opus"))
    status, _, body = _get(base, q2)
    assert status == 200
    assert body == b"fake-opus-audio-content-12345"


def test_bars_dan_preview_sandbox(srv):
    base, root, outside = srv
    q = "/api/bars?path=" + urllib.parse.quote(str(outside))
    assert _get(base, q)[0] == 403
    q = "/api/bars?path=" + urllib.parse.quote(
        str(root / "tVisualization.data"))
    status, _, body = _get(base, q)
    assert status == 200
    assert json.loads(body)["length"] == 60
    t = urllib.parse.quote(str(root / "tVisualization.data"))
    s = urllib.parse.quote(str(outside))
    assert _get(base, f"/api/preview?target={t}&source={s}")[0] == 403


def test_jobs_tolak_path_luar_root(srv):
    base, root, outside = srv
    t = str(root / "tVisualization.data")
    payload = json.dumps({
        "target": t, "source": str(outside), "channels": 1,
        "dry_run": True,
    }).encode()
    status, _, body = _req(base, "/api/jobs", data=payload,
                            headers={"Content-Type": "application/json"})
    assert status == 403
    payload = json.dumps({
        "target": t, "source": str(root / "song.mp3"), "channels": 1,
        "dry_run": True,
    }).encode()
    status, _, body = _req(base, "/api/jobs", data=payload,
                            headers={"Content-Type": "application/json"})
    assert status == 200
    assert "id" in json.loads(body)


def test_upload_streaming_isi_utuh(srv):
    base, root, _ = srv
    boundary = "vnswap-test-boundary-12345"
    payload = bytes((i * 7) % 251 for i in range(200 * 1024))  # > 64KB
    assert boundary.encode() not in payload
    body = (f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="file"; filename="lagu.mp3"\r\n'
            f"Content-Type: audio/mpeg\r\n\r\n").encode() + payload + \
        f"\r\n--{boundary}--\r\n".encode()
    status, _, resp = _req(
        base, "/api/upload", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    assert status == 200
    saved = json.loads(resp)
    assert saved["size"] == len(payload)
    assert Path(saved["path"]).read_bytes() == payload


def test_upload_tolak_file_kosong_dan_raksasa(srv):
    base, _, _ = srv
    boundary = "b"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; "
            'name="file"; filename="k.mp3"\r\n\r\n'
            f"\r\n--{boundary}--\r\n").encode()
    status, _, _ = _req(
        base, "/api/upload", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    assert status == 400


def test_unggahan_kedaluarsa_dibersihkan(srv):
    base, _, _ = srv
    up = web.SERVER_CONFIG["upload_dir"]
    stale = up / "tua-test.mp3"
    stale.write_bytes(b"x" * 100)
    old = time.time() - web._UPLOAD_TTL_SEC - 10
    os.utime(stale, (old, old))
    status, _, _ = _get(base, "/api/sources")
    assert status == 200
    assert not stale.exists()


def test_job_purge_batas_dan_ttl():
    store = web.JobStore()
    for _ in range(5):
        store.create("t", "s", 1, True)
    assert len(store._jobs) == 5
    import vnswap_web as w
    old_max = w._MAX_JOBS
    w._MAX_JOBS = 3
    try:
        store.create("t", "s", 1, True)
    finally:
        w._MAX_JOBS = old_max
    assert len(store._jobs) == 3
    old_ttl = w._JOB_TTL_SEC
    w._JOB_TTL_SEC = -1
    try:
        store.purge()
    finally:
        w._JOB_TTL_SEC = old_ttl
    assert len(store._jobs) == 0


def test_rate_limit_post_429(srv, monkeypatch):
    base, _, _ = srv
    monkeypatch.setattr(web, "_RATE_MAX", 2)
    web._rate_hits.clear()
    codes = []
    for _ in range(3):
        status, headers, _ = _req(base, "/api/jobs", data=b"",
                                  headers={"Content-Type": "application/json"})
        codes.append(status)
    assert codes[0] == 400 and codes[1] == 400
    assert codes[2] == 429
    web._rate_hits.clear()
