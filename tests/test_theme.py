"""Tes disiplin tema web Catppuccin: satu aksen + banner terstruktur."""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CSS = (HERE / "web" / "styles.css").read_text(encoding="utf-8")
HTML = (HERE / "web" / "index.html").read_text(encoding="utf-8")
JS = (HERE / "web" / "app.js").read_text(encoding="utf-8")


def _block(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", CSS)
    assert m, f"blok {selector} tidak ada di styles.css"
    return m.group(1)


def test_aksen_tunggal_mauve_untuk_aksi_primer():
    assert "--primary:#CBA6F7" in CSS.replace(" ", "")
    primary = _block(".btn.primary")
    assert "var(--primary)" in primary
    assert "var(--green)" not in primary


def test_kartu_punya_batas_tegas():
    assert "1px solid var(--surface1)" in CSS
    assert "--radius:14px" in CSS.replace(" ", "")


def test_banner_kesehatan_terstruktur_bukan_teks_mentah():
    assert 'id="health-banner"' in HTML
    assert 'id="health-list"' in JS or '"health-list"' in JS
    assert "Salin" in JS and "clipboard" in JS
    assert "fix-row" in CSS and ".health-list" in CSS


def test_pill_health_tidak_terpotong_di_mobile():
    assert "-webkit-line-clamp" in CSS
