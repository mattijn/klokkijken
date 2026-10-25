"""Play whole rounds in a real browser: tap the hour, turn the big hand, build sentences and write at frozen gates.

The writing uses digits and correctly spelled words, which the rules read without the speller.
"""

import functools
import http.server
import math
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
import uvicorn
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

import pages
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
    page.wait_for_function("PHRASES.length === 720")
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
        page.click(f'.tray .word[data-word="{word}"]:not([hidden])')


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


def test_a_right_time_bursts_the_rink_before_the_next(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 0)
    skate(page)
    page.wait_for_function("blast !== null")
    assert page.evaluate("S.phase") == "between"
    page.wait_for_function("S.phase === 'skate' && blast === null")
    assert errors == []


def test_back_to_the_levels_mid_round(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 2)
    page.evaluate("S.gate = 4; nextGate()")
    page.wait_for_selector("#answer")
    page.click("#t-menu")
    assert page.locator("#start").is_visible()
    assert page.locator("#panel").is_hidden()
    assert page.evaluate("[S.phase, frost.goal]") == ["start", 0]
    page.click("#levels .lv[data-level='0']")
    page.click("#go")
    page.wait_for_function("S.phase === 'skate'")
    assert page.inner_text("#level") == "HELE UREN"
    assert errors == []


def test_whole_hours_turn_in_quarters(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 0)
    page.evaluate("S.T = S.P = 3 * 60; S.target = 7 * 60; renderTarget()")
    page.mouse.move(*point(page, 0, 0.8))
    page.mouse.down()
    for m in range(1, 18):
        page.mouse.move(*point(page, m / 60 * 2 * math.pi, 0.8))
    page.mouse.up()
    assert page.evaluate("mod(S.T, 60)") == 15
    page.click("#t-menu")
    start_level(page, 2)
    page.evaluate("S.T = S.P = 3 * 60; S.target = 7 * 60 + 45; renderTarget()")
    page.mouse.move(*point(page, 0, 0.8))
    page.mouse.down()
    for m in range(1, 8):
        page.mouse.move(*point(page, m / 60 * 2 * math.pi, 0.8))
    page.wait_for_timeout(100)
    assert page.evaluate("[dragging, !!LEVELS[S.level].loupe, !!LEVELS[3].loupe]") == ["minute", False, True]
    page.mouse.up()
    assert errors == []


def test_arrow_keys_turn_the_hands(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 4)
    page.evaluate("S.T = S.P = 9 * 60 + 40; S.target = 9 * 60 + 47; renderTarget()")
    for _ in range(3):
        page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowLeft")
    assert page.evaluate("S.T") == 9 * 60 + 42
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowDown")
    assert page.evaluate("S.T") == 10 * 60 + 42
    page.keyboard.press("ArrowDown")
    for _ in range(5):
        page.keyboard.press("ArrowRight")
    page.wait_for_function("S.gate === 1")
    assert errors == []


def test_a_level_party_before_the_stars(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 2)
    page.evaluate("S.firstTry = 4; S.gate = S.gates; endRun()")
    assert page.evaluate("[S.phase, party.level]") == ["party", 2]
    assert page.locator("#end").is_hidden()
    page.wait_for_function("S.phase === 'end' && party === null")
    assert page.locator("#end").is_visible()
    page.click("#again")
    page.evaluate("S.firstTry = 4; S.gate = S.gates; endRun()")
    page.click("#t-menu")
    page.wait_for_timeout(1500)
    assert page.locator("#end").is_hidden()
    assert errors == []


def test_taking_back_a_block(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 2)
    page.evaluate("S.gate = 2; nextGate()")
    page.wait_for_selector(".tray .word")
    first = page.evaluate("PHRASES[face(S.target)][0][0]")
    page.click(f'.tray .word[data-word="{first}"]')
    page.wait_for_function("S.placed.length === 1")
    page.click("#back")
    assert page.evaluate("S.placed") == []
    assert page.locator("#built .tile").count() == 0
    build(page)
    page.wait_for_function("S.gate === 3")
    assert page.evaluate("store.get('log').at(-1).first")
    assert errors == []


