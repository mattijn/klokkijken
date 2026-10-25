"""Dutch clock reading: how a time is said, what the child said, and which steps lead to the right words.

All time logic lives here, never in the language model: the model only repairs the child's spelling and reacts to it.
"""

import re
import unicodedata
from functools import partial
from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "VALUES",
    "Fit",
    "Mistake",
    "Reading",
    "Step",
    "Verdict",
    "alike",
    "judge",
    "minutes",
    "mistakes",
    "nudge",
    "number_word",
    "parse",
    "place",
    "readings",
    "sentence",
    "spelled_out",
    "steps",
    "tray",
    "twelve",
    "words",
]

UNITS = "_ een twee drie vier vijf zes zeven acht negen tien elf twaalf dertien veertien vijftien zestien zeventien"
UNIT_WORDS = (UNITS + " achttien negentien").split()
TENS = {2: "twintig", 3: "dertig", 4: "veertig", 5: "vijftig"}

Direction = Literal["over", "voor", "none"]
Mistake = Literal["24h", "order", "anchor", "direction", "number", "hour"]
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


class Fit(BaseModel):
    """How a block fits next in the sentence: its role when it does, a hint about the broken rule when it doesn't."""

    role: str | None
    hint: str | None
    mistake: Mistake | None
    done: bool


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
VALUES: dict[str, int] = {number_word(n): n for n in range(1, 60)}


def spelled_out(text: str) -> str:
    """The text with its numerals written as words, also when glued to a word: 4voor8 becomes vier voor acht."""
    return re.sub(r"\d+", numeral, text)


def numeral(match: re.Match[str]) -> str:
    n = int(match.group())
    return f" {number_word(n)} " if 1 <= n <= 59 else match.group()


def parse(text: str) -> Reading | None:
    """The time in correctly spelled Dutch words, or None when the words don't form a time."""
    tokens = [NUMBERS.get(t, t) for t in re.findall(r"[a-z]+", plain(text))]
    if tokens[-1:] == ["uur"]:
        tokens.pop()
    match tokens:
        case [int(hour)] if hour <= 24:
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


def swapped(reading: Reading) -> Reading | None:
    """The reading with its number and hour traded places, when both fit the other's spot."""
    if reading.direction == "none" or not 1 <= reading.number <= 12:
        return None
    return reading.model_copy(update={"number": reading.hour, "hour": reading.number})


def mistakes(hour: int, minute: int, reading: Reading) -> tuple[list[Mistake], Reading]:
    """What differs from the nearest right way to say the time, and that way; hour and number swapped is one mistake."""
    said = reading.model_copy(update={"hour": twelve(reading.hour)})
    right = readings(hour, minute)
    swap = swapped(said)
    order: list[Mistake] = []
    if swap is not None and nearest(right, swap) < nearest(right, said):
        said, order = swap, ["order"]
    form = min(right, key=partial(distance, said))
    found = order + differences(said, form)
    if form.direction == "none":  # on the hour or the half, minutes come down to one question: exactly there?
        direction: Mistake = "direction"
        found = list(dict.fromkeys(direction if m == "number" else m for m in found))
    clock: list[Mistake] = ["24h"] if reading.hour > 12 else []
    return clock + found, form


def distance(said: Reading, form: Reading) -> int:
    return len(differences(said, form))


def nearest(forms: list[Reading], said: Reading) -> int:
    return min(distance(said, form) for form in forms)


def steps(hour: int, minute: int, reading: Reading) -> list[Step]:
    """One question per mistake, in the order a child builds the sentence: order, anchor, direction, number, hour."""
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
            case "order":
                out.append(
                    Step(
                        mistake=mistake,
                        ask="Wat zeg je eerst: de minuten of het uur?",
                        options=["de minuten", "het uur"],
                        answer="de minuten",
                        hint="Het uur komt altijd achteraan, zoals in: tien over twee.",
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
                        ask="Bij voor en half noem je het uur dat nog komt. Welk uur komt eraan?",
                        options=[str(now), str(next_)],
                        answer=str(next_),
                        hint="Je gaat nog naar dat uur toe. Welk getal moet de kleine schaatser nog halen?",
                    )
                )
            case "hour":
                out.append(
                    Step(
                        mistake=mistake,
                        ask="Bij over noem je het uur dat net geweest is. Welk uur is dat?",
                        options=[str(now), str(next_)],
                        answer=str(now),
                        hint="Kijk welk getal de kleine schaatser net voorbij is.",
                    )
                )
    return out


