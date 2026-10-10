import re

from app.web.mascot import MOODS, bird_svg


def test_every_mood_draws_and_clip_ids_are_unique() -> None:
    svgs = [str(bird_svg(mood)) for mood in MOODS] + [str(bird_svg("idle"))]
    assert all(svg.startswith("<svg") and svg.endswith("</svg>") for svg in svgs)
    ids = [i for svg in svgs for i in re.findall(r'id="([^"]+)"', svg)]
    assert len(ids) == len(set(ids))


def test_unknown_mood_falls_back_to_idle() -> None:
    assert 'class="wave"' in str(bird_svg("nope"))
