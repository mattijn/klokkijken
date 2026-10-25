"""The IJsbaan-klok: the game, every phrase on the clock face, and the dialogue at a frozen gate.

The dialogue is stateless, like an MCP elicitation on the 2026-07-28 protocol: each question goes to the client with
the dialogue so far, and the answer comes back with it.
"""

from pathlib import Path
from typing import Any

import uvicorn
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

import tutor
from klok import Reading, Step, judge, parse, readings, sentence, steps, words

__all__ = ["app"]

PORT = 8740
PAGE = Path(__file__).parent / "static" / "index.html"
PHRASES = [words(readings(i // 60, i % 60)[0]) for i in range(720)]


class Answer(BaseModel):
    hour: int
    minute: int
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


async def page(request: Request) -> FileResponse:
    return FileResponse(PAGE)


async def phrases(request: Request) -> JSONResponse:
    return JSONResponse(PHRASES)


async def question(dialogue: Dialogue) -> dict[str, Any]:
    step = dialogue.steps[dialogue.index]
    return {
        "dialogue": dialogue.model_dump(),
        "lead": await tutor.react(sentence(dialogue.said)) if dialogue.index == 0 else None,
        "question": step.ask,
        "options": step.options,
        "number": dialogue.index + 1,
        "total": len(dialogue.steps),
    }


async def read(request: Request) -> JSONResponse:
    """Repair the child's spelling and judge the time; a wrong time opens a dialogue, which the client asks next."""
    answer = Answer.model_validate(await request.json())
    spelled = await tutor.spell(answer.text)
    said = parse(spelled)
    right = words(readings(answer.hour, answer.minute)[0])
    if said is None:
        return JSONResponse({"verdict": "unreadable", "spelled": spelled, "right": right})
    verdict = judge(answer.hour, answer.minute, said)
    body: dict[str, Any] = {"verdict": verdict, "said": words(said), "right": right}
    if verdict == "wrong":
        dialogue = Dialogue(
            hour=answer.hour, minute=answer.minute, said=said, steps=steps(answer.hour, answer.minute, said), index=0
        )
        body["dialogue"] = dialogue.model_dump()
    return JSONResponse(body)


async def ask(request: Request) -> JSONResponse:
    """The dialogue's current question; the first one opens with the coach reacting to what the child wrote."""
    return JSONResponse(await question(Dialogue.model_validate(await request.json())))


async def answer_step(request: Request) -> JSONResponse:
    """Check a choice; a right one moves on to the next question, a wrong one gets the step's hint."""
    choice = Choice.model_validate(await request.json())
    dialogue = choice.dialogue
    step = dialogue.steps[dialogue.index]
    if choice.choice not in step.options:
        raise ValueError(f"{choice.choice!r} is not one of {step.options}")
    if choice.choice != step.answer:
        return JSONResponse({"correct": False, "hint": step.hint})
    dialogue = dialogue.model_copy(update={"index": dialogue.index + 1})
    if dialogue.index == len(dialogue.steps):
        return JSONResponse({"correct": True, "done": True})
    return JSONResponse({"correct": True, "done": False} | await question(dialogue))


app = Starlette(
    routes=[
        Route("/", page),
        Route("/phrases", phrases),
        Route("/read", read, methods=["POST"]),
        Route("/ask", ask, methods=["POST"]),
        Route("/step", answer_step, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    print(f"IJsbaan-klok: http://localhost:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
