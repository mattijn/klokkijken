"""The game's questions and answers, the same on the server and in the browser: every phrase on the clock face, the
dialogue at a frozen gate, and building sentences.

The dialogue is stateless, like an MCP elicitation on the 2026-07-28 protocol: each question goes to the client with
the dialogue so far, and the answer comes back with it. Only reading the child's spelling differs: the Mac asks
Apple's on-device model, the browser the rules in `klok.repair`.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from klok import (
    VALUES,
    Reading,
    Step,
    judge,
    nudge,
    parse,
    place,
    readings,
    repair,
    spelled_out,
    steps,
    together,
    tray,
    words,
)

__all__ = ["PHRASES", "Speller", "browser", "handle"]

PHRASES = [words(readings(i // 60, i % 60)[0]) for i in range(720)]

Speller = Callable[[str], Awaitable[str]]


class Clock(BaseModel):
    hour: int
    minute: int


class Placing(Clock):
    placed: list[str]
    word: str


class Position(Clock):
    at: int
    digital: bool


class Face(Clock):
    digital: bool


class Answer(Clock):
    text: str


class Dialogue(BaseModel):
    hour: int
    minute: int
    said: Reading
    steps: list[Step]
    index: int


class Choice(BaseModel):
    dialogue: Dialogue
    choice: str


def question(dialogue: Dialogue) -> dict[str, Any]:
    step = dialogue.steps[dialogue.index]
    return {
        "dialogue": dialogue.model_dump(),
        "question": step.ask,
        "options": step.options,
        "number": dialogue.index + 1,
        "total": len(dialogue.steps),
    }


async def read(answer: Answer, spell: Speller) -> dict[str, Any]:
    """Read the child's words, by the rules when they already form a time and by the speller when they don't, and judge
    the time; a wrong time opens a dialogue, which the client asks next."""
    said = parse(spelled_out(answer.text)) or parse(await spell(answer.text))
    right = words(readings(answer.hour, answer.minute)[0])
    if said is None:
        return {"verdict": "unreadable", "right": right}
    verdict = judge(answer.hour, answer.minute, said)
    body: dict[str, Any] = {"verdict": verdict, "said": words(said), "right": right}
    if verdict == "wrong":
        found = steps(answer.hour, answer.minute, said)
        body["dialogue"] = Dialogue(
            hour=answer.hour, minute=answer.minute, said=said, steps=found, index=0
        ).model_dump()
    return body


def ask(body: dict[str, Any]) -> dict[str, Any]:
    """The dialogue's current question."""
    return question(Dialogue.model_validate(body))


def answer_step(body: dict[str, Any]) -> dict[str, Any]:
    """Check a choice; a right one moves on to the next question, a wrong one gets the step's hint."""
    choice = Choice.model_validate(body)
    dialogue = choice.dialogue
    step = dialogue.steps[dialogue.index]
    if choice.choice not in step.options:
        raise ValueError(f"{choice.choice!r} is not one of {step.options}")
    if choice.choice != step.answer:
        return {"correct": False, "hint": step.hint}
    dialogue = dialogue.model_copy(update={"index": dialogue.index + 1})
    if dialogue.index == len(dialogue.steps):
        return {"correct": True, "done": True, "right": words(readings(dialogue.hour, dialogue.minute)[0])}
    return {"correct": True, "done": False} | question(dialogue)


def build(body: dict[str, Any]) -> dict[str, Any]:
    """The blocks to build the time's sentence from, each number with its digit."""
    clock = Clock.model_validate(body)
    return {"tray": [[word, VALUES.get(word)] for word in tray(clock.hour, clock.minute)]}


def place_word(body: dict[str, Any]) -> dict[str, Any]:
    """Whether the block fits next, with its role to colour it, or a hint about the rule it breaks."""
    placing = Placing.model_validate(body)
    return place(placing.hour, placing.minute, placing.placed, placing.word).model_dump()


def hint(body: dict[str, Any]) -> dict[str, Any]:
    """The rule to remember when the clock has the right minutes on the wrong hour."""
    position = Position.model_validate(body)
    found = nudge(position.hour, position.minute, position.at, position.digital)
    return {"nudge": found.model_dump() if found else None}


def start_together(body: dict[str, Any]) -> dict[str, Any]:
    """The questions before the child and the coach build the sentence together."""
    face = Face.model_validate(body)
    return {"steps": [step.model_dump() for step in together(face.hour, face.digital)]}


def phrases(body: dict[str, Any]) -> list[list[tuple[str, str]]]:
    return PHRASES


HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "phrases": phrases,
    "ask": ask,
    "step": answer_step,
    "build": build,
    "place": place_word,
    "nudge": hint,
    "together": start_together,
}


async def handle(name: str, body: dict[str, Any], spell: Speller) -> Any:
    if name == "read":
        return await read(Answer.model_validate(body), spell)
    return HANDLERS[name](body)


async def by_rules(text: str) -> str:
    return repair(text)


async def browser(name: str, body: str) -> str:
    """The browser's way in, from Pyodide: JSON in and out, with the spelling read by the rules."""
    return json.dumps(await handle(name, json.loads(body), by_rules))
