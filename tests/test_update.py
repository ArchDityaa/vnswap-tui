"""Tes untuk subcommand launcher dan update mandiri (hanya stdlib + git)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vnswap
from vnswap import resolve_mode, run_update, split_subcommand, _read_version

GIT = shutil.which("git")
need_git = pytest.mark.skipif(GIT is None, reason="git tidak terpasang")


# ---------------------------------------------------------------------------
# split_subcommand / resolve_mode (murni, tanpa efek samping)
# ---------------------------------------------------------------------------

def test_split_subcommand_ambil_posisi_pertama():
    assert split_subcommand(["web", "--port", "8080"]) == ("web", ["--port", "8080"])
    assert split_subcommand(["update", "--check"]) == ("update", ["--check"])
    assert split_subcommand(["--web"]) == (None, ["--web"])
    assert split_subcommand([]) == (None, [])


def test_split_subcommand_bukan_posisi_pertama_diabaikan():
    assert split_subcommand(["--shared", "web"]) == (None, ["--shared", "web"])


def _ns(**kw):
    base = {"web": False, "cli": False}
    base.update(kw)
    return argparse.Namespace(**base)


def test_resolve_mode_subcommand_menang_atas_flag():
    assert resolve_mode("cli", _ns(web=True)) == "cli"
    assert resolve_mode("tui", _ns(web=True, cli=True)) == "tui"
    assert resolve_mode("update", _ns()) == "update"


def test_resolve_mode_flag_lama_tetap_jalan():
    assert resolve_mode(None, _ns(web=True)) == "web"
    assert resolve_mode(None, _ns(cli=True)) == "cli"
    assert resolve_mode(None, _ns()) == "tui"


# ---------------------------------------------------------------------------
# run_update dengan repo git sementara
# ---------------------------------------------------------------------------

def _git(cwd: Path, *args: str) -> None:
    subprocess.run([GIT, *args], cwd=cwd, check=True,
                   capture_output=True, timeout=120)


@pytest.fixture()
def origin_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "origin"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tes@example.com")
    _git(repo, "config", "user.name", "tes")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "vnswap_core.py").write_text('VERSION = "9.9.0"\n', encoding="utf-8")
    (repo / "vnswap.py").write_text("# dummy\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "awal")
    return repo


@need_git
def test_update_sudah_terbaru(tmp_path: Path, origin_repo: Path, capsys):
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", str(origin_repo), str(clone))
    assert run_update(repo=clone) == 0
    assert "sudah versi terbaru" in capsys.readouterr().out


@need_git
def test_update_check_dan_pull(tmp_path: Path, origin_repo: Path, capsys):
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", str(origin_repo), str(clone))
    (origin_repo / "baru.txt").write_text("baru", encoding="utf-8")
    _git(origin_repo, "add", ".")
    _git(origin_repo, "commit", "-m", "kedua")
    assert run_update(check_only=True, repo=clone) == 2
    assert "ada update" in capsys.readouterr().out
    assert run_update(repo=clone) == 0
    assert (clone / "baru.txt").is_file()
    assert "terupdate" in capsys.readouterr().out


@need_git
def test_update_batal_bila_kotor(tmp_path: Path, origin_repo: Path, capsys):
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", str(origin_repo), str(clone))
    (clone / "vnswap.py").write_text("# ubahan lokal\n", encoding="utf-8")
    assert run_update(repo=clone) == 1
    assert "perubahan lokal" in capsys.readouterr().out


@need_git
def test_update_bukan_repo_git(tmp_path: Path, capsys):
    assert run_update(repo=tmp_path / "kosong") == 1
    assert "bukan clone git" in capsys.readouterr().out


def test_read_version_baca_tanpa_import(tmp_path: Path):
    (tmp_path / "vnswap_core.py").write_text('VERSION = "1.6.0"\n', encoding="utf-8")
    assert _read_version(tmp_path) == "1.6.0"
    assert _read_version(tmp_path / "hilang") is None
