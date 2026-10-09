"""Tes untuk vnswap_core — hanya stdlib, tanpa perlu ffmpeg/Textual.

Path yang bergantung ffmpeg (decode/probe) dilewati bila tidak ada binary yang ditemukan.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vnswap_core as core


# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------

def _write_visualization(path: Path, bars: list[int]) -> Path:
    path.write_bytes(bytes(bars))
    return path


# ---------------------------------------------------------------------------
# versi
# ---------------------------------------------------------------------------

def test_version_present_and_semver_like():
    assert isinstance(core.VERSION, str)
    parts = core.VERSION.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)


# ---------------------------------------------------------------------------
# shorten_middle / template_base_name
# ---------------------------------------------------------------------------

def test_shorten_middle_short_unchanged():
    assert core.shorten_middle("abc.data", 28) == "abc.data"


def test_shorten_middle_truncates_middle():
    name = "a" * 20 + "Visualization.data"  # > 28 karakter
    out = core.shorten_middle(name, 28)
    assert len(out) == 28
    assert out.startswith("a")
    assert out.endswith("a")
    assert "…" in out


def test_shorten_middle_narrow_width_returns_as_is():
    assert core.shorten_middle("longname", 4) == "longname"


def test_template_base_name_visualization():
    assert core.template_base_name("abc123Visualization.data", "x") == "abc123"
    assert core.template_base_name("ABCVISUALIZATION.DATA", "x") == "ABC"


def test_template_base_name_fallback_strips_extension():
    assert core.template_base_name("song.mp3", "x") == "song"
    assert core.template_base_name("  ", "fb") == "fb"


# ---------------------------------------------------------------------------
# parse_target_visualization_data
# ---------------------------------------------------------------------------

def test_parse_valid_sidecar():
    length, dur = core.parse_target_visualization_data(bytes([0, 50, 100] * 10), "a")
    assert length == 30
    assert dur == pytest.approx(30 / core.VIS_BARS_PER_SECOND)


def test_parse_empty_rejected():
    with pytest.raises(ValueError):
        core.parse_target_visualization_data(b"", "a")


def test_parse_oversize_rejected():
    with pytest.raises(ValueError):
        core.parse_target_visualization_data(bytes(core.MAX_TEMPLATE_BYTES + 1), "a")


def test_parse_byte_over_100_rejected():
    with pytest.raises(ValueError):
        core.parse_target_visualization_data(bytes([0, 101]), "a")


# ---------------------------------------------------------------------------
# detect_targets
# ---------------------------------------------------------------------------

def test_detect_targets_pairs_opus_and_sorts_newest_first(tmp_path: Path):
    old = tmp_path / "oldVisualization.data"
    new = tmp_path / "newVisualization.data"
    _write_visualization(old, [10] * 20)
    _write_visualization(new, [20] * 40)
    (tmp_path / "new.opus").write_bytes(b"fake")
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000, 2_000_000))

    found = core.detect_targets(tmp_path)
    assert [t.data_path.name for t in found] == [
        "newVisualization.data", "oldVisualization.data"]
    assert found[0].opus_path is not None
    assert found[0].length == 40
    assert found[1].opus_path is None


def test_detect_targets_skips_invalid_and_missing_dir(tmp_path: Path):
    bad = tmp_path / "badVisualization.data"
    bad.write_bytes(bytes([0, 200]))  # byte > 100
    assert core.detect_targets(tmp_path) == []
    assert core.detect_targets(tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# sumber
# ---------------------------------------------------------------------------

def test_is_supported_source():
    assert core.is_supported_source(Path("a.mp3"))
    assert core.is_supported_source(Path("b.MP4"))
    assert not core.is_supported_source(Path("c.txt"))
    assert not core.is_supported_source(Path("noext"))


def test_discover_sources_filters_and_limits(tmp_path: Path):
    for i in range(5):
        (tmp_path / f"s{i}.mp3").write_bytes(b"x" * (10 + i))
    (tmp_path / "note.txt").write_bytes(b"x" * 50)
    (tmp_path / "empty.mp3").write_bytes(b"")
    got = core.discover_sources([tmp_path], limit=3)
    assert len(got) == 3
    assert all(p.suffix == ".mp3" and p.stat().st_size > 0 for p in got)
    assert core.discover_sources([tmp_path / "missing"]) == []


# ---------------------------------------------------------------------------
# rencana encode / vendor
# ---------------------------------------------------------------------------

def test_build_encode_plan_mono_and_stereo():
    mono = core.build_encode_plan(1)
    assert mono.channels == 1 and mono.bitrate == "32k"
    assert mono.application == "voip" and len(mono.args_list) == 2
    assert all("{in}" in a and "{out}" in a for a in mono.args_list)
    stereo = core.build_encode_plan(2)
    assert stereo.channels == 2 and stereo.bitrate == "64k"
    assert len(stereo.args_list) == 4


def test_read_opus_vendor_found_and_missing():
    vendor = b"WhatsApp"
    blob = b"\x00\x01OpusTags" + struct.pack("<I", len(vendor)) + vendor + b"\xff" * 20
    assert core.read_opus_vendor(blob) == "WhatsApp"
    assert core.read_opus_vendor(b"no magic here" * 10) is None
    truncated = b"OpusTags" + struct.pack("<I", 50) + b"short"
    assert core.read_opus_vendor(truncated) is None


# ---------------------------------------------------------------------------
# kurva visualisasi
# ---------------------------------------------------------------------------

def test_compute_vis_empty_and_silent():
    assert core.compute_vis_from_samples([], 48000, 1.0) == [0] * 20
    assert core.compute_vis_from_samples([0.0] * 4800, 48000, 0.1) == [0] * 2


def test_compute_vis_shape_and_range():
    samples = [0.1] * 2400 + [0.9] * 2400  # setengah hening, setengah keras
    bars = core.compute_vis_from_samples(samples, 48000, 0.1)
    assert len(bars) == 2
    assert all(0 <= b <= 100 for b in bars)
    assert bars[1] == 100  # yang terkeras dinormalisasi ke 100
    assert bars[0] < bars[1]


def test_resample_bars():
    assert core.resample_bars([], 4) == [0.0] * 4
    assert core.resample_bars([7.0], 3) == [7.0] * 3
    assert core.resample_bars([1.0, 2.0], 2) == [1.0, 2.0]
    assert core.resample_bars([0.0, 100.0], 3) == [0.0, 50.0, 100.0]
    assert core.resample_bars([1.0], 0) == []


def test_clamp_sidecar_resamples_clamps_and_caps(monkeypatch):
    out = core.clamp_sidecar([0.0, 200.0, -5.0, 50.0], 4)
    assert list(out) == [0, 100, 0, 50]
    out2 = core.clamp_sidecar([10.0] * 4, 8)
    assert len(out2) == 8
    monkeypatch.setattr(core, "MAX_TEMPLATE_BYTES", 5)
    assert len(core.clamp_sidecar([10.0] * 10, 10)) == 5


# ---------------------------------------------------------------------------
# swap atomik / rollback
# ---------------------------------------------------------------------------

def test_atomic_swap_dry_run_touches_nothing(tmp_path: Path):
    data = tmp_path / "vVisualization.data"
    opus = tmp_path / "v.opus"
    _write_visualization(data, [1] * 10)
    opus.write_bytes(b"orig-opus")
    target = core.VoiceNoteTarget(data, opus, 10, 0.5, 0.0)
    res = core.atomic_swap(b"new-opus", bytes([2] * 10), target, dry_run=True)
    assert res.backup_opus is None and res.backup_data is None
    assert opus.read_bytes() == b"orig-opus"
    assert data.read_bytes() == bytes([1] * 10)


def test_atomic_swap_writes_and_backs_up_then_restores(tmp_path: Path):
    data = tmp_path / "vVisualization.data"
    opus = tmp_path / "v.opus"
    _write_visualization(data, [1] * 10)
    opus.write_bytes(b"orig-opus")
    target = core.VoiceNoteTarget(data, opus, 10, 0.5, 0.0)
    res = core.atomic_swap(b"new-opus", bytes([2] * 10), target, dry_run=False)
    assert res.backup_opus is not None and res.backup_data is not None
    assert opus.read_bytes() == b"new-opus"
    assert data.read_bytes() == bytes([2] * 10)
    core.restore_backup(res)
    assert opus.read_bytes() == b"orig-opus"
    assert data.read_bytes() == bytes([1] * 10)


# ---------------------------------------------------------------------------
# helper ffmpeg (dilewati bila binary tidak ada)
# ---------------------------------------------------------------------------

FFMPEG = core.find_ffmpeg()


def test_find_ffmpeg_returns_str_or_none():
    assert FFMPEG is None or isinstance(FFMPEG, str)


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg tidak terpasang")
def test_probe_and_decode_error_paths(tmp_path: Path):
    bogus = tmp_path / "bogus.mp3"
    bogus.write_bytes(b"not real audio" * 100)
    assert core.probe_duration(FFMPEG, bogus) == 0.0
    with pytest.raises(RuntimeError):
        core.decode_pcm_mono(FFMPEG, bogus)
