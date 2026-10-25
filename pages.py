"""Build the school version into `_site`: the same page with the rules running in the browser and its share image, for GitHub Pages."""

import shutil
from pathlib import Path

ROOT = Path(__file__).parent
SITE = ROOT / "_site"
SERVER = '<meta name="engine" content="server">'


def main() -> None:
    page = (ROOT / "static" / "index.html").read_text()
    if page.count(SERVER) != 1:
        raise ValueError(f"index.html should hold {SERVER} once")
    shutil.rmtree(SITE, ignore_errors=True)
    SITE.mkdir()
    (SITE / "index.html").write_text(page.replace(SERVER, '<meta name="engine" content="browser">'))
    for module in ["klok.py", "play.py"]:
        shutil.copy(ROOT / module, SITE / module)
    shutil.copy(ROOT / "static" / "og.jpg", SITE / "og.jpg")


if __name__ == "__main__":
    main()
