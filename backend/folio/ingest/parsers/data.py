import json
from pathlib import Path

from folio.ingest.parsers.base import ParseError, Section, clean, read_text

GROUP_CHARS = 2400


def _grouped(lines: list[str], heading: str | None = None) -> list[Section]:
    sections: list[Section] = []
    group: list[str] = []
    size = 0
    for line in lines:
        if group and size + len(line) > GROUP_CHARS:
            sections.append(Section("\n".join(group), heading=heading))
            group, size = [], 0
        group.append(line)
        size += len(line) + 1
    if group:
        sections.append(Section("\n".join(group), heading=heading))
    return sections


def _flatten(value: object, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            lines.extend(_flatten(item, f"{prefix}.{key}" if prefix else str(key)))
        return lines
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return [f"{prefix}: {', '.join(map(str, value))}"]
        lines = []
        for index, item in enumerate(value):
            lines.extend(_flatten(item, f"{prefix}[{index}]"))
        return lines
    return [f"{prefix}: {value}" if prefix else str(value)]


def parse_json(path: Path) -> list[Section]:
    text = read_text(path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc}") from exc
    return _grouped(_flatten(data))


def parse_jsonl(path: Path) -> list[Section]:
    lines = []
    for number, line in enumerate(read_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            lines.append(line)
            continue
        lines.append(f"[{number}] " + "; ".join(_flatten(record)))
    return _grouped(lines)


def parse_yaml(path: Path) -> list[Section]:
    import yaml

    try:
        documents = list(yaml.safe_load_all(read_text(path)))
    except yaml.YAMLError:
        return _plain(path)
    lines = []
    for document in documents:
        if document is not None:
            lines.extend(_flatten(document))
    return _grouped(lines)


def parse_toml(path: Path) -> list[Section]:
    import tomllib

    try:
        data = tomllib.loads(read_text(path))
    except tomllib.TOMLDecodeError:
        return _plain(path)
    return _grouped(_flatten(data))


def parse_ini(path: Path) -> list[Section]:
    import configparser

    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read_string(read_text(path))
    except configparser.Error:
        return _plain(path)
    sections = []
    for name in parser.sections():
        lines = [f"{key} = {value}" for key, value in parser.items(name, raw=True)]
        sections.extend(_grouped([f"[{name}]", *lines], heading=name))
    return sections or _plain(path)


def parse_ipynb(path: Path) -> list[Section]:
    try:
        notebook = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid notebook: {exc}") from exc
    sections: list[Section] = []
    heading: str | None = None
    for cell in notebook.get("cells", []):
        source = cell.get("source", "")
        source = "".join(source) if isinstance(source, list) else source
        if not source.strip():
            continue
        if cell.get("cell_type") == "markdown":
            first = source.strip().splitlines()[0]
            if first.startswith("#"):
                heading = first.lstrip("#").strip()
            sections.append(Section(clean(source), heading=heading))
        else:
            sections.append(Section(f"```\n{source.strip()}\n```", heading=heading))
    return sections


def _plain(path: Path) -> list[Section]:
    text = clean(read_text(path))
    return [Section(text)] if text else []
