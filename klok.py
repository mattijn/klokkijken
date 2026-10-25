"""Dutch clock reading: how a time is said, what the child said, and which steps lead to the right words.

All time logic lives here, never in the language model: the model only repairs the child's spelling and reacts to it.
"""

import re
import unicodedata
from functools import partial
from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "Mistake",
    "Reading",
    "Step",
    "Verdict",
    "judge",
    "minutes",
    "mistakes",
    "number_word",
    "parse",
    "readings",
    "sentence",
    "steps",
    "twelve",
    "words",
]

UNITS = "_ een twee drie vier vijf zes zeven acht negen tien elf twaalf dertien veertien vijftien zestien zeventien"
UNIT_WORDS = (UNITS + " achttien negentien").split()
TENS = {2: "twintig", 3: "dertig", 4: "veertig", 5: "vijftig"}

Direction = Literal["over", "voor", "none"]
Mistake = Literal["24h", "anchor", "direction", "number", "hour"]
Verdict = Literal["right", "other_words", "wrong"]

FIELDS: list[tuple[Mistake, str]] = [
    ("anchor", "half"),
    ("direction", "direction"),
    ("number", "number"),
    ("hour", "hour"),
]


class Reading(BaseModel):
    """A time in Dutch words: [number] [over|voor] [half] hour; `number` 15 is 'kwart', an `hour` above 12 is kept."""

    number: int = Field(ge=0, le=59)
    direction: Direction
    half: bool
    hour: int = Field(ge=1, le=24)


class Step(BaseModel):
    """One question on the way to the right words, with its answer and a hint for a wrong choice."""

    mistake: Mistake
    ask: str
    options: list[str]
    answer: str
    hint: str


def twelve(hour: int) -> int:
    return hour % 12 or 12


def number_word(n: int) -> str:
    if not 1 <= n <= 59:
        raise ValueError(f"No Dutch number word for {n}")
    if n == 1:
        return "één"
    if n < 20:
        return UNIT_WORDS[n]
    tens, unit = divmod(n, 10)
    if not unit:
        return TENS[tens]
    first = "een" if unit == 1 else UNIT_WORDS[unit]
    return f"{first}{'ën' if first.endswith('e') else 'en'}{TENS[tens]}"


def readings(hour: int, minute: int) -> list[Reading]:
    """The right ways to say a time, the usual one first."""
    now, next_ = twelve(hour), twelve(hour + 1)
    if minute == 0:
        return [Reading(number=0, direction="none", half=False, hour=now)]
    if minute == 30:
        return [Reading(number=0, direction="none", half=True, hour=next_)]
    if minute <= 15:
        return [Reading(number=minute, direction="over", half=False, hour=now)]
    if minute < 30:
        usual = Reading(number=30 - minute, direction="voor", half=True, hour=next_)
        return [usual, Reading(number=minute, direction="over", half=False, hour=now)][: 2 if minute <= 20 else 1]
    if minute < 45:
        usual = Reading(number=minute - 30, direction="over", half=True, hour=next_)
        return [usual, Reading(number=60 - minute, direction="voor", half=False, hour=next_)][
            : 2 if minute >= 40 else 1
        ]
    return [Reading(number=60 - minute, direction="voor", half=False, hour=next_)]


def words(reading: Reading) -> list[tuple[str, str]]:
    """The words with their role, which the game colours: about the hour, about the half, or the hour itself."""
    out: list[tuple[str, str]] = []
    if reading.direction != "none" and reading.number:
        kwart = reading.number == 15 and not reading.half
        out.append(("kwart" if kwart else number_word(reading.number), "number"))
    if reading.direction != "none":
        out.append((reading.direction, "to-half" if reading.half else "to-hour"))
    if reading.half:
        out.append(("half", "half"))
    out.append((number_word(reading.hour), "hour"))
    if reading.direction == "none" and not reading.half:
        out.append(("uur", "hour"))
    return out


def sentence(reading: Reading) -> str:
    return " ".join(word for word, role in words(reading))


def plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


NUMBERS: dict[str, int] = {plain(number_word(n)): n for n in range(1, 60)} | {"kwart": 15}


def parse(text: str) -> Reading | None:
    """The time in correctly spelled Dutch words, or None when the words don't form a time."""
    tokens = [NUMBERS.get(t, t) for t in re.findall(r"[a-z]+", plain(text))]
    match tokens:
        case [int(hour)] | [int(hour), "uur"] if hour <= 24:
            return Reading(number=0, direction="none", half=False, hour=hour)
        case ["half", int(hour)] if hour <= 24:
            return Reading(number=0, direction="none", half=True, hour=hour)
        case [int(number), "over" | "voor" as direction, int(hour)] if hour <= 24:
            return Reading(number=number, direction=direction, half=False, hour=hour)
        case [int(number), "over" | "voor" as direction, "half", int(hour)] if hour <= 24:
            return Reading(number=number, direction=direction, half=True, hour=hour)
    return None


