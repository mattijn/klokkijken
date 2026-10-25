"""The language model's job, on Apple's on-device model: repair the child's spelling.

Repairing spelling is a content transformation, so the speller runs with Apple's permissive guardrails; the default
ones reject harmless misspellings such as "twintug". The questions themselves come from the code word for word: when
the model rephrased them, it changed what they asked.
"""

import apple_fm_sdk as fm
from apple_fm_model import AppleFoundationModel
from pydantic_ai import Agent

__all__ = ["spell", "speller"]

SPELL = """\
Je verbetert de spelling van een kind dat een kloktijd opschrijft.
Schrijf dezelfde woorden terug, goed gespeld, in kleine letters. Cijfers schrijf je als woord.
Verander nooit de tijd, ook niet als die fout is. Voeg geen woorden toe en laat er geen weg.

Voorbeelden:
twintug ovr negn -> twintig over negen
haf aght -> half acht
tin voor haf 9 -> tien voor half negen
dreeentwintug over fier -> drieëntwintig over vier
elluf uur -> elf uur
kwrt voor twalf -> kwart voor twaalf"""

permissive = fm.SystemLanguageModel(guardrails=fm.SystemLanguageModelGuardrails.PERMISSIVE_CONTENT_TRANSFORMATIONS)
speller = Agent(AppleFoundationModel(permissive), instructions=SPELL, model_settings={"temperature": 0})


async def spell(text: str) -> str:
    return (await speller.run(text)).output.strip()
