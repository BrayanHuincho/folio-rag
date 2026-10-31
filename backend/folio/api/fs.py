from __future__ import annotations

import os
import string
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/fs", tags=["fs"])


def _drives() -> list[dict]:
    drives = [f"{letter}:\\" for letter in string.ascii_uppercase]
    return [{"name": d, "path": d} for d in drives if os.path.exists(d)]


@router.get("/browse")
def browse(path: str = "") -> dict:
    if not path:
        if os.name == "nt":
            return {"path": "", "parent": None, "dirs": _drives()}
        path = str(Path.home())

    target = Path(path).expanduser().resolve()
    if not target.is_dir():
        raise HTTPException(404, f"No es una carpeta: {path}")

    dirs = []
    try:
        for entry in os.scandir(target):
            try:
                if entry.is_dir() and not entry.name.startswith((".", "$")):
                    dirs.append({"name": entry.name, "path": entry.path})
            except OSError:
                continue
    except PermissionError:
        raise HTTPException(403, f"Sin permiso para abrir: {target}")

    if target.parent != target:
        parent = str(target.parent)
    else:
        parent = "" if os.name == "nt" else None
    return {
        "path": str(target),
        "parent": parent,
        "dirs": sorted(dirs, key=lambda d: d["name"].lower()),
    }
