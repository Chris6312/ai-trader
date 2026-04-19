from __future__ import annotations

from pathlib import Path
from typing import Any
import pickle


def dump(value: Any, filename: str | Path, compress: int | bool | None = None) -> list[str]:
    path = Path(filename)
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return [str(path)]


def load(filename: str | Path) -> Any:
    path = Path(filename)
    with path.open("rb") as handle:
        return pickle.load(handle)
