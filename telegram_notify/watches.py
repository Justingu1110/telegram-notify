import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_WATCHES_PATH = Path(__file__).resolve().parent.parent / "watches.toml"


@dataclass(frozen=True)
class Watch:
    name: str
    url: str
    parser: str


def load_watches(path=DEFAULT_WATCHES_PATH):
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return [Watch(name=w["name"], url=w["url"], parser=w["parser"]) for w in data["watch"]]
