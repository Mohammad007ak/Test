"""رندر امن مقاله‌ها و درستی همه فایل‌های مقاله."""

from app.web.articles import all_articles, parse, render


def test_render_headings_lists_bold_and_links() -> None:
    source = "## عنوان\n\nبند با **پررنگ** و [ابزار](/tools/loan).\n\n- یک\n- دو\n\n1. اول\n2. دوم"
    html = str(render(source))
    assert "<h2>عنوان</h2>" in html
    assert "<strong>پررنگ</strong>" in html and '<a href="/tools/loan">ابزار</a>' in html
    assert "<ul><li>یک</li><li>دو</li></ul>" in html
    assert "<ol><li>اول</li><li>دوم</li></ol>" in html


def test_render_escapes_html_and_blocks_unsafe_links() -> None:
    html = str(render('<script>alert(1)</script> [x](javascript:alert(1)) [y](http://evil.example)'))
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert 'href="javascript' not in html and 'href="http://' not in html


def test_parse_front_matter_and_reading_time() -> None:
    article = parse("demo", "---\ntitle: تست\ndescription: توضیح\nupdated: 1405-07-13\n---\n"
                    + "کلمه " * 400)
    assert article.title == "تست" and article.updated.isoformat() == "2026-10-05"
    assert article.minutes == 2


def test_every_article_file_is_valid() -> None:
    articles = all_articles()
    assert len(articles) >= 5
    for a in articles:
        assert a.title and 50 <= len(a.description) <= 170, a.slug
        assert "<h2>" in a.html and a.minutes >= 2, a.slug


def test_landing_articles_exist() -> None:
    from app.web import strings as s
    from app.web.articles import by_slug

    assert all(by_slug(slug) for slug in s.LANDING_ARTICLES)
