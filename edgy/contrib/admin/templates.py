from pathlib import Path

from lilya.templating import Jinja2Template

templates = Jinja2Template(
    directory=str(Path(__file__).resolve().parent / "templates")
)
