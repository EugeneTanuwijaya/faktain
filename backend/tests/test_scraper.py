from unittest.mock import patch

import pytest

from app.services.scraper_service import _parse_html


def test_wikipedia_keeps_lead_before_longer_sections_and_skips_tables():
    lead = "Kepresidenan Prabowo Subianto dimulai pada 20 Oktober 2024. Ia merupakan Presiden Indonesia ke-8."
    linked_lead = lead.replace("Presiden Indonesia ke-8", '<a href="/wiki/Presiden">Presiden Indonesia ke-8</a>')
    html = '<div class="mw-parser-output"><section><table><tr><td><p>Navigasi infobox</p></td></tr></table><p>' + linked_lead + '</p></section><section><p>' + 'Program kesehatan. ' * 100 + '</p></section></div>'
    with patch("app.services.scraper_service.Article") as newspaper:
        text = _parse_html("https://id.wikipedia.org/wiki/Kepresidenan_Prabowo_Subianto", html)
    assert text.startswith(lead)
    assert "Program kesehatan." in text and "Navigasi infobox" not in text
    newspaper.assert_not_called()


def test_non_wikipedia_still_uses_existing_article_parser():
    with patch("app.services.scraper_service.Article") as newspaper:
        newspaper.return_value.text = "Isi artikel asli"
        assert _parse_html("https://news.example/article", '<div class="mw-parser-output"><p>Unrelated markup</p></div>') == "Isi artikel asli"
        newspaper.return_value.parse.assert_called_once()


@pytest.mark.parametrize("container", ['class="mw-parser-output"', 'id="mw-content-text"'])
def test_wikipedia_skips_empty_style_container_and_preserves_actual_lead(container):
    lead = "Gibran Rakabuming Raka adalah Wakil Presiden Indonesia sejak 20 Oktober 2024."
    html = '<style class="mw-parser-output"></style><div ' + container + '><p>' + lead + '</p><p>' + "Pencalonan dan kampanye. " * 100 + '</p></div>'
    with patch("app.services.scraper_service.Article") as newspaper:
        text = _parse_html("https://id.wikipedia.org/wiki/Gibran_Rakabuming_Raka", html)
    assert text.startswith(lead)
    newspaper.assert_not_called()


def test_semantic_article_body_wins_over_long_archive_sidebar():
    lead = "Gibran resmi dilantik sebagai Wakil Presiden Republik Indonesia masa bakti 2024-2029."
    html = '<div class="post-article"><p>' + lead + '</p><p>Pelantikan berlangsung pada 20 Oktober 2024.</p></div><aside>' + '<p>Arsip berita September 2024.</p>' * 100 + '</aside>'
    with patch("app.services.scraper_service.Article") as newspaper:
        text = _parse_html("https://wapresri.go.id/contoh-artikel/", html)
    assert text.startswith(lead) and "Arsip berita" not in text
    newspaper.assert_not_called()
