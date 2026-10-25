# IJsbaan-klok

Klokkijken als schaatsspel. Sleep de grote wijzer naar de goede tijd. Bij een bevroren poort schrijf je de tijd op, en Apple's on-device model leest je spelling. De tijdlogica zit in `klok.py`; het model rekent nooit.

```bash
uv sync
uv run python server.py
```

Open daarna http://localhost:8740.

Het spel heeft [fm-pydantic-ai](https://github.com/mattijn/fm-pydantic-ai) nodig in `../fm-pydantic-ai`.

```bash
uv run --group dev ruff check . && uv run --group dev ruff format --check . && uv run --group dev mypy && uv run --group dev pytest
uv run python -m evals.spelling
```
