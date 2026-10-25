# IJsbaan-klok

Klokkijken als schaatsspel. Tik het uur en draai de grote wijzer naar de goede tijd. Bij een bevroren poort schrijf je de tijd op, en Apple's on-device model leest je spelling. Bij een bouwpoort tik je de tijd met woordblokjes bij elkaar, en een fout blokje krijgt de regel die het breekt. De tijdlogica zit in `klok.py`; het model rekent nooit.

```bash
uv sync
uv run python server.py
```

Open daarna http://localhost:8740.

Het model loopt via [fm-pydantic-ai](https://github.com/mattijn/fm-pydantic-ai), dat `uv sync` van GitHub haalt.

De browsertests in `tests/test_play.py` spelen per niveau een ronde in Chromium en tikken op een iPad in WebKit:

```bash
uv run playwright install chromium webkit
uv run --group dev ruff check . && uv run --group dev ruff format --check . && uv run --group dev mypy && uv run --group dev pytest
uv run python -m evals.spelling
```
