# IJsbaan-klok

Klokkijken als schaatsspel. Tik het uur en draai de grote wijzer naar de goede tijd. Bij een bevroren poort schrijf je de tijd op; spelling maakt niet uit. Bij een bouwpoort tik je de tijd met woordblokjes bij elkaar, en een fout blokje krijgt de regel die het breekt. Wie vastzit, doet het samen; die tijd komt later terug om zelf te doen. Twee sterren (de helft van de schrijf- en bouwpoorten in één keer goed) openen het volgende niveau, drie sterren is alles in één keer en nergens samen gedaan. De volglijn op het beginscherm kleurt per niveau brons, zilver of goud; alles goud is kampioen. De tijdlogica zit in `klok.py`, de vragen en antwoorden in `play.py`.

## Op school

https://mattijn.github.io/klokkijken/ draait zonder server en zonder installatie, ook op Windows. Python draait in de browser via [Pyodide](https://pyodide.org), en de spelling wordt gelezen met regels (`klok.repair`). Elke speler kiest een naam; namen en voortgang blijven in de browser van die computer. De site wordt bij elke push naar `main` gebouwd met `pages.py`.

## Op een Mac

Hier leest Apple's on-device model de spelling, via [fm-pydantic-ai](https://github.com/mattijn/fm-pydantic-ai), dat `uv sync` van GitHub haalt.

```bash
uv sync
uv run python server.py
```

Open daarna http://localhost:8740.

## Testen

De browsertests in `tests/test_play.py` spelen per niveau een ronde in Chromium, tikken op een iPad in WebKit en spelen de schoolversie zonder server:

```bash
uv run playwright install chromium webkit
uv run --group dev ruff check . && uv run --group dev ruff format --check . && uv run --group dev mypy && uv run --group dev pytest
uv run python -m evals.spelling model
uv run python -m evals.spelling rules
```