def test_a_new_level_is_chosen_and_started(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    assert play_round(page, 0) == 3
    assert page.evaluate("[S.unlocked, S.level]") == [1, 1]
    assert page.inner_text("#again") == "Naar Half!"
    page.click("#levels-end .lv[data-level='0']")
    assert page.inner_text("#again") == "Nog een rondje"
    page.click("#levels-end .lv[data-level='1']")
    page.keyboard.press("Enter")
    page.wait_for_function("S.phase === 'skate'")
    assert page.inner_text("#level") == "HALF"
    assert errors == []


def test_sound_that_will_not_start_keeps_the_game_going(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    page.evaluate("""audio(); A.ctx.suspend();
      A.ctx.resume = () => Promise.reject(new DOMException('Failed to start the audio device', 'InvalidStateError'));
      true""")
    page.wait_for_function("A.ctx.state === 'suspended'")
    page.evaluate("audio()")
    page.wait_for_timeout(200)
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


def test_closing_the_keyboard_on_a_tablet_is_no_samen(playwright: Playwright, url: str) -> None:
    browser = playwright.webkit.launch()
    page, errors = open_game(browser, url, **playwright.devices["iPad (gen 7)"])
    page.evaluate("S.level = 2; S.unlocked = 2")
    page.click("#go")
    page.wait_for_function("S.phase === 'skate'")
    page.evaluate("S.gate = 4; nextGate()")
    page.wait_for_selector("#answer")
    page.fill("#answer", "half")
    page.tap("#samen-write")
    assert page.evaluate("[S.together, document.activeElement.id, $('#answer').value]") == [False, "", "half"]
    page.tap("#samen-write")
    page.wait_for_function("S.together")
    assert errors == []
    browser.close()


def test_a_tap_beside_the_answer_closes_the_keyboard(playwright: Playwright, url: str) -> None:
    browser = playwright.webkit.launch()
    page, errors = open_game(browser, url, **playwright.devices["iPad (gen 7)"])
    page.evaluate("S.level = 2; S.unlocked = 2")
    page.click("#go")
    page.wait_for_function("S.phase === 'skate'")
    page.evaluate("S.gate = 4; nextGate()")
    page.wait_for_selector("#answer")
    page.fill("#answer", "half")
    page.touchscreen.tap(*point(page, 0, 0))
    assert page.evaluate("[document.activeElement.id, $('#answer').value, S.together]") == ["", "half", False]
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
    assert "Hele uren" in str(page.text_content("#report"))
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
    assert page.evaluate("Object.keys(localStorage).sort()") == ["ijsbaan.calm"]
    assert page.evaluate("[S.level, S.unlocked]") == [0, 0]
    assert errors == []


def start_level(page: Page, level: int) -> None:
    page.evaluate(f"S.unlocked = {level}; S.level = {level}; renderLevels('#levels')")
    page.click("#go")
    page.wait_for_function("S.phase === 'skate'")


def tap_number(page: Page, n: int) -> None:
    page.mouse.click(*point(page, n / 12 * 2 * math.pi, 0.74))


def test_half_by_tapping_the_hour_then_the_six(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 1)
    page.evaluate("S.target = 8 * 60 + 30; renderTarget()")
    tap_number(page, 8)
    assert "Nu de grote wijzer" in page.inner_text("#live")
    tap_number(page, 6)
    page.wait_for_function("S.gate === 1")
    assert errors == []


def test_the_half_level_turns_in_quarters(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 1)
    page.evaluate("S.T = S.P = 11 * 60; S.target = 5 * 60 + 30; renderTarget()")
    page.mouse.move(*point(page, 0, 0.8))
    page.mouse.down()
    for m in range(1, 21):
        page.mouse.move(*point(page, m / 60 * 2 * math.pi, 0.8))
    page.mouse.up()
    assert page.evaluate("mod(S.T, 60)") == 15
    assert page.inner_text("#live .blocks").split() == ["kwart", "over", "elf"]
    assert errors == []


def test_a_wrong_hour_keeps_taps_on_the_hour(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 1)
    page.evaluate("S.target = 8 * 60 + 30; renderTarget()")
    tap_number(page, 9)
    tap_number(page, 6)
    assert page.evaluate("face(S.T)") == 6 * 60
    assert errors == []


def test_skating_together_then_alone(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 2)
    page.evaluate("S.offer = true; renderLive()")
    back = page.evaluate("S.T")
    page.click("#samen")
    page.wait_for_function("coach !== null && face(S.T) === face(S.target)", timeout=8000)
    page.wait_for_function("coach === null", timeout=12000)
    assert page.evaluate("[S.T, S.gate]") == [back, 0]
    assert "Nu jij!" in page.inner_text("#live")
    skate(page)
    page.wait_for_function("S.gate === 1")
    entry = page.evaluate("store.get('log').at(-1)")
    assert (entry["together"], entry["first"]) == (True, False)
    assert page.evaluate("S.again.map(a => a.gate)") == [2]
    assert errors == []


def test_writing_nothing_builds_it_together(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 4)
    page.evaluate("S.gate = 4; S.T = 15 * 60; nextGate()")
    page.wait_for_selector("#answer")
    page.evaluate("S.target = 18 * 60 + 37")
    page.press("#answer", "Enter")
    assert page.inner_text("#panel .ask") == "Schrijf eerst de tijd."
    page.click("#samen-write")
    page.click(".choices .btn:text-is('6')")
    page.wait_for_selector(".tray .word")
    assert "zeven over half zeven" in page.inner_text(".ghost-line").replace("\n", " ")
    build(page)
    page.wait_for_function("S.gate === 5")
    entry = page.evaluate("store.get('log').at(-1)")
    assert (entry["kind"], entry["together"], entry["first"]) == ("frozen", True, False)
    assert page.evaluate("[S.again.length, S.gates]") == [1, 10]
    assert errors == []


def test_the_report_names_one_thing_to_work_on(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    page.evaluate("""store.set('log', [0, 1, 2].map(i => ({at: Date.now(), level: 3, kind: 'frozen', first: false, together: false,
      slips: ['hour'], target: 'vier voor negen', right: 'vier voor negen',
      example: {mistake: 'hour', how: 'geschreven', what: 'vier voor acht'}})))""")
    page.evaluate("report()")
    text = page.inner_text("#report")
    assert "Dit gaat nog vaak mis" in text
    assert "✗\nvier voor acht\n✓\nvier voor negen" in text
    assert "Welk uur komt eraan?" in text
    assert page.evaluate("focus()") == "hour"
    assert errors == []


def add_player(page: Page, name: str) -> None:
    page.fill("#name", name)
    page.press("#name", "Enter")


def test_each_name_keeps_its_own_level(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    page.evaluate("store.set('unlocked', 2); store.set('level', 2)")
    add_player(page, "Sam")
    assert page.evaluate("[store.player, S.unlocked]") == ["Sam", 2]
    add_player(page, "Noor")
    assert page.evaluate("[store.player, S.unlocked, S.level]") == ["Noor", 0, 0]
    page.click("#players button.lv:text-is('Sam')")
    assert page.evaluate("[S.unlocked, S.level]") == [2, 2]
    page.reload()
    page.wait_for_function("PHRASES.length === 720")
    assert page.evaluate("[store.player, S.unlocked, store.get('players', [])]") == ["Sam", 2, ["Sam", "Noor"]]
    assert page.evaluate("localStorage.getItem('ijsbaan.unlocked')") is None
    assert errors == []


def test_removing_a_name(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    add_player(page, "Sam")
    page.evaluate("report()")
    assert page.inner_text("#parents-title") == "Hoe gaat het klokkijken bij Sam?"
    page.once("dialog", accept)
    with page.expect_navigation():
        page.click("#forget")
    page.wait_for_function("PHRASES.length === 720")
    assert page.evaluate("[store.player, store.get('players', [])]") == ["", []]
    assert errors == []


@pytest.fixture(scope="module")
def site() -> Iterator[str]:
    """The school version, built and served as plain files, with the rules running in the browser."""
    pages.main()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(pages.SITE))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_the_school_version_plays_without_a_server(chromium: Browser, site: str) -> None:
    page, errors = open_game(chromium, site)
    assert page.evaluate("ENGINE") == "browser"
    assert play_round(page, 3) == 3
    assert page.evaluate("api('/read', {hour: 20, minute: 56, text: 'fier foor neegen'})")["verdict"] == "right"
    assert errors == []


def accept(dialog: Any) -> None:
    dialog.accept()


def end_level(page: Page, level: int, first: int, helped: bool) -> None:
    start_level(page, level)
    page.evaluate(f"""S.firstTry = {first}; S.helped = {str(helped).lower()}; S.marks = [true, true, false, true].map(f => ({{kind: 'build', first: f}}));
      S.gate = S.gates; endRun(); true""")
    page.wait_for_function("S.phase === 'end'")


def test_samen_doen_keeps_the_third_star(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    end_level(page, 1, first=4, helped=True)
    assert page.locator("#stars .on").count() == 2
    assert page.inner_text("#goal") == "★★★ = alles zelf, zonder Samen doen"
    assert page.locator("#gates .yes").count() == 3
    assert page.evaluate("store.get('stars')") == [None, 2]
    page.evaluate("stopRun()")
    assert page.inner_text("#levels .lv[data-level='1'] i") == "★★★"
    assert page.locator("#levels .lv[data-level='1'] i em").inner_text() == "★"
    assert errors == []


def test_all_gold_is_a_champion(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    page.evaluate("store.set('stars', [3, 3, 3, 3, 2]); store.set('unlocked', 4)")
    page.reload()
    page.wait_for_function("PHRASES.length === 720")
    assert page.locator("#levels .cup").is_disabled()
    start_level(page, 4)
    page.evaluate("""S.firstTry = 4; S.helped = false; S.marks = [true, true, true, true].map(f => ({kind: 'build', first: f}));
      S.gate = S.gates; endRun(); true""")
    assert page.evaluate("[S.phase, party.champion, party.dur]") == ["party", True, 24000]
    page.wait_for_timeout(2000)
    assert page.evaluate("S.phase") == "party"
    page.click("#skip")
    page.wait_for_function("S.phase === 'end'")
    assert page.inner_text("#end-title") == "Kampioen!"
    assert page.inner_text("#goal") == "Alle niveaus goud!"
    page.click("#levels-end .cup")
    assert page.evaluate("[S.phase, party.champion]") == ["party", True]
    page.click("#skip")
    page.wait_for_function("S.phase === 'end'")
    assert page.locator("#end").is_visible()
    page.evaluate("stopRun()")
    page.click("#levels .cup")
    page.click("#skip")
    page.wait_for_function("S.phase === 'start'")
    assert page.locator("#start").is_visible()
    assert errors == []


def test_tapping_the_rim_skates_the_big_hand_there(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 2)
    page.evaluate("S.target = 7 * 60 + 45; renderTarget(); S.P = 3 * 60; setT(false)")
    page.mouse.click(*point(page, 44 / 60 * 2 * math.pi, 0.93))
    page.wait_for_function("S.T > 3 * 60 && S.T < 3 * 60 + 45")
    page.wait_for_function("S.T === 3 * 60 + 45 && S.glide === null")
    page.mouse.move(*point(page, 45 / 60 * 2 * math.pi, 0.93))
    page.mouse.down()
    for m in range(46, 61):
        page.mouse.move(*point(page, m / 60 * 2 * math.pi, 0.93))
    page.mouse.up()
    assert page.evaluate("S.T") == 4 * 60
    assert errors == []


def test_the_round_trail_follows_the_gates(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 2)
    skate(page)
    page.wait_for_function("S.gate === 1")
    page.wait_for_function("lap.u === 1")
    assert page.evaluate("S.results") == ["first"]
    assert page.get_attribute("#run", "aria-label") == "Poort 2 van 10"
    assert errors == []


def test_a_tap_just_off_a_number_is_the_rim(chromium: Browser, url: str) -> None:
    page, errors = open_game(chromium, url)
    start_level(page, 2)

    def kind(minute: int, radius: float) -> list[Any]:
        x, y = point(page, minute / 60 * 2 * math.pi, radius)
        return list(page.evaluate(f"(z => [z.kind, z.n])(zone({{clientX: {x}, clientY: {y}, pointerType: 'touch'}}))"))

    page.evaluate("S.T = 7 * 60; S.P = S.T; S.disp = S.T")
    assert kind(15, 0.74) == ["hour", 3]
    assert kind(17, 0.8) == ["ring", None]
    assert kind(45, 0.83)[0] == "hour"
    assert kind(43, 0.88) == ["ring", None]
    assert errors == []
