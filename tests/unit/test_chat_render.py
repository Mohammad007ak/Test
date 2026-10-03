from app.web.render import chat_markdown


def test_escapes_html_first() -> None:
    html = str(chat_markdown("<script>alert(1)</script> **x**"))
    assert "<script>" not in html and "&lt;script&gt;" in html and "<strong>x</strong>" in html


def test_bold_lists_and_paragraphs() -> None:
    html = str(chat_markdown("خلاصه:\n- خرید: **1,200,000** تومان\n- قبض: 450,000\n\nپایان"))
    assert html.count("<li>") == 2 and "<ul>" in html
    assert "<strong>۱٬۲۰۰٬۰۰۰</strong>" in html  # ارقام فارسی و جداکننده فارسی
    assert html.startswith("<p>خلاصه:</p>") and html.endswith("<p>پایان</p>")


def test_numbered_list_and_bullet_dot() -> None:
    html = str(chat_markdown("1. اول\n2. دوم\n• سوم"))
    assert "<ol>" in html and html.count("<li>") == 3


def test_headings_become_bold_lines() -> None:
    assert "<p><strong>جمع‌بندی</strong></p>" in str(chat_markdown("### جمع‌بندی"))
