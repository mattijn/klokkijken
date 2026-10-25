"""How well a speller reads a child's misspelled times: uv run python -m evals.spelling [model|rules]

A case passes when the repaired words parse to the same time words as the intended ones; a wrong time the child
wrote must stay wrong.
"""

import asyncio
import sys
import time

from klok import parse
from play import Speller, by_rules

__all__ = ["CASES", "main"]

CASES = [
    ("twintug over negen", "twintig over negen"),
    ("zeve ovr half nege", "zeven over half negen"),
    ("tin voor haf 9", "tien voor half negen"),
    ("half aght", "half acht"),
    ("kwartf voor tien", "kwart voor tien"),
    ("twintig over twintig", "twintig over twintig"),
    ("10 over half 9", "tien over half negen"),
    ("elluf uur", "elf uur"),
    ("zeefenderdig over acht", "zevenendertig over acht"),
    ("fijf voor haf drie", "vijf voor half drie"),
    ("kwrt ovr twalf", "kwart over twaalf"),
    ("haf een", "half één"),
    ("dreeentwintig over 4", "drieëntwintig over vier"),
    ("negun uur", "negen uur"),
    ("veir over haf zes", "vier over half zes"),
    ("achtienn voor zeven", "achttien voor zeven"),
    ("zefe over haf aht", "zeven over half acht"),
    ("twinug foor neegen", "twintig voor negen"),
    ("tien ofer haaf nehen", "tien over half negen"),
    ("drie foor half twee", "drie voor half twee"),
    ("kwart oevr ses", "kwart over zes"),
    ("haalf tien", "half tien"),
    ("vuif over tien", "vijf over tien"),
    ("twaalf uhr", "twaalf uur"),
    ("acht over half twintig", "acht over half twintig"),
    ("4 voor 8", "vier voor acht"),
    ("eenetwintig over 8", "eenentwintig over acht"),
    ("ses voor haf elf", "zes voor half elf"),
    ("negn over haf tie", "negen over half tien"),
    ("kwart foor drie", "kwart voor drie"),
    ("4voor8", "vier voor acht"),
    ("4vor8", "vier voor acht"),
    ("acht voor vier", "acht voor vier"),
    ("vier voor 8 uur", "vier voor acht"),
    ("10ovr haf 3", "tien over half drie"),
]


async def main(spell: Speller) -> None:
    passed = 0
    for text, intended in CASES:
        start = time.perf_counter()
        repaired = await spell(text)
        ok = parse(repaired) == parse(intended)
        passed += ok
        print(f"{'ok ' if ok else 'XX '}{time.perf_counter() - start:4.1f}s  {text!r:28} -> {repaired!r}")
    print(f"\n{passed}/{len(CASES)} read as meant")


if __name__ == "__main__":
    if sys.argv[1:] == ["rules"]:
        asyncio.run(main(by_rules))
    else:
        from tutor import spell

        asyncio.run(main(spell))
