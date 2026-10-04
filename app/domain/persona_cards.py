"""۵۰ کارت شخصیت مالی و انتخاب نزدیک‌ترین کارت به پرسونای کاربر.

هر کارت یک «اثر انگشت» چهارتایی دارد (ریسک، انضباط، صبر، دانش؛ ۰ تا ۱۰۰) و چند
همخوانی با جواب‌ها (مثلاً هدف خرید خانه یا علاقه به رمزارز). کارتی برنده است که فاصله‌اش
از ویژگی‌های کاربر، منهای امتیاز همخوانی‌ها، کمترین باشد. متن فارسی کارت‌ها در strings.py.
"""

from dataclasses import dataclass

from app.domain.persona import STATS, Persona, stats

# امتیاز هر همخوانی (به واحد مجذور فاصله)؛ هدف مالی مهم‌ترین نشانه شخصیت است
AFFINITY_BONUS = {"goal": 1000}
DEFAULT_BONUS = 500


@dataclass(frozen=True)
class CardSpec:
    key: str
    fingerprint: tuple[int, int, int, int]  # risk, discipline, patience, knowledge
    affinity: dict[str, frozenset[str]]


def _c(key: str, risk: int, discipline: int, patience: int, knowledge: int,
       **affinity: str) -> CardSpec:
    return CardSpec(key, (risk, discipline, patience, knowledge),
                    {k: frozenset(v.split()) for k, v in affinity.items()})


SPECS: tuple[CardSpec, ...] = (
    _c("owl", 55, 80, 95, 80, goal="retire growth"),
    _c("turtle", 15, 85, 85, 60),
    _c("amir", 35, 95, 60, 50, goal="debt"),
    _c("architect", 50, 75, 75, 85),
    _c("eagle", 90, 55, 40, 90, goal="growth"),
    _c("surfer", 90, 35, 65, 65, interests="crypto"),
    _c("bee", 45, 90, 90, 55, goal="retire"),
    _c("sprout", 50, 50, 50, 5, age="u25 25_34"),
    _c("coin", 20, 75, 80, 30, goal="inflation", interests="gold"),
    _c("fox", 65, 60, 60, 80, interests="stocks"),
    _c("wolf", 95, 25, 15, 85),
    _c("lion", 80, 65, 60, 75, job="business"),
    _c("dolphin", 45, 70, 70, 95),
    _c("ant", 20, 95, 75, 25, goal="emergency"),
    _c("squirrel", 30, 80, 55, 25, goal="emergency"),
    _c("unicorn", 97, 40, 75, 60, goal="growth"),
    _c("simorgh", 60, 70, 85, 70, goal="debt"),
    _c("giraffe", 72, 65, 97, 75, goal="growth"),
    _c("elephant", 40, 75, 90, 90, age="45_54 55p"),
    _c("panda", 40, 30, 50, 30, style="spender"),
    _c("peacock", 55, 20, 30, 40, style="spender"),
    _c("cat", 50, 55, 55, 80, income="variable"),
    _c("octopus", 55, 70, 70, 80, interests="gold fx stocks property"),
    _c("bull", 75, 50, 55, 55, interests="stocks"),
    _c("bear", 35, 70, 60, 90),
    _c("rostam", 30, 80, 70, 45, household="kids supports"),
    _c("arash", 60, 85, 70, 45, goal="home car"),
    _c("kaveh", 45, 75, 60, 35, job="business freelancer"),
    _c("merchant", 65, 55, 50, 60, job="business"),
    _c("traveler", 40, 80, 55, 50, goal="migrate", interests="fx"),
    _c("racer", 45, 65, 40, 40, goal="car"),
    _c("nest", 35, 80, 75, 40, goal="home", housing="renter"),
    _c("midas", 80, 45, 40, 40, interests="gold"),
    _c("captain", 85, 20, 75, 50, style="spender"),
    _c("chess", 55, 80, 80, 90),
    _c("scientist", 60, 75, 60, 98),
    _c("dervish", 10, 90, 70, 30, style="frugal"),
    _c("astronaut", 92, 45, 70, 70, goal="growth", interests="crypto stocks"),
    _c("castle", 10, 75, 60, 40, emergency="gt6"),
    _c("gardener", 40, 80, 98, 50, goal="retire"),
    _c("cheetah", 80, 45, 20, 65),
    _c("camel", 30, 70, 95, 40, interests="deposit"),
    _c("parrot", 70, 30, 25, 20),
    _c("bat", 88, 35, 25, 70, interests="crypto"),
    _c("swan", 45, 75, 70, 90),
    _c("archer", 50, 90, 55, 60),
    _c("butterfly", 45, 45, 45, 30, job="student between"),
    _c("sailor", 60, 60, 45, 55, income="variable", job="freelancer"),
    _c("hedgehog", 20, 85, 50, 40, goal="debt"),
    _c("dragon", 60, 80, 80, 65, interests="gold property"),
)
CARDS: tuple[str, ...] = tuple(spec.key for spec in SPECS)
_BY_KEY = {spec.key: spec for spec in SPECS}


def _bonus(persona: Persona, spec: CardSpec) -> int:
    total = 0
    for key, wanted in spec.affinity.items():
        hit = (bool(wanted & set(persona.interests)) if key == "interests"
               else persona.get(key) in wanted)
        total += AFFINITY_BONUS.get(key, DEFAULT_BONUS) if hit else 0
    return total


def card_for(persona: Persona) -> str:
    """نزدیک‌ترین کارت؛ در تساوی، کارتی که زودتر آمده."""
    mine = stats(persona)
    user = tuple(mine[name] for name in STATS)

    def cost(spec: CardSpec) -> int:
        distance = sum((u - c) ** 2 for u, c in zip(user, spec.fingerprint, strict=True))
        return distance - _bonus(persona, spec)

    return min(SPECS, key=cost).key


def rarity(card: str) -> str:
    """کمیابی از روی افراطی بودن اثر انگشت: هرچه از میانه دورتر، کمیاب‌تر."""
    extreme = max(abs(v - 50) for v in _BY_KEY[card].fingerprint)
    if extreme >= 45:
        return "legendary"
    if extreme >= 38:
        return "epic"
    return "rare" if extreme >= 28 else "common"


def fingerprint(card: str) -> dict[str, int]:
    return dict(zip(STATS, _BY_KEY[card].fingerprint, strict=True))
