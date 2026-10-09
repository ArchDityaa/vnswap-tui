"""Live-server tests for vnswap_web endpoints (no browser needed).

Preview tests need ffmpeg and are skipped without it; audio/auth/health
tests only need the stdlib.
"""

from __future__ import annotations

import json
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vnswap_core as core
import vnswap_web as web

FFMPEG = core.find_ffmpeg()


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    root = tmp_path_factory.mktemp("web")
    (root / "tVisualization.data").write_bytes(bytes([40] * 60))
    (root / "t.opus").write_bytes(b"fake-opus-audio-content-12345")
    (root / "song.mp3").write_bytes(b"x" * 5000)
    server = web.run_server("127.0.0.1", 0, root, [root])
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}", root
    server.shutdown()
    server.server_close()


def _get(base: str, path: str, headers: dict | None = None):
    req = urllib.request.Request(base + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_health_reports_version_and_auth_flag(srv):
    base, _ = srv
    status, _, body = _get(base, "/api/health")
    assert status == 200
    h = json.loads(body)
    assert h["version"] == core.VERSION
    assert h["auth"] is False


def test_audio_full_and_range_and_404(srv):
    base, root = srv
    q = "/api/audio?path=" + urllib.parse.quote(str(root / "t.opus"))
    status, headers, body = _get(base, q)
    assert status == 200
    assert body == b"fake-opus-audio-content-12345"
    assert headers.get("Content-Type") == "audio/ogg"
    assert headers.get("Accept-Ranges") == "bytes"

    status, headers, body = _get(base, q, {"Range": "bytes=0-3"})
    assert status == 206
    assert body == b"fake"
    assert headers.get("Content-Range") == "bytes 0-3/29"

    status, _, _ = _get(base, "/api/audio?path=" +
                        urllib.parse.quote(str(root / "missing.opus")))
    assert status == 404
    status, _, _ = _get(base, "/api/audio")
    assert status == 400


def test_preview_validation_errors(srv):
    base, root = srv
    t = urllib.parse.quote(str(root / "tVisualization.data"))
    s = urllib.parse.quote(str(root / "song.mp3"))
    status, _, _ = _get(base, "/api/preview")
    assert status == 400
    status, _, _ = _get(base, f"/api/preview?target={t}&source={s}-nope")
    assert status == 404


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")
def test_preview_computes_resampled_bars(srv):
    base, root = srv
    # real 1s tone as the source
    tone = root / "tone.wav"
    import subprocess
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                        str(tone)], capture_output=True)
    assert r.returncode == 0
    t = urllib.parse.quote(str(root / "tVisualization.data"))
    s = urllib.parse.quote(str(tone))
    status, _, body = _get(base, f"/api/preview?target={t}&source={s}")
    assert status == 200
    pv = json.loads(body)
    assert pv["target_length"] == 60
    assert len(pv["target_bars"]) == 60
    assert len(pv["source_bars"]) == 60  # resampled to target length
    assert all(0 <= b <= 100 for b in pv["source_bars"])
    assert max(pv["source_bars"]) == 100


def test_token_gates_api_but_not_static(tmp_path):
    (tmp_path / "tVisualization.data").write_bytes(bytes([10] * 20))
    server = web.run_server("127.0.0.1", 0, tmp_path, [tmp_path],
                            token="TOK123")
    base = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.2)
    try:
        status, _, _ = _get(base, "/api/health")
        assert status == 401
        status, _, _ = _get(base, "/api/audio?path=x")
        assert status == 401
        status, _, _ = _get(base, "/")
        assert status == 200
        status, _, body = _get(base, "/api/health?token=TOK123")
        assert status == 200
        assert json.loads(body)["auth"] is True
    finally:
        server.shutdown()
        server.server_close()
        web.SERVER_CONFIG["token"] = None
