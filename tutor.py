"""The language model's two jobs, on Apple's on-device model: repair the child's spelling, and react to what he wrote.

Repairing spelling is a content transformation, so the speller runs with Apple's permissive guardrails; the default
ones reject harmless misspellings such as "twintug". The questions themselves come from the code word for word: when
the model rephrased them, it changed what they asked.
"""

import apple_fm_sdk as fm
from apple_fm_model import AppleFoundationModel
from pydantic_ai import Agent

__all__ = ["coach", "react", "spell", "speller"]

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

COACH = """\
Je bent een vrolijke schaatsleraar voor een kind van negen dat moeite heeft met klokkijken.
Het kind heeft een tijd opgeschreven die nog niet klopt. Schrijf één korte, warme zin in eenvoudig Nederlands
die zijn antwoord noemt en hem aanmoedigt om samen te kijken. Zeg niet dat het fout is en noem geen andere tijd.
Geen emoji.

Voorbeeld: Je schreef kwart over drie, laten we samen eens goed naar de wijzers kijken!"""

permissive = fm.SystemLanguageModel(guardrails=fm.SystemLanguageModelGuardrails.PERMISSIVE_CONTENT_TRANSFORMATIONS)
speller = Agent(AppleFoundationModel(permissive), instructions=SPELL, model_settings={"temperature": 0})
coach = Agent(
    AppleFoundationModel(fm.SystemLanguageModel()),
    instructions=COACH,
    model_settings={"temperature": 0.4, "max_tokens": 120},
)


async def spell(text: str) -> str:
    return (await speller.run(text)).output.strip()


async def react(said: str) -> str:
    return (await coach.run(f"Het kind schreef: {said}")).output.strip()
