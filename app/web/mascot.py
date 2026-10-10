"""پرنده وزیر، شخصیت مدرسه: SVG تخت با پنج حالت (idle، think، happy، sad، party).

برگردان store/learn/vazir-bird.html به پایتون تا سمت سرور در قالب‌ها کشیده شود (ماکرو mascot در
_ui.html). حرکت‌ها با CSS اپ است و با prefers-reduced-motion خاموش می‌شود. شناسه clipPath هر
نمونه یکتاست تا چند پرنده در یک صفحه (حتی پنهان) با هم تداخل نکنند.
"""

import itertools

from markupsafe import Markup

MOODS = ("idle", "think", "happy", "sad", "party")
C = {"body": "#2cb57b", "shade": "#1f9b67", "deep": "#0d4a35", "wing": "#1d9363",
     "wing_dark": "#167a52", "mint": "#c6f2db", "mint_shade": "#a9e6c8", "scarf": "#0f5a40",
     "scarf_dark": "#0a4431", "beak": "#ffcf4d", "beak_shade": "#f0a92e", "mouth": "#e2566c",
     "tongue": "#ff8a9b", "gold": "#f5c76a", "feet": "#ffc23d", "feet_shade": "#eea62b"}
_ids = itertools.count(1)


def _wing(side: str, angle: int, cls: str = "") -> str:
    x, y, f = (80, 192, 1) if side == "l" else (160, 192, -1)
    return (f'<g class="wing {side} {cls}"><g transform="translate({x} {y}) scale({f} 1) '
            f'rotate({angle})">'
            f'<path d="M4 -4 C-20 2 -32 30 -28 60 C-27 70 -19 74 -13 68 C-9 76 -1 75 2 66 '
            f'C8 71 15 64 13 54 C14 30 14 8 4 -4Z" fill="{C["wing"]}"/>'
            f'<path d="M-2 10 C-14 22 -20 44 -18 62 C-16 66 -13 66 -13 68 C-19 74 -27 70 -28 60 '
            f'C-32 30 -20 2 4 -4 C2 2 0 6 -2 10Z" fill="{C["wing_dark"]}"/></g></g>')


def _eye(cx: int, state: str, look: tuple[int, int] = (0, 0), side: str = "l") -> str:
    y = 108
    if state == "closed":
        return (f'<path d="M{cx - 15} {y + 4} Q{cx} {y - 14} {cx + 15} {y + 4}" '
                f'stroke="{C["deep"]}" stroke-width="6.5" fill="none" stroke-linecap="round"/>')
    clip = f"vb{next(_ids)}"
    lids = {"sad": (-2, -16) if side == "l" else (-16, -2), "skeptic": (-8, -8)}
    lid = ""
    if state in lids:
        outer, inner = lids[state]
        y1, y2 = (y + outer, y + inner) if side == "l" else (y + inner, y + outer)
        lid = (f'<path clip-path="url(#{clip})" d="M{cx - 30} {y1} L{cx + 30} {y2} '
               f'L{cx + 30} {y - 40} L{cx - 30} {y - 40}Z" fill="{C["mint"]}"/>'
               f'<path clip-path="url(#{clip})" d="M{cx - 30} {y1} L{cx + 30} {y2}" '
               f'stroke="{C["deep"]}" stroke-width="4"/>')
    lx, ly = look
    return (f'<clipPath id="{clip}"><circle cx="{cx}" cy="{y}" r="25"/></clipPath>'
            f'<g class="blink"><circle cx="{cx}" cy="{y}" r="25" fill="#fff"/>'
            f'<path clip-path="url(#{clip})" d="M{cx - 25} {y + 12} Q{cx} {y + 30} {cx + 25} '
            f'{y + 12} L{cx + 25} {y + 30} L{cx - 25} {y + 30}Z" fill="#e3f6ec"/>'
            f'<circle cx="{cx + lx}" cy="{y + 2 + ly}" r="16" fill="{C["deep"]}"/>'
            f'<circle cx="{cx + 6 + lx}" cy="{y - 5 + ly}" r="6" fill="#fff"/>'
            f'<circle cx="{cx - 6 + lx}" cy="{y + 9 + ly}" r="2.6" fill="#fff" opacity=".85"/>'
            f'{lid}</g>')


