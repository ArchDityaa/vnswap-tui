"""Antarmuka web vnswap — server HTTP + JSON API hanya stdlib.

Mencerminkan wizard TUI 1:1 (Target -> Sumber -> Cek -> Proses)
tanpa membutuhkan Textual. Menyajikan file statis ./web/ dan menyediakan:

  GET  /api/health          status ffmpeg, dir shared, jumlah
  GET  /api/targets         pasangan Visualization.data terdeteksi (terbaru dulu)
  GET  /api/sources         file audio/video yang didukung terbaru
  GET  /api/bars?path=...   bar sidecar untuk preview gelombang
  GET  /api/plan?channels=  info resep encode
  POST /api/upload          upload file multipart -> {name, path, size}
  POST /api/jobs            {target, source, channels, dry_run} -> {id}
  GET  /api/jobs/<id>       status / progres / log / hasil job
  POST /api/jobs/<id>/rollback  kembalikan backup .bak

Cara pakai:
  python vnswap_web.py [--host 127.0.0.1] [--port 8000] [--shared DIR]
  python vnswap.py --web [--port 8000] [--host 127.0.0.1]

Tanpa dependensi pihak ketiga. ThreadingHTTPServer + thread latar.
"""

from __future__ import annotations

import argparse
import errno
import html
import json
import mimetypes
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import vnswap_core as core

try:
    from vnswap_ui_nav import fmt_dur, fmt_size, rel_time, media_tag, wave_preview