def tray(hour: int, minute: int) -> list[str]:
    """The blocks to build the sentence from: its words and two that show a thinking mistake, numbers first."""
    reading = readings(hour, minute)[0]
    right = [word for word, role in words(reading)]
    other_hour = twelve(hour + 1) if reading.hour == twelve(hour) else twelve(hour)
    tempting = [number_word(other_hour)]
    if minute and reading.number != minute:
        tempting.append(number_word(minute))
    if reading.direction != "none":
        tempting.append({"over": "voor", "voor": "over"}[reading.direction])
    else:
        tempting.append("uur" if reading.half else "half")
    clear = [word for word in tempting if word not in right and not any(alike(word, r) for r in right)]
    return sorted(right + clear[:2], key=reading_order)


def alike(a: str, b: str) -> bool:
    """Blocks a child easily takes for each other: one written inside the other, as acht in achttien or 1 in 12."""
    forms = [(a, b)] + ([(str(VALUES[a]), str(VALUES[b]))] if a in VALUES and b in VALUES else [])
    return a != b and any(x in y or y in x for x, y in forms)


def reading_order(word: str) -> tuple[bool, int, str]:
    return word not in VALUES, VALUES.get(word, 0), word


def place(hour: int, minute: int, placed: list[str], word: str) -> Fit:
    """Whether `word` fits after the placed words in a right way to say the time."""
    n = len(placed)
    fitting = [r for r in readings(hour, minute) if [w for w, role in words(r)][:n] == placed and len(words(r)) > n]
    if not fitting:
        raise ValueError(f"{placed} starts no way to say {hour}:{minute:02}")
    for reading in fitting:
        next_word, role = words(reading)[n]
        if next_word == word:
            return Fit(role=role, hint=None, mistake=None, done=len(words(reading)) == n + 1)
    mistake, hint = clue(hour, minute, fitting[0], words(fitting[0])[n], word)
    return Fit(role=None, hint=hint, mistake=mistake, done=False)


def clue(hour: int, minute: int, reading: Reading, expected: tuple[str, str], word: str) -> tuple[Mistake, str]:
    """The thinking mistake behind `word` coming next in `reading` where `expected` does, and the rule it breaks."""
    hours = {number_word(twelve(hour)), number_word(twelve(hour + 1))}
    anchor = "de half" if reading.half else "het hele uur"
    match expected:
        case (_, "number") if word in hours:
            return "order", "Het uur komt achteraan. Begin met de minuten."
        case (_, "number") if minute and word == number_word(minute) and reading.direction == "voor":
            return "number", f"Niet {minute}: tel hoeveel minuten het nog duurt tot {anchor}."
        case (_, "number") if minute and word == number_word(minute):
            return "number", f"Niet {minute}: tel hoeveel minuten het al na {anchor} is."
        case (_, "number"):
            return "order", f"Begin met hoeveel minuten het is tot {anchor} of erna."
        case (_, "to-hour" | "to-half") if word in ("over", "voor"):
            return "direction", f"Is {anchor} al geweest? Dan zeg je over. Komt hij nog? Dan zeg je voor."
        case (_, "to-hour" | "to-half"):
            return "order", "Na de minuten komt over of voor."
        case (_, "half"):
            return "anchor", "Je telt vanaf de half, dus nu komt het woord half."
        case ("uur", "hour"):
            return "anchor", "Bij een heel uur zeg je er uur achter."
        case (_, "hour") if word in hours and (reading.half or reading.direction == "voor"):
            return "hour", "Bij voor en half noem je het uur dat nog komt."
        case (_, "hour") if word in hours:
            return "hour", "Bij over noem je het uur dat net geweest is."
        case (_, "hour"):
            return "order", "Nu komt het uur."
    raise ValueError(f"No clue for {expected}")


def nudge(hour: int, minute: int, at: int) -> str | None:
    """The rule to remember when the clock, at `at` minutes past twelve, has the right minutes on the wrong hour."""
    if at % 60 != minute or at % 720 == hour % 12 * 60 + minute:
        return None
    reading = readings(hour, minute)[0]
    if reading.half or reading.direction == "voor":
        return f"Bij {'half' if reading.half else 'voor'} hoort het uur dat nog komt. Tik dat uur en draai terug."
    if reading.direction == "over":
        return "Bij over hoort het uur dat net geweest is. Tik dat uur en draai vooruit."
    return "De grote wijzer staat goed. Tik nu het uur dat in de zin staat."