def _brow(cx: int, tilt: int, lift: int = 0) -> str:
    """ابروی کلفت کوتاه؛ tilt مثبت = گوشه بیرونی پایین‌تر (ناراحت)."""
    y = 72 - lift
    s = 1 if cx < 120 else -1
    return (f'<path d="M{cx - 13} {y + tilt * s} Q{cx} {y - 8} {cx + 13} {y - tilt * s}" '
            f'stroke="{C["deep"]}" stroke-width="7" fill="none" stroke-linecap="round"/>')


def _star(x: int, y: int, size: int, fill: str, cls: str) -> str:
    a, b = size, size * .18
    return (f'<path class="spark {cls}" d="M{x} {y - a} Q{x + b} {y - b} {x + a} {y} '
            f'Q{x + b} {y + b} {x} {y + a} Q{x - b} {y + b} {x - a} {y} '
            f'Q{x - b} {y - b} {x} {y - a}Z" fill="{fill}"/>')


def _eyes(mood: str) -> str:
    look = {"think": (6, -8), "sad": (-2, 6), "idle": (3, 0), "happy": (2, 0)}.get(mood, (0, 0))
    if mood == "party":
        return _eye(92, "closed") + _eye(148, "closed")
    if mood == "happy":
        return _eye(92, "open", look, "l") + _eye(148, "closed")
    if mood == "sad":
        return _eye(92, "sad", look, "l") + _eye(148, "sad", look, "r")
    if mood == "think":
        return _eye(92, "skeptic", look, "l") + _eye(148, "open", look, "r")
    return _eye(92, "open", look, "l") + _eye(148, "open", look, "r")


def _beak(mood: str) -> str:
    opening = {"idle": 10, "happy": 16, "party": 24}.get(mood, 0)
    mouth = ""
    if opening:
        mouth = (f'<path d="M108 138 Q120 {138 + opening} 132 138Z" fill="{C["mouth"]}"/>'
                 f'<path d="M113 {138 + opening * .45} Q120 {138 + opening * .9} 127 '
                 f'{138 + opening * .45} Q120 {138 + opening * .35} 113 {138 + opening * .45}Z" '
                 f'fill="{C["tongue"]}"/>')
    tip = 147 if mood == "sad" else 144
    return (f'{mouth}<path d="M106 128 Q120 118 134 128 Q131 138 120 {tip} Q109 138 106 128Z" '
            f'fill="{C["beak"]}"/>'
            f'<path d="M108 134 Q120 140 132 134 Q128 141 120 {tip} Q112 141 108 134Z" '
            f'fill="{C["beak_shade"]}"/>'
            f'<ellipse cx="115" cy="126" rx="5" ry="2.4" fill="#fff" opacity=".55"/>')


def _extra(mood: str) -> str:
    if mood == "think":
        return (f'<g class="q" transform="translate(196 50) scale(-1 1)"><path d="M-12 0 q0 -14 '
                f'13 -14 q13 0 13 12 q0 9 -12 13 v7" stroke="{C["body"]}" stroke-width="7" '
                f'fill="none" stroke-linecap="round"/><circle cx="2" cy="30" r="4.5" '
                f'fill="{C["body"]}"/></g>')
    if mood == "sad":
        return '<path d="M182 92 q7 12 0 19 q-7 -7 0 -19z" fill="#5ac8fa"/>'
    if mood in ("happy", "party"):
        return (_star(200, 70, 11, C["gold"], "") + _star(42, 88, 8, C["body"], "s2")
                + _star(206, 150, 7, C["body"], "s3"))
    return ""