except ImportError:  # pragma: no cover
    def fmt_dur(s: float) -> str:  # type: ignore
        try:
            v = max(0.0, float(s))
        except (TypeError, ValueError):
            return "--:--"
        m = int(v // 60)
        sec = int(round(v % 60))
        return f"{m}:{sec:02d}"

    def fmt_size(n: int) -> str:  # type: ignore
        try:
            v = float(n)
        except (TypeError, ValueError):
            return "--"
        if v < 1024:
            return f"{int(v)} B"
        if v < 1024 * 1024:
            return f"{v / 1024:.1f} KB"
        return f"{v / (1024 * 1024):.1f} MB"

    def rel_time(mtime: float) -> str:  # type: ignore
        try:
            delta = time.time() - float(mtime)
        except (TypeError, ValueError):
            return "--"
        if delta < 60:
            return "baru saja"
        if delta < 3600:
            return f"{int(delta // 60)} mnt lalu"
        if delta < 86400:
            return f"{int(delta // 3600)} jam lalu"
        return time.strftime("%Y-%m-%d", time.localtime(mtime))

    def media_tag(p) -> str:  # type: ignore
        return Path(str(p)).suffix.lower().lstrip(".").upper() or "--"


HERE = Path(__file__).resolve().parent
WEB_DIR = HERE / "web"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "vnswap-uploads"

STAGE_LABELS = [
    "Encode opus",
    "Visual 20 bars per detik",
    "Backup .bak",
    "Tukar atomik",
]


# ---------------------------------------------------------------------------
# Penyimpanan job
# ---------------------------------------------------------------------------

class JobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}

    def create(self, target: str, source: str, channels: int, dry_run: bool) -> dict:
        jid = uuid.uuid4().hex[:12]
        job = {
            "id": jid,
            "target": target,
            "source": source,
            "channels": channels,
            "dry_run": dry_run,
            "status": "queued",  # queued | running | done | error
            "progress": 0,
            "stages": ["todo", "todo", "todo", "todo"],
            "logs": [],
            "result": None,
            "error": None,
            "created": time.time(),
        }
        with self._lock:
            self._jobs[jid] = job
        return job

    def get(self, jid: str) -> dict | None:
        with self._lock:
            return self._jobs.get(jid)

    def update(self, jid: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(jid)
            if job is not None:
                job.update(fields)

    def log(self, jid: str, level: str, msg: str) -> None:
        with self._lock:
            job = self._jobs.get(jid)
            if job is not None:
                job["logs"].append({"t": time.time(), "level": level, "msg": msg})

    def set_stage(self, jid: str, idx: int, value: str) -> None:
        with self._lock:
            job = self._jobs.get(jid)
            if job is not None and 0 <= idx < len(job["stages"]):
                job["stages"][idx] = value


STORE = JobStore()

SERVER_CONFIG: dict = {
    "shared_dir": core.DEFAULT_SHARED_DIR,
    "media_dirs": [],
    "upload_dir": UPLOAD_DIR,
    "token": None,
    "shared_auto": False,
}


def is_loopback(host: str) -> bool:
    """True untuk binding localhost yang tidak pernah keluar dari perangkat."""
    h = host.strip().lower()
    return h in ("localhost", "::1") or h.startswith("127.")


def resolve_token(host: str, token: str | None,
                  no_auth: bool = False) -> tuple[str | None, bool]:
    """Menentukan token API. Mengembalikan (token, auto_generated).

    Host non-loopback mendapat token otomatis kecuali sudah diberi
    atau auth dimatikan eksplisit dengan --no-auth.
    """
    if no_auth:
        return None, False
    if token:
        return token, False
    if is_loopback(host):
        return None, False
    return secrets.token_urlsafe(32), True


def lan_ips() -> list[str]:
    """IP LAN perangkat untuk URL yang bisa dibuka dari browser HP.

    Trik UDP-connect hanya membaca tabel routing — tidak ada paket yang
    dikirim, jadi aman offline (saat gagal, kembalikan list kosong).
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return []
    if not ip or ip.startswith("127."):
        return []
    return [ip]


def access_urls(host: str, port: int, token: str | None) -> list[str]:
    """URL yang benar-benar bisa dibuka di browser.

    Jangan pernah cetak host bind mentah: `0.0.0.0` bukan alamat tujuan
    yang valid dan browser menolaknya. Selalu sertakan loopback, tambah
    tiap IP LAN bila binding non-loopback, dan sematkan token.
    """
    suffix = f"?token={token}" if token else ""
    urls = [f"http://127.0.0.1:{port}/{suffix}"]
    if not is_loopback(host):
        seen = {"127.0.0.1"}
        candidates = []
        h = host.strip()
        if h not in ("0.0.0.0", "::"):
            candidates.append(h)
        candidates.extend(lan_ips())
        for cand in candidates:
            if cand and cand not in seen:
                seen.add(cand)
                urls.append(f"http://{cand}:{port}/{suffix}")
    return urls


def default_media_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / "storage" / "downloads",
        home / "storage" / "movies",
        home / "storage" / "music",
        home / "storage" / "dcim",
        Path("/sdcard/Download"),
        Path("/sdcard/Movies"),
        Path("/sdcard/Music"),
    ]


# ---------------------------------------------------------------------------
# Pekerja job — mencerminkan RunScreen._run / run_pipeline langkah demi langkah
# ---------------------------------------------------------------------------

def run_job(job_id: str) -> None:
    job = STORE.get(job_id)
    if job is None:
        return
    STORE.update(job_id, status="running", progress=1)
    STORE.set_stage(job_id, 0, "active")
    STORE.log(job_id, "info", "pekerjaan dimulai.")

    target_path = Path(job["target"])
    source_path = Path(job["source"])
    channels = int(job.get("channels", 1) or 1)
    dry_run = bool(job.get("dry_run", False))

    def step(pct: int, msg: str, level: str = "info") -> None:
        STORE.update(job_id, progress=max(0, min(100, pct)))
        STORE.log(job_id, level, msg)

    # Validasi target
    try:
        raw_target = target_path.read_bytes()
        length, duration_tpl = core.parse_target_visualization_data(
            raw_target, target_path.name
        )
    except Exception as exc:
        STORE.set_stage(job_id, 0, "fail")
        STORE.update(job_id, status="error", error=f"target tidak valid: {exc}")
        step(0, f"target tidak valid: {exc}", "error")
        return

    base = core.template_base_name(target_path.name, "")
    opus_path = target_path.with_name(f"{base}.opus") if base else None
    if opus_path is not None and not opus_path.is_file():
        opus_path = None
    target = core.VoiceNoteTarget(
        data_path=target_path,
        opus_path=opus_path,
        length=length,
        approx_duration_sec=duration_tpl,
        mtime=target_path.stat().st_mtime if target_path.exists() else 0.0,
    )

    if not source_path.is_file():
        STORE.update(job_id, status="error", error="file sumber tidak ada.")
        STORE.set_stage(job_id, 0, "fail")
        step(0, "file sumber tidak ada.", "error")
        return

    ffmpeg = core.find_ffmpeg()
    if not ffmpeg:
        STORE.set_stage(job_id, 0, "fail")
        STORE.update(job_id, status="error",
                      error="ffmpeg tidak ditemukan - pkg install ffmpeg dulu.")
        step(0, "ffmpeg tidak ditemukan - pkg install ffmpeg dulu.", "error")
        return

    plan = core.build_encode_plan(channels)
    step(2, f"resep: opus {plan.bitrate} {plan.application} {plan.label}.", "info")

    last_result: core.SwapResult | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="vnswap-") as tmpdir:
            out = Path(tmpdir) / "converted.ogg"
            converted: bytes | None = None
            for idx, argv in enumerate(plan.args_list):
                cmd = [
                    str(source_path) if a == "{in}"
                    else str(out) if a == "{out}" else a
                    for a in [ffmpeg, "-hide_banner", "-y", *argv]
                ]
                tag = "utama" if idx == 0 else f"fallback {idx}"
                step(5 + idx * 10, f"encode {tag} berjalan...", "info")
                proc = subprocess.run(cmd, capture_output=True, timeout=600)
                if proc.returncode == 0 and out.exists():
                    converted = out.read_bytes()
                    STORE.set_stage(job_id, 0, "done")
                    step(40, f"encode {tag} ok ({len(converted)} bytes).", "ok")
                    break
                step(5 + idx * 10, "encode gagal, coba berikutnya...", "warn")
            if not converted:
                STORE.set_stage(job_id, 0, "fail")
                STORE.update(job_id, status="error",
                              error="Semua percobaan encode gagal.")
                step(0, "semua percobaan encode gagal.", "error")
                return
            vendor = core.read_opus_vendor(converted)
            step(45, f'vendor tag: "{vendor or "tak terbaca"}".', "info")
            STORE.set_stage(job_id, 1, "active")
            step(55, "decode dan hitung visualisasi 20 bars per detik...", "info")
            samples, duration = core.decode_pcm_mono(ffmpeg, source_path)
            bars = core.compute_vis_from_samples(samples, 48000, duration or 1.0)
            sidecar = core.clamp_sidecar(bars, target.length)
            STORE.set_stage(job_id, 1, "done")
            step(70, f"sidecar {len(sidecar)} bytes (target {target.length}).", "ok")
            STORE.set_stage(job_id, 2, "active")
            STORE.set_stage(job_id, 3, "active")
            last_result = core.atomic_swap(
                converted, sidecar, target, dry_run=dry_run)
            STORE.set_stage(job_id, 2, "done")
            STORE.set_stage(job_id, 3, "done")
            if dry_run:
                step(100, "PREVIEW selesai - tidak ada file diubah.", "info")
                STORE.update(job_id, status="done", progress=100, result={
                    "mode": "preview",
                    "opus_path": str(last_result.opus_path),
                    "data_path": str(last_result.data_path),
                    "backup_opus": None,
                    "backup_data": None,
                    "vendor": last_result.vendor,
                    "opus_bytes": len(converted),
                    "sidecar_bytes": len(sidecar),
                })
            else:
                step(100, f"TERTUKAR: {last_result.opus_path.name} + "
                          f"{last_result.data_path.name} (backup .bak tersimpan).",
                     "ok")
                STORE.update(job_id, status="done", progress=100, result={
                    "mode": "write",
                    "opus_path": str(last_result.opus_path),
                    "data_path": str(last_result.data_path),
                    "backup_opus": (str(last_result.backup_opus)
                                    if last_result.backup_opus else None),
                    "backup_data": (str(last_result.backup_data)
                                    if last_result.backup_data else None),
                    "vendor": last_result.vendor,
                    "opus_bytes": len(converted),
                    "sidecar_bytes": len(sidecar),
                })
    except Exception as exc:  # noqa: BLE001
        STORE.set_stage(job_id, 3, "fail")
        if last_result is not None:
            try:
                core.restore_backup(last_result)
                step(0, "backup dikembalikan (rollback).", "warn")
            except Exception:
                pass
        STORE.update(job_id, status="error", error=f"gagal: {exc}")
        step(0, f"gagal: {exc}", "error")


# ---------------------------------------------------------------------------
# Lapisan HTTP
# ---------------------------------------------------------------------------

def _send_json(handler: BaseHTTPRequestHandler, obj, status: int = 200) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _targets_payload(shared: Path) -> list[dict]:
    out = []
    for t in core.detect_targets(shared)[:50]:
        out.append({
            "name": t.data_path.name,
            "short_name": t.short_name,
            "base_name": t.base_name,
            "path": str(t.data_path),
            "length": t.length,
            "duration": t.approx_duration_sec,
            "duration_str": fmt_dur(t.approx_duration_sec),
            "mtime": t.mtime,
            "rel": rel_time(t.mtime),
            "size_str": fmt_size(t.length),
            "has_opus": t.opus_path is not None,
            "opus_path": str(t.opus_path) if t.opus_path else None,
        })
    return out


def _sources_payload(dirs: list[Path]) -> list[dict]:
    out = []
    for p in core.discover_sources(dirs, limit=50):
        try:
            sz = p.stat().st_size
        except OSError:
            sz = 0
        out.append({
            "name": p.name,
            "path": str(p),
            "size": sz,
            "size_str": fmt_size(sz),
            "ext": p.suffix.lower().lstrip("."),
            "tag": media_tag(p),
            "supported": core.is_supported_source(p),
        })
    # file upload dulu (terbaru)
    up = SERVER_CONFIG.get("upload_dir", UPLOAD_DIR)
    try:
        if isinstance(up, Path) and up.is_dir():
            for p in sorted(up.iterdir(), key=lambda e: e.stat().st_mtime,
                            reverse=True)[:20]:
                if p.is_file() and core.is_supported_source(p):
                    try:
                        sz = p.stat().st_size
                    except OSError:
                        continue
                    out.insert(0, {
                        "name": p.name,
                        "path": str(p),
                        "size": sz,
                        "size_str": fmt_size(sz),
                        "ext": p.suffix.lower().lstrip("."),
                        "tag": media_tag(p),
                        "supported": True,
                        "uploaded": True,
                    })
    except OSError:
        pass
    return out


def _save_multipart(handler: BaseHTTPRequestHandler) -> dict | None:
    ctype = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in ctype or "boundary=" not in ctype:
        return None
    boundary = ctype.split("boundary=")[-1].strip().strip('"').encode()
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        return None
    if length <= 0 or length > 600 * 1024 * 1024:
        return None
    raw = handler.rfile.read(length)
    # parser file tunggal minimal: cari filename="..." lalu \r\n\r\n ... \r\n--boundary
    marker = b'filename="'
    idx = raw.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker)
    end = raw.find(b'"', start)
    fname = raw[start:end].decode("utf-8", "replace")
    fname = Path(fname).name or f"upload-{uuid.uuid4().hex[:8]}"
    # pertahankan ekstensi, bersihkan
    safe = "".join(c for c in fname if c.isalnum() or c in "._- ")[:120].strip()
    if not safe:
        safe = f"upload-{uuid.uuid4().hex[:8]}"
    head_end = raw.find(b"\r\n\r\n", end)
    if head_end < 0:
        return None
    content_start = head_end + 4
    tail = raw.rfind(b"\r\n--" + boundary)
    if tail < 0:
        tail = raw.rfind(b"--" + boundary + b"--")
    if tail < 0 or tail <= content_start:
        return None
    payload = raw[content_start:tail]
    if payload.endswith(b"\r\n"):
        payload = payload[:-2]
    upload_dir: Path = SERVER_CONFIG.get("upload_dir", UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{int(time.time())}-{safe}"
    dest.write_bytes(payload)
    return {"name": dest.name, "path": str(dest), "size": len(payload),
            "size_str": fmt_size(len(payload))}


_AUDIO_MIME = {
    "opus": "audio/ogg", "ogg": "audio/ogg", "oga": "audio/ogg",
    "mp3": "audio/mpeg", "m4a": "audio/mp4", "aac": "audio/aac",
    "wav": "audio/wav", "flac": "audio/flac", "weba": "audio/webm",
    "webm": "video/webm", "mp4": "video/mp4", "m4v": "video/mp4",
    "mov": "video/quicktime", "mkv": "video/x-matroska", "3gp": "video/3gpp",
}

_MAX_AUDIO_BYTES = 300 * 1024 * 1024


def _serve_media(handler: BaseHTTPRequestHandler, path: Path) -> None:
    """Menyajikan file audio/video lokal dengan dukungan HTTP Range untuk pemutar."""
    try:
        total = path.stat().st_size
    except OSError:
        _send_json(handler, {"error": "file tidak ada"}, 404)
        return
    if total > _MAX_AUDIO_BYTES:
        _send_json(handler, {"error": "file terlalu besar untuk preview"}, 413)
        return
    ctype = _AUDIO_MIME.get(path.suffix.lower().lstrip("."),
                            "application/octet-stream")
    start, end, status = 0, total - 1, 200
    range_h = handler.headers.get("Range", "")
    if range_h.startswith("bytes=") and total > 0:
        spec = range_h[6:].split("-", 1)
        try:
            if spec[0]:
                start = int(spec[0])
                end = int(spec[1]) if len(spec) > 1 and spec[1] else total - 1
            elif len(spec) > 1 and spec[1]:
                start = max(0, total - int(spec[1]))
            end = min(end, total - 1)
            if start > end or start >= total:
                raise ValueError
            status = 206
        except ValueError:
            handler.send_response(416)
            handler.send_header("Content-Range", f"bytes */{total}")
            handler.end_headers()
            return
    try:
        with open(path, "rb") as fh:
            fh.seek(start)
            body = fh.read(end - start + 1)
    except OSError as exc:
        _send_json(handler, {"error": str(exc)}, 400)
        return
    handler.send_response(status)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Accept-Ranges", "bytes")
    if status == 206:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{total}")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    server_version = "vnswap-web/1.0"

    def log_message(self, fmt, *args):  # lebih sepi
        pass

    def _api_authorized(self) -> bool:
        """Cek token untuk /api/* — via query ?token= atau header Bearer."""
        token = SERVER_CONFIG.get("token")
        if not token:
            return True
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if qs.get("token", [None])[0] == token:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {token}"

    def _require_api_auth(self) -> bool:
        """Kirim 401 dan kembalikan False bila token API hilang/salah."""
        if self._api_authorized():
            return True
        _send_json(self, {
            "error": "butuh token — buka URL lengkap dari terminal (?token=...).",
        }, 401)
        return False

    # -- pembantu ------------------------------------------------------
    def _serve_static(self, rel: str) -> bool:
        target = (WEB_DIR / rel).resolve() if rel else WEB_DIR / "index.html"
        try:
            if WEB_DIR.resolve() not in target.parents and target != WEB_DIR.resolve():
                # hanya izinkan index persis
                pass
            if target.is_dir():
                target = target / "index.html"
            if WEB_DIR.resolve() not in target.resolve().parents:
                return False
            if not target.is_file():
                return False
        except OSError:
            return False
        ctype, _ = mimetypes.guess_type(str(target))
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
        return True

    # -- GET ----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/api/") and not self._require_api_auth():
            return
        if path == "/" or path == "/index.html":
            if not self._serve_static("index.html"):
                self.send_error(500, "web/index.html missing")
            return
        if path.startswith("/static/"):
            if not self._serve_static(path[len("/static/"):]):
                self.send_error(404)
            return
        if path in ("/styles.css", "/app.js"):
            if not self._serve_static(path.lstrip("/")):
                self.send_error(404)
            return
        if path == "/api/health":
            ffmpeg = core.find_ffmpeg()
            shared: Path = SERVER_CONFIG["shared_dir"]
            try:
                n_targets = len(core.detect_targets(shared))
                n_sources = len(core.discover_sources(
                    SERVER_CONFIG.get("media_dirs", [])))
            except OSError as exc:
                return _send_json(self, {
                    "error": f"gagal memindai: {exc}",
                    "shared_dir": str(shared),
                    "shared_exists": shared.is_dir(),
                }, 500)
            try:
                checks = core.check_health(
                    shared, SERVER_CONFIG.get("media_dirs", []))
                checks_payload = [{
                    "id": c.id, "label": c.label, "ok": c.ok,
                    "detail": c.detail, "fix": c.fix,
                } for c in checks]
            except Exception:
                checks_payload = []
            return _send_json(self, {
                "version": core.VERSION,
                "auth": bool(SERVER_CONFIG.get("token")),
                "shared_auto": bool(SERVER_CONFIG.get("shared_auto")),
                "ffmpeg": ffmpeg,
                "ffmpeg_ok": bool(ffmpeg),
                "shared_dir": str(shared),
                "shared_exists": shared.is_dir(),
                "targets": n_targets,
                "sources": n_sources,
                "checks": checks_payload,
                "failed": sum(1 for c in checks_payload if not c["ok"]),
            })
        if path == "/api/targets":
            shared: Path = SERVER_CONFIG["shared_dir"]
            custom = qs.get("shared", [None])[0]
            if custom:
                shared = Path(custom)
            try:
                payload = _targets_payload(shared)
            except OSError as exc:
                return _send_json(self, {
                    "error": f"gagal membaca folder: {exc}",
                    "shared_dir": str(shared),
                }, 500)
            return _send_json(self, {"targets": payload,
                                     "shared_dir": str(shared)})
        if path == "/api/sources":
            return _send_json(self, {
                "sources": _sources_payload(SERVER_CONFIG.get("media_dirs", []))})
        if path == "/api/bars":
            req = qs.get("path", [None])[0]
            if not req:
                return _send_json(self, {"error": "path wajib diisi"}, 400)
            p = Path(req)
            if not p.is_file():
                return _send_json(self, {"error": "file tidak ada"}, 404)
            try:
                raw = p.read_bytes()
            except OSError as exc:
                return _send_json(self, {"error": str(exc)}, 400)
            try:
                length, _ = core.parse_target_visualization_data(raw, p.name)
            except ValueError as exc:
                return _send_json(self, {"error": str(exc)}, 400)
            return _send_json(self, {"length": length, "bars": list(raw)})
        if path == "/api/preview":
            treq = qs.get("target", [None])[0]
            sreq = qs.get("source", [None])[0]
            if not treq or not sreq:
                return _send_json(self, {
                    "error": "target dan source wajib diisi"}, 400)
            tpath, spath = Path(treq), Path(sreq)
            if not tpath.is_file() or not spath.is_file():
                return _send_json(self, {"error": "file tidak ada"}, 404)
            try:
                raw = tpath.read_bytes()
                length, _ = core.parse_target_visualization_data(
                    raw, tpath.name)
            except (OSError, ValueError) as exc:
                return _send_json(self, {
                    "error": f"target tidak valid: {exc}"}, 400)
            ffmpeg = core.find_ffmpeg()
            if not ffmpeg:
                return _send_json(self, {
                    "error": "ffmpeg tidak ditemukan"}, 503)
            try:
                samples, duration = core.decode_pcm_mono(ffmpeg, spath)
            except Exception as exc:
                return _send_json(self, {
                    "error": f"sumber tidak bisa dibaca: {exc}"}, 400)
            bars = core.compute_vis_from_samples(samples, 48000,
                                                 duration or 1.0)
            sized = (bars if len(bars) == length
                     else core.resample_bars(bars, length))
            return _send_json(self, {
                "target_length": length,
                "target_bars": list(raw),
                "source_duration": duration,
                "source_duration_str": fmt_dur(duration),
                "source_bars_raw": len(bars),
                "source_bars": [max(0, min(100, round(v))) for v in sized],
            })
        if path == "/api/audio":
            req = qs.get("path", [None])[0]
            if not req:
                return _send_json(self, {"error": "path wajib diisi"}, 400)
            p = Path(req)
            if not p.is_file():
                return _send_json(self, {"error": "file tidak ada"}, 404)
            return _serve_media(self, p)
        if path == "/api/shared-candidates":
            try:
                ranked = core.rank_shared_candidates()
            except OSError as exc:
                return _send_json(self, {
                    "error": f"gagal memindai kandidat: {exc}",
                }, 500)
            return _send_json(self, {
                "selected": str(SERVER_CONFIG.get("shared_dir", "")),
                "candidates": [{"path": str(p), "targets": n}
                               for p, n in ranked],
            })
        if path == "/api/diagnostics":
            shared = SERVER_CONFIG["shared_dir"]
            try:
                ranked = core.rank_shared_candidates()
                cands = [{"path": str(p), "targets": n} for p, n in ranked]
                scan_error = None
            except OSError as exc:
                cands = []
                scan_error = str(exc)
            return _send_json(self, {
                "version": core.VERSION,
                "os": os.name,
                "cwd": str(Path.cwd()),
                "env_shared": os.environ.get("VNSWAP_SHARED", ""),
                "shared_dir": str(shared),
                "shared_exists": shared.is_dir(),
                "shared_auto": bool(SERVER_CONFIG.get("shared_auto")),
                "candidates": cands,
                "scan_error": scan_error,
                "ffmpeg": core.find_ffmpeg(),
                "auth": bool(SERVER_CONFIG.get("token")),
                "media_dirs": [str(d) for d in
                               SERVER_CONFIG.get("media_dirs", [])],
            })
        if path == "/api/plan":
            try:
                ch = int(qs.get("channels", ["1"])[0])
            except ValueError:
                ch = 1
            plan = core.build_encode_plan(2 if ch == 2 else 1)
            return _send_json(self, {
                "channels": plan.channels, "bitrate": plan.bitrate,
                "application": plan.application, "label": plan.label,
                "steps": len(plan.args_list)})
        if path.startswith("/api/jobs/"):
            jid = path[len("/api/jobs/"):].strip("/")
            job = STORE.get(jid)
            if job is None:
                return _send_json(self, {"error": "job tidak ada"}, 404)
            return _send_json(self, job)
        if path == "/api/jobs":
            return _send_json(self, {"error": "gunakan POST /api/jobs"}, 405)
        self.send_error(404)

    # -- POST ---------------------------------------------------------
    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/") and not self._require_api_auth():
            return
        if path == "/api/upload":
            saved = _save_multipart(self)
            if not saved:
                return _send_json(self, {
                    "error": "upload gagal - kirim multipart file."}, 400)
            if not core.is_supported_source(Path(saved["path"])):
                saved["warning"] = ("ekstensi tidak dikenal, "
                                    "encode tetap dicoba.")
            return _send_json(self, saved)

        if path == "/api/jobs":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 64 * 1024:
                return _send_json(self, {"error": "body kosong"}, 400)
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return _send_json(self, {"error": "JSON tidak valid"}, 400)
            target = str(body.get("target", "")).strip()
            source = str(body.get("source", "")).strip()
            try:
                channels = int(body.get("channels", 1))
            except (TypeError, ValueError):
                channels = 1
            channels = 2 if channels == 2 else 1
            dry_run = bool(body.get("dry_run", False))
            if not target or not source:
                return _send_json(self, {
                    "error": "target dan source wajib diisi"}, 400)
            if not Path(target).is_file():
                return _send_json(self, {
                    "error": "file target tidak ada"}, 400)
            if not Path(source).is_file():
                return _send_json(self, {
                    "error": "file sumber tidak ada"}, 400)
            job = STORE.create(target, source, channels, dry_run)
            t = threading.Thread(target=run_job, args=(job["id"],),
                                 daemon=True)
            t.start()
            return _send_json(self, {"id": job["id"]})

        if path.startswith("/api/jobs/") and path.endswith("/rollback"):
            jid = path[len("/api/jobs/"):-len("/rollback")].strip("/")
            job = STORE.get(jid)
            if job is None:
                return _send_json(self, {"error": "job tidak ada"}, 404)
            res = job.get("result") or {}
            b_opus = res.get("backup_opus")
            b_data = res.get("backup_data")
            if not b_opus and not b_data:
                return _send_json(self, {
                    "error": "tidak ada backup untuk job ini"}, 400)
            restored = []
            for dest_key, bak in (("opus_path", b_opus),
                                  ("data_path", b_data)):
                dest = res.get(dest_key)
                if dest and bak and Path(bak).exists():
                    try:
                        shutil.copy2(bak, dest)
                        restored.append(dest)
                    except OSError as exc:
                        return _send_json(self, {"error": str(exc)}, 500)
            STORE.log(jid, "warn", "rollback selesai - file asli dikembalikan.")
            return _send_json(self, {"ok": True, "restored": restored})

        self.send_error(404)


def run_server(host: str = "127.0.0.1", port: int = 8000,
               shared_dir: Path | None = None,
               media_dirs: list[Path] | None = None,
               token: str | None = None) -> ThreadingHTTPServer:
    auto = shared_dir is None
    resolved = core.auto_shared_dir(shared_dir)
    SERVER_CONFIG["shared_dir"] = resolved
    SERVER_CONFIG["shared_auto"] = auto
    SERVER_CONFIG["media_dirs"] = (media_dirs if media_dirs is not None
                                   else default_media_dirs())
    SERVER_CONFIG["upload_dir"] = UPLOAD_DIR
    SERVER_CONFIG["token"] = token
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        srv = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        # Windows melaporkan konflik sebagai errno=EACCES(13)/winerror=10013,
        # Unix sebagai EADDRINUSE — tangkap semuanya lewat kedua atribut.
        codes = {exc.errno, getattr(exc, "winerror", None)}
        if codes & {errno.EADDRINUSE, errno.EACCES, 10013, 10048}:
            raise OSError(
                f"port {port} tidak bisa dipakai (kemungkinan sudah dipakai "
                f"proses lain) — hentikan server lama atau ulangi dengan "
                f"--port lain (mis. --port {port + 1})."
            ) from exc
        raise
    return srv


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vnswap-web")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--shared", default=None,
                    help="folder .Shared (bawaan: deteksi otomatis)")
    ap.add_argument("--token", default=None,
                    help="token auth API (bawaan: otomatis saat host non-lokal)")
    ap.add_argument("--no-auth", action="store_true",
                    help="nonaktifkan token auth (hanya untuk jaringan tepercaya)")
    ap.add_argument("--version", action="version",
                    version=f"%(prog)s {core.VERSION}")
    args = ap.parse_args(argv)
    token, generated = resolve_token(args.host, args.token, args.no_auth)
    try:
        srv = run_server(args.host, args.port,
                         Path(args.shared) if args.shared else None,
                         default_media_dirs(), token=token)
    except OSError as exc:
        print(f"[XX] {exc}")
        return 1
    port = srv.server_address[1]
    resolved = SERVER_CONFIG["shared_dir"]
    auto_note = " (deteksi otomatis)" if SERVER_CONFIG["shared_auto"] else ""
    print(f"vnswap web v{core.VERSION}: buka salah satu URL ini di browser HP:")
    for u in access_urls(args.host, port, token):
        print(f"  {u}")
    print(f"  http://127.0.0.1:{port}/api/diagnostics"
          "  (halaman diagnosis bila daftar target kosong)")
    if token:
        print("token sudah tersemat di URL di atas.")
        if generated:
            print("[!!] token dibuat otomatis karena host non-lokal.")
    elif not is_loopback(args.host):
        print("[!!] tanpa token di jaringan lokal — hanya untuk jaringan tepercaya.")
    print(f"shared: {resolved}{auto_note}")
    print("dikembangkan oleh hakiraadityaa (Ctrl+C untuk berhenti)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