def minutes(reading: Reading) -> int:
    """The time a reading names, in minutes past twelve on a twelve-hour clock face."""
    anchor = reading.hour % 12 * 60 - (30 if reading.half else 0)
    sign = {"over": 1, "voor": -1, "none": 0}[reading.direction]
    return (anchor + sign * reading.number) % 720


def judge(hour: int, minute: int, reading: Reading) -> Verdict:
    if reading.hour <= 12 and reading in readings(hour, minute):
        return "right"
    if reading.hour <= 12 and minutes(reading) == hour % 12 * 60 + minute:
        return "other_words"
    return "wrong"


def differences(said: Reading, form: Reading) -> list[Mistake]:
    return [mistake for mistake, field in FIELDS if getattr(said, field) != getattr(form, field)]


def mistakes(hour: int, minute: int, reading: Reading) -> tuple[list[Mistake], Reading]:
    """What differs from the nearest right way to say the time, and that way."""
    said = reading.model_copy(update={"hour": twelve(reading.hour)})
    form = min(readings(hour, minute), key=partial(distance, said))
    found = differences(said, form)
    if form.direction == "none":  # on the hour or the half, minutes come down to one question: exactly there?
        direction: Mistake = "direction"
        found = list(dict.fromkeys(direction if m == "number" else m for m in found))
    clock: list[Mistake] = ["24h"] if reading.hour > 12 else []
    return clock + found, form


def distance(said: Reading, form: Reading) -> int:
    return len(differences(said, form))


def steps(hour: int, minute: int, reading: Reading) -> list[Step]:
    """One question per mistake, in the order a child builds the sentence: anchor, direction, number, hour."""
    found, form = mistakes(hour, minute, reading)
    now, next_ = twelve(hour), twelve(hour + 1)
    anchor = "de half" if form.half else "het hele uur"
    out = []
    for mistake in found:
        match mistake:
            case "24h":
                options = sorted({twelve(reading.hour), reading.hour, reading.hour - 10})
                out.append(
                    Step(
                        mistake=mistake,
                        ask=f"Op de wijzerklok heet {reading.hour} anders. Welk getal is het daar?",
                        options=[str(o) for o in options],
                        answer=str(twelve(reading.hour)),
                        hint=f"Tel verder na de 12: 13 is 1, 14 is 2, en zo door tot {reading.hour}.",
                    )
                )
            case "anchor":
                out.append(
                    Step(
                        mistake=mistake,
                        ask="Staat de grote wijzer dichter bij de half of bij het hele uur?",
                        options=["bij de half", "bij het hele uur"],
                        answer="bij de half" if form.half else "bij het hele uur",
                        hint="Kijk naar de kleur onder de grote wijzer: roze hoort bij de half, blauw bij het hele uur.",
                    )
                )
            case "direction" if form.direction == "none":
                out.append(
                    Step(
                        mistake=mistake,
                        ask=f"Staat de grote wijzer precies op {anchor}?",
                        options=["ja, precies", "nee"],
                        answer="ja, precies",
                        hint="Kijk waar de punt van de grote wijzer staat.",
                    )
                )
            case "direction":
                past = form.direction == "over"
                out.append(
                    Step(
                        mistake=mistake,
                        ask=f"Is de grote wijzer al voorbij {anchor}, of moet hij er nog naartoe?",
                        options=["al voorbij", "er nog naartoe"],
                        answer="al voorbij" if past else "er nog naartoe",
                        hint=f"De wijzers draaien rechtsom. Is {anchor} al geweest, of komt hij nog?",
                    )
                )
            case "number":
                near = [form.number, reading.number, form.number + 5, form.number - 5]
                options = list(dict.fromkeys(n for n in near if 1 <= n <= 30))[:3]
                out.append(
                    Step(
                        mistake=mistake,
                        ask=f"Hoeveel minuten zitten er tussen de grote wijzer en {anchor}?",
                        options=[str(o) for o in sorted(options)],
                        answer=str(form.number),
                        hint=f"Elk groot streepje is vijf minuten, elk klein streepje één. Tel vanaf {anchor}.",
                    )
                )
            case "hour" if form.half or form.direction == "voor":
                out.append(
                    Step(
                        mistake=mistake,
                        ask="Naar welk uur schaatst de kleine schaatser?",
                        options=[str(now), str(next_)],
                        answer=str(next_),
                        hint="Kijk welk getal de kleine schaatser nog moet halen.",
                    )
                )
            case "hour":
                out.append(
                    Step(
                        mistake=mistake,
                        ask="Welk uur is net geweest?",
                        options=[str(now), str(next_)],
                        answer=str(now),
                        hint="Kijk welk getal de kleine schaatser net voorbij is.",
                    )
                )
    return out
