from typing import Any

from starlette.testclient import TestClient

from server import app

client = TestClient(app)


def post(path: str, body: dict[str, Any]) -> Any:
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_every_minute_has_its_phrase() -> None:
    phrases = client.get("/phrases").json()
    assert len(phrases) == 720
    assert [w for w, role in phrases[8 * 60 + 37]] == ["zeven", "over", "half", "negen"]


def test_misspelled_right_answer() -> None:
    assert post("/read", {"hour": 20, "minute": 40, "text": "tien ovr haf negn"})["verdict"] == "right"


def test_dialogue_for_twenty_past_nine() -> None:
    read = post("/read", {"hour": 20, "minute": 40, "text": "twintug over negen"})
    assert read["verdict"] == "wrong"
    assert [w for w, role in read["said"]] == ["twintig", "over", "negen"]

    first = post("/ask", read["dialogue"])
    assert first["lead"]
    assert first["question"] == "Is de grote wijzer al voorbij het hele uur, of moet hij er nog naartoe?"

    wrong = post("/step", {"dialogue": first["dialogue"], "choice": "al voorbij"})
    assert wrong == {
        "correct": False,
        "hint": "De wijzers draaien rechtsom. Is het hele uur al geweest, of komt hij nog?",
    }
    done = post("/step", {"dialogue": first["dialogue"], "choice": "er nog naartoe"})
    assert done["done"]
    assert [w for w, role in done["right"]] == ["tien", "over", "half", "negen"]


def test_words_that_are_no_time() -> None:
    assert post("/read", {"hour": 20, "minute": 40, "text": "ik weet het niet"})["verdict"] == "unreadable"


def test_building_four_to_nine() -> None:
    clock = {"hour": 20, "minute": 56}
    assert post("/build", clock)["tray"] == [
        ["vier", 4],
        ["acht", 8],
        ["negen", 9],
        ["zesenvijftig", 56],
        ["voor", None],
    ]
    assert (
        post("/place", clock | {"placed": [], "word": "negen"})["hint"]
        == "Het uur komt achteraan. Begin met de minuten."
    )
    assert post("/place", clock | {"placed": ["vier", "voor"], "word": "acht"}) == {
        "role": None,
        "hint": "Bij voor en half noem je het uur dat nog komt.",
        "mistake": "hour",
        "done": False,
    }
    assert post("/place", clock | {"placed": ["vier", "voor"], "word": "negen"}) == {
        "role": "hour",
        "hint": None,
        "mistake": None,
        "done": True,
    }


def test_glued_numerals_are_read() -> None:
    read = post("/read", {"hour": 20, "minute": 56, "text": "4voor8"})
    assert [w for w, role in read["said"]] == ["vier", "voor", "acht"]
