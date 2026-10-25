import pytest

from klok import (
    Reading,
    alike,
    judge,
    minutes,
    mistakes,
    nudge,
    number_word,
    parse,
    place,
    readings,
    sentence,
    spelled_out,
    steps,
    together,
    tray,
    words,
)


def said(text: str) -> Reading:
    reading = parse(text)
    assert reading is not None
    return reading


@pytest.mark.parametrize(
    ("n", "word"), [(1, "één"), (13, "dertien"), (21, "eenentwintig"), (22, "tweeëntwintig"), (37, "zevenendertig")]
)
def test_number_words(n: int, word: str) -> None:
    assert number_word(n) == word


@pytest.mark.parametrize(
    ("hour", "minute", "spoken"),
    [
        (20, 0, ["acht uur"]),
        (20, 15, ["kwart over acht"]),
        (20, 20, ["tien voor half negen", "twintig over acht"]),
        (20, 30, ["half negen"]),
        (20, 37, ["zeven over half negen"]),
        (20, 40, ["tien over half negen", "twintig voor negen"]),
        (20, 45, ["kwart voor negen"]),
        (0, 30, ["half één"]),
        (23, 55, ["vijf voor twaalf"]),
    ],
)
def test_readings(hour: int, minute: int, spoken: list[str]) -> None:
    assert [sentence(r) for r in readings(hour, minute)] == spoken


def test_every_reading_names_its_own_time() -> None:
    for t in range(720):
        assert {minutes(r) for r in readings(t // 60, t % 60)} == {t}


def test_every_sentence_parses_back() -> None:
    for t in range(720):
        for reading in readings(t // 60, t % 60):
            assert parse(sentence(reading)) == reading


@pytest.mark.parametrize("text", ["over half negen", "zeventig over acht", "zes uur over half acht", ""])
def test_words_that_are_no_time(text: str) -> None:
    assert parse(text) is None


def test_uur_after_a_time_is_allowed() -> None:
    assert parse("vier voor negen uur") == parse("vier voor negen")


@pytest.mark.parametrize(
    ("text", "verdict", "found"),
    [
        ("tien over half negen", "right", []),
        ("Twintig voor negen", "right", []),
        ("veertig over acht", "other_words", []),
        ("twintig over negen", "wrong", ["direction"]),
        ("tien over half acht", "wrong", ["hour"]),
        ("tien voor half negen", "wrong", ["direction"]),
        ("tien over half eenentwintig", "wrong", ["24h"]),
        ("tien over negen", "wrong", ["anchor"]),
        ("zeven over negen", "wrong", ["anchor", "number"]),
    ],
)
def test_twenty_to_nine(text: str, verdict: str, found: list[str]) -> None:
    assert judge(20, 40, said(text)) == verdict
    if verdict == "wrong":
        assert mistakes(20, 40, said(text))[0] == found


def test_minutes_on_the_hour_or_half_are_one_question() -> None:
    assert mistakes(21, 0, said("vijf over negen"))[0] == ["direction"]
    assert mistakes(20, 30, said("tien over half negen"))[0] == ["direction"]


def test_steps_lead_to_their_answers() -> None:
    texts = ["twintig over negen", "half acht", "kwart voor twaalf", "zeven over half negen", "acht over half twintig"]
    for t in range(0, 720, 7):
        for text in texts:
            for step in steps(t // 60, t % 60, said(text)):
                assert step.answer in step.options
                assert len(set(step.options)) == len(step.options) >= 2


def test_step_for_twenty_past_nine() -> None:
    [step] = steps(20, 40, said("twintig over negen"))
    assert step.answer == "er nog naartoe"
    assert "het hele uur" in step.ask


@pytest.mark.parametrize(
    ("text", "found"),
    [("acht voor vier", ["order", "hour"]), ("vier voor acht", ["hour"]), ("negen voor vier", ["order"])],
)
def test_four_to_nine(text: str, found: list[str]) -> None:
    assert mistakes(20, 56, said(text))[0] == found


def test_the_hour_question_names_the_rule() -> None:
    [step] = steps(20, 56, said("vier voor acht"))
    assert step.ask.startswith("Bij voor en half noem je het uur dat nog komt.")
    assert step.answer == "9"


def test_every_sentence_builds_from_its_tray() -> None:
    for t in range(720):
        hour, minute = t // 60, t % 60
        blocks = tray(hour, minute)
        right = [word for word, role in words(readings(hour, minute)[0])]
        assert 1 <= len(blocks) - len(right) <= 2
        for n, word in enumerate(right):
            for block in set(blocks) - {word}:
                fits = any([w for w, role in words(r)][: n + 1] == right[:n] + [block] for r in readings(hour, minute))
                assert (place(hour, minute, right[:n], block).hint is None) == fits
            fit = place(hour, minute, right[:n], word)
            assert (fit.hint, fit.done) == (None, n + 1 == len(right))
            blocks.remove(word)
        assert blocks


def test_no_lookalike_blocks() -> None:
    for t in range(720):
        hour, minute = t // 60, t % 60
        right = [word for word, role in words(readings(hour, minute)[0])]
        blocks = tray(hour, minute)
        for word in right:
            blocks.remove(word)
        assert not any(alike(block, word) for block in blocks for word in right)


def test_lookalikes() -> None:
    assert alike("acht", "achttien")
    assert alike("één", "twaalf")
    assert not alike("acht", "negen")


def said_nudge(hour: int, minute: int, at: int, digital: bool = False) -> tuple[str, str] | None:
    found = nudge(hour, minute, at, digital)
    return None if found is None else (found.mistake, found.text)


def test_half_five_turned_back_from_four() -> None:
    assert said_nudge(16, 30, 3 * 60 + 30) == ("hour", "Nog niet de 5. Tik de 4.")
    assert said_nudge(16, 30, 4 * 60 + 30) is None
    assert said_nudge(16, 30, 4 * 60) is None


def test_nudges_follow_the_sentence() -> None:
    assert said_nudge(20, 56, 7 * 60 + 56) == ("hour", "Nog niet de 9. Tik de 8.")
    assert said_nudge(20, 10, 9 * 60 + 10) == ("hour", "Tik de 8.")
    assert said_nudge(20, 0, 9 * 60) == ("hour", "Tik de 8.")


def test_an_hour_too_early_on_the_digital_clock() -> None:
    assert said_nudge(22, 36, 9 * 60 + 36, digital=True) == ("24h", "22 = 10")
    assert said_nudge(8, 56, 9 * 60 + 56, digital=True) == ("hour", "Tik de 8.")


def test_together_asks_the_clock_hour_first_on_the_digital_clock() -> None:
    [step] = together(15, digital=True)
    assert (step.mistake, step.options, step.answer) == ("24h", ["2", "3", "4"], "3")
    assert together(13, digital=True)[0].options == ["1", "2", "12"]
    assert together(15, digital=False) == []
    assert together(9, digital=True) == []


@pytest.mark.parametrize(
    ("text", "spoken"),
    [("4voor8", "vier voor acht"), ("10 over half 9", "tien over half negen"), ("half 12", "half twaalf")],
)
def test_numerals_become_words(text: str, spoken: str) -> None:
    assert parse(spelled_out(text)) == parse(spoken)