def bird_svg(mood: str = "idle") -> Markup:
    if mood not in MOODS:
        mood = "idle"
    brows = {"idle": _brow(92, 1) + _brow(148, 1),
             "think": _brow(92, 0, -2) + _brow(148, -3, 8),
             "happy": _brow(92, 1, 3) + _brow(148, 1, 3),
             "sad": _brow(92, 7, 2) + _brow(148, 7, 2),
             "party": _brow(92, 2, 6) + _brow(148, 2, 6)}[mood]
    back, front = {
        "idle": (_wing("l", 0), f'<g class="wave">{_wing("r", 123)}</g>'),
        "think": (_wing("l", 0), _wing("r", -158)),
        "happy": (_wing("l", 0), _wing("r", 118)),
        "sad": (_wing("l", -6) + _wing("r", -6), ""),
        "party": ("", _wing("l", 126) + _wing("r", 126)),
    }[mood]
    blush = .5 if mood in ("happy", "party") else .28
    feet = "".join(
        f'<g><ellipse cx="{x}" cy="280" rx="20" ry="7" fill="{C["feet_shade"]}"/>'
        f'<ellipse cx="{x - 11}" cy="277" rx="8.5" ry="6.5" fill="{C["feet"]}"/>'
        f'<ellipse cx="{x}" cy="275" rx="9" ry="7" fill="{C["feet"]}"/>'
        f'<ellipse cx="{x + 11}" cy="277" rx="8.5" ry="6.5" fill="{C["feet"]}"/></g>'
        for x in (100, 140))
    return Markup(
        '<svg viewBox="20 6 200 292" aria-hidden="true" focusable="false">'
        '<ellipse class="shadow" cx="120" cy="288" rx="56" ry="7" fill="#000" opacity=".12"/>'
        f'<g class="rig">{feet}'
        f'<path d="M80 170 C70 198 66 236 74 256 C82 274 100 280 120 280 C140 280 158 274 166 256 '
        f'C174 236 170 198 160 170Z" fill="{C["body"]}"/>'
        f'<path d="M152 176 C166 200 172 236 164 258 C156 272 142 278 126 280 C150 268 160 246 160 '
        f'222 C160 202 156 188 152 176Z" fill="{C["shade"]}"/>'
        f'<path d="M90 198 C84 228 90 262 120 268 C150 262 156 228 150 198 '
        f'C140 208 100 208 90 198Z" fill="{C["mint"]}"/>'
        f'<path d="M108 226 l6 5 l6 -5 M120 240 l6 5 l6 -5 M104 248 l6 5 l6 -5" '
        f'stroke="{C["mint_shade"]}" stroke-width="3" fill="none" stroke-linecap="round"/>'
        f'<ellipse cx="120" cy="180" rx="46" ry="10" fill="{C["shade"]}"/>'
        f'{back}'
        f'<g class="feather"><path d="M110 46 C102 32 106 20 116 12 C115 24 120 34 126 44Z" '
        f'fill="{C["shade"]}"/><path d="M118 44 C120 28 132 16 150 15 C140 23 136 34 136 46Z" '
        f'fill="{C["body"]}"/><path d="M132 46 C140 36 152 32 164 34 C153 38 147 44 143 50Z" '
        f'fill="{C["shade"]}"/></g>'
        f'<path d="M120 38 C178 38 200 64 200 110 C200 154 172 178 120 178 C68 178 40 154 40 110 '
        f'C40 64 62 38 120 38Z" fill="{C["body"]}"/>'
        f'<path d="M168 50 C192 66 200 90 200 112 C200 150 178 174 136 178 '
        f'C172 162 188 140 188 110 C188 84 180 64 168 50Z" fill="{C["shade"]}"/>'
        '<ellipse cx="82" cy="62" rx="24" ry="9" transform="rotate(-22 82 62)" fill="#fff" '
        'opacity=".14"/>'
        f'<circle cx="92" cy="110" r="35" fill="{C["mint"]}"/>'
        f'<circle cx="148" cy="110" r="35" fill="{C["mint"]}"/>'
        f'<ellipse cx="120" cy="126" rx="30" ry="26" fill="{C["mint"]}"/>'
        f'<ellipse cx="62" cy="140" rx="10" ry="6" fill="#ff8fa3" opacity="{blush}"/>'
        f'<ellipse cx="178" cy="140" rx="10" ry="6" fill="#ff8fa3" opacity="{blush}"/>'
        f'{_eyes(mood)}{brows}{_beak(mood)}'
        f'<path d="M78 168 C100 180 140 180 162 168 L156 182 L120 216 L84 182Z" '
        f'fill="{C["scarf"]}"/>'
        f'<path d="M120 216 L104 196 Q120 204 136 196Z" fill="{C["scarf_dark"]}"/>'
        f'<path d="M84 182 Q120 194 156 182" stroke="{C["scarf_dark"]}" stroke-width="3" '
        f'fill="none"/>'
        f'<path d="M120 186 l8 9 l-8 9 l-8 -9z" fill="{C["gold"]}"/>'
        '<path d="M120 186 l4 4.5 l-4 4.5 l-4 -4.5z" fill="#fff3c9"/>'
        f'{front}</g>{_extra(mood)}</svg>')
