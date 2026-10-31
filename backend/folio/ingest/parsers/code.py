import re
from pathlib import Path

from folio.ingest.parsers.base import Section, read_text

LANGUAGES = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript", ".java": "java", ".kt": "kotlin",
    ".kts": "kotlin", ".scala": "scala", ".go": "go", ".rs": "rust", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".cs": "csharp",
    ".php": "php", ".rb": "ruby", ".swift": "swift", ".m": "objc", ".mm": "objc", ".lua": "lua",
    ".pl": "perl", ".pm": "perl", ".r": "r", ".jl": "julia", ".dart": "dart", ".ex": "elixir",
    ".exs": "elixir", ".erl": "erlang", ".hs": "haskell", ".ml": "ocaml", ".clj": "clojure",
    ".fs": "fsharp", ".vb": "vbnet", ".groovy": "groovy", ".gradle": "groovy", ".sh": "shell",
    ".bash": "shell", ".zsh": "shell", ".fish": "shell", ".ps1": "powershell", ".psm1": "powershell",
    ".bat": "batch", ".cmd": "batch", ".sql": "sql", ".css": "css", ".scss": "scss", ".sass": "sass",
    ".less": "less", ".vue": "vue", ".svelte": "svelte", ".astro": "astro", ".zig": "zig",
    ".nim": "nim", ".v": "verilog", ".sv": "verilog", ".vhd": "vhdl", ".tf": "terraform",
    ".proto": "protobuf", ".graphql": "graphql", ".gql": "graphql", ".cmake": "cmake",
    ".asm": "asm", ".s": "asm", ".sol": "solidity", ".pas": "pascal", ".f90": "fortran",
}
FILENAMES = {"dockerfile": "docker", "makefile": "make", "rakefile": "ruby", "gemfile": "ruby", "jenkinsfile": "groovy"}

_DEFINITION = re.compile(
    r"^\s*(?:export\s+|public\s+|private\s+|protected\s+|static\s+|async\s+|pub(?:\(crate\))?\s+)*"
    r"(?:def|class|function|func|fn|interface|struct|enum|impl|trait|module|type|const\s+\w+\s*=\s*(?:async\s*)?\(|"
    r"CREATE\s+(?:TABLE|VIEW|FUNCTION|PROCEDURE))\b",
    re.IGNORECASE,
)
_NAME = re.compile(r"(?:def|class|function|func|fn|interface|struct|enum|impl|trait|type|const)\s+([\w.$]+)")
BLOCK_CHARS = 2400


def language_for(path: Path) -> str | None:
    return LANGUAGES.get(path.suffix.lower()) or FILENAMES.get(path.name.lower())


def parse_code(path: Path) -> list[Section]:
    language = language_for(path) or ""
    lines = read_text(path).splitlines()
    blocks: list[tuple[str | None, list[str]]] = []
    name: str | None = None
    current: list[str] = []
    size = 0

    def flush() -> None:
        if any(line.strip() for line in current):
            blocks.append((name, current.copy()))
        current.clear()

    for line in lines:
        top_level = _DEFINITION.match(line) and len(line) - len(line.lstrip()) <= 4
        # cortamos en definiciones o en línea vacía solo si el bloque ya es grande
        if current and (top_level or (not line.strip() and size > BLOCK_CHARS)):
            flush()
            size = 0
        if top_level:
            match = _NAME.search(line)
            name = match.group(1) if match else line.strip()[:60]
        current.append(line)
        size += len(line) + 1
    flush()

    sections = []
    for block_name, block in blocks:
        body = "\n".join(block).strip("\n")
        heading = f"{path.name}: {block_name}" if block_name else path.name
        sections.append(Section(f"```{language}\n{body}\n```", heading=heading))
    return sections
