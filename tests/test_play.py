"""Play whole rounds in a real browser: tap the hour, turn the big hand, build sentences and write at frozen gates.

The writing uses digits and correctly spelled words, which the rules read without the speller.
"""

import math
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
import uvicorn
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from server import app

LEVELS = range(5)


@pytest.fixture(scope="module")
def url() -> Iterator[str]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join()


@pytest.fixture(scope="module")
def playwright() -> Iterator[Playwright]:
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="module")
def chromium(playwright: Playwright) -> Iterator[Browser]:
    browser = playwright.chromium.launch()
    yield browser
    browser.close()


def open_game(browser: Browser, url: str, **context: Any) -> tuple[Page, list[Any]]:
    page = browser.new_context(**context).new_page()
    errors: list[Any] = []

    def keep(error: Any) -> None:
        errors.append(error)

    page.on("pageerror", keep)
    page.goto(url)
    page.evaluate("localStorage.setItem('ijsbaan.coached', 'true'); localStorage.setItem('ijsbaan.calm', 'true')")
    page.reload()
    page.wait_for_function("PHRASES.length === 720")
    return page, errors


def point(page: Page, angle: float, radius: float) -> tuple[float, float]:
    cx, cy, r = page.evaluate("[CX, CY, R]")
    return cx + radius * r * math.sin(angle), cy - radius * r * math.cos(angle)


def skate(page: Page) -> None:
    """Tap the hour the target sits in, then turn the big hand forward from twelve to its minutes."""
    hour, minute = page.evaluate("[Math.floor(mod(S.target, 720) / 60), mod(S.target, 60)]")
    page.mouse.click(*point(page, (hour or 12) / 12 * 2 * math.pi, 0.74))
    if minute:
        page.mouse.move(*point(page, 0, 0.8))
        page.mouse.down()
        for m in range(1, minute + 1):
            page.mouse.move(*point(page, m / 60 * 2 * math.pi, 0.8))
        page.mouse.up()


def build(page: Page) -> None:
    for word in page.evaluate("PHRASES[face(S.target)].map(([w]) => w)"):
        page.click(f'.tray .word[data-word="{word}"]')


def write(page: Page) -> None:
    page.fill("#answer", page.evaluate("PHRASES[face(S.target)].map(([w]) => w).join(' ')"))
    page.press("#answer", "Enter")


def play_round(page: Page, level: int) -> int:
    page.evaluate(f"S.unlocked = {level}; S.level = {level}; renderLevels('#levels')")
    page.click("#go")
    for _ in range(600):
        phase, gate = page.evaluate("[S.phase, S.gate]")
        if phase == "end":
            return int(page.locator("#stars .on").count())
        if phase == "skate":
            skate(page)
        elif phase == "build" and page.locator(".tray .word").count():
            build(page)
        elif phase == "frozen" and page.locator("#answer").count():
            write(page)
        else:
            page.wait_for_timeout(50)
            continue
        page.wait_for_function(f"S.gate !== {gate}", timeout=8000)
    raise AssertionError(f"Level {level} did not end")


@pytest.mark.parametrize("level", LEVELS)
def test_a_round_per_level(chromium: Browser, url: str, level: int) -> None:
    page, errors = open_game(chromium, url)
    assert play_round(page, level) == 3
    assert page.locator("#crash").is_hidden()
    assert errors == []


def test_tapping_an_hour_on_a_tablet(playwright: Playwright, url: str) -> None:
    browser = playwright.webkit.launch()
    page, errors = open_game(browser, url, **playwright.devices["iPad (gen 7)"])
    page.evaluate("S.level = 1; S.unlocked = 1")
    page.click("#go")
    page.wait_for_function("S.phase === 'skate'")
    page.touchscreen.tap(*point(page, 5 / 12 * 2 * math.pi, 0.74))
    assert page.evaluate("mod(S.T, 720)") == 5 * 60
    assert errors == []
    browser.close()


def test_a_crash_is_shown(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    page.evaluate("setTimeout(() => { throw new Error('kapot') })")
    page.wait_for_selector("#crash:not([hidden])")
    assert "kapot" in page.inner_text("#crash-msg")
    assert [str(error) for error in errors] == ["kapot"]


def test_the_parent_report_counts_the_gates(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    play_round(page, 0)
    page.evaluate("report()")
    assert "Hele uren" in page.inner_text("#report")
    assert page.evaluate("store.get('log', []).length") == 10
    assert errors == []


def test_starting_over_clears_everything(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    play_round(page, 0)
    page.evaluate("report()")
    page.once("dialog", accept)
    with page.expect_navigation():
        page.click("#reset")
    page.wait_for_function("PHRASES.length === 720")
    assert page.evaluate("Object.keys(localStorage).filter(k => k.startsWith('ijsbaan.'))") == []
    assert page.evaluate("[S.level, S.unlocked]") == [0, 0]
    assert errors == []


def accept(dialog: Any) -> None:
    dialog.accept()
