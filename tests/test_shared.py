"""Tests for .Shared auto-detection (stdlib only, no device needed)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vnswap_core as core


def _sidecar(d: Path, name: str) -> None:
    (d / name).write_bytes(bytes([10]) * 20)


def test_env_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VNSWAP_SHARED", str(tmp_path))
    assert tmp_path in core.find_shared_candidates()


def test_env_missing_dir_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VNSWAP_SHARED", str(tmp_path / "nope"))
    assert tmp_path / "nope" not in core.find_shared_candidates()


def test_count_targets(tmp_path: Path):
    _sidecar(tmp_path, "aVisualization.data")
    (tmp_path / "note.txt").write_bytes(b"x")
    assert core.count_shared_targets(tmp_path) == 1
    assert core.count_shared_targets(tmp_path / "missing") == 0


def test_rank_orders_by_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _sidecar(a, "xVisualization.data")
    _sidecar(b, "yVisualization.data")
    _sidecar(b, "zVisualization.data")
    monkeypatch.setattr(core, "find_shared_candidates", lambda: [a, b])
    ranked = core.rank_shared_candidates()
    assert [p for p, _ in ranked] == [b, a]
    assert ranked[0][1] == 2


def test_auto_prefers_explicit_and_richest(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setattr(core, "rank_shared_candidates",
                        lambda: [(b, 2), (a, 1)])
    assert core.auto_shared_dir(explicit=a) == a
    assert core.auto_shared_dir() == b


def test_auto_falls_back_without_candidates(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(core, "rank_shared_candidates", lambda: [])
    monkeypatch.delenv("VNSWAP_SHARED", raising=False)
    assert core.auto_shared_dir() == core.DEFAULT_SHARED_DIR
    missing = tmp_path / "nope"
    assert core.auto_shared_dir(explicit=missing) == missing
