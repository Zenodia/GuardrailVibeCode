"""Shared loaders for the governance contract.

Stdlib only (Python >= 3.11 for tomllib) so the guards run before the
workspace is installed and cannot be broken by a dependency change made
by the very task they are checking. tiktoken is used when present for
token counts; the fallback over-estimates on purpose, because an
under-estimate is what lets an oversized packet through.
"""

from __future__ import annotations

import ast
import hashlib
import math
import re
import subprocess
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REQ_ID = re.compile(r"^REQ-[A-Z]+-\d{3}$")
TASK_ID = re.compile(r"^(TASK-\d{4}|RT-\d{2})$")
CON_ID = re.compile(r"\*\*(CON-\d{2})\b")
LEVELS = {"MUST", "SHOULD", "PREFER"}
STATUSES = {"draft", "approved", "deprecated", "superseded"}
TASK_KINDS = {"fix", "feature", "refactor", "test"}
# Status is the contract's lifecycle only. Whether a task is claimed or
# delivered is read from git (branch exists / Task trailer on main), so
# there is no hand-edited state that can drift between developers.
TASK_STATUSES = {"draft", "ready", "retired"}
BRANCH_PREFIX = "task/"
UNSET = "UNSET"


class ContractError(Exception):
    """A contract file is malformed. Never caught to "keep going"."""


def _git_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if out.returncode == 0 and out.stdout.strip():
        return Path(out.stdout.strip())
    return Path(__file__).resolve().parents[2]


ROOT = _git_root()


def git(*args: str, check: bool = True) -> str:
    out = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
    )
    if check and out.returncode != 0:
        raise ContractError(f"git {' '.join(args)}: {out.stderr.strip()}")
    return out.stdout


def load_toml(path: Path) -> dict:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ContractError(f"{path}: {exc}") from exc


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- tokens


@lru_cache(maxsize=1)
def budgets() -> dict:
    return load_toml(ROOT / "governance" / "budgets.toml")


def profile(name: str | None = None) -> dict:
    b = budgets()
    name = name or b["active_profile"]
    try:
        return {"name": name, **b["profiles"][name]}
    except KeyError as exc:
        raise ContractError(f"unknown budget profile {name!r}") from exc


@lru_cache(maxsize=1)
def _encoder():
    try:
        import tiktoken  # type: ignore[import-not-found]

        return tiktoken.get_encoding(budgets()["tokenizer"]["name"])
    except Exception:  # noqa: BLE001 - absence is the expected case
        return None


def count_tokens(text: str) -> int:
    enc = _encoder()
    if enc is not None:
        return len(enc.encode(text))
    cpt = float(budgets()["tokenizer"]["chars_per_token_fallback"])
    return math.ceil(len(text) / cpt)


def token_counter_name() -> str:
    return "tiktoken" if _encoder() is not None else "chars-fallback"


# ---------------------------------------------------------- requirements


@dataclass(frozen=True)
class Requirement:
    id: str
    version: int
    status: str
    level: str
    principle: tuple[str, ...]
    text: str
    verify: str
    source: str
    file: str
    superseded_by: str | None = None

    @property
    def hash(self) -> str:
        return req_hash(self)

    @property
    def binding(self) -> bool:
        return self.level in {"MUST", "SHOULD"}


def normalize(text: str) -> str:
    # Whitespace-insensitive so re-wrapping a paragraph does not stale
    # every task; any word change does.
    return " ".join(text.split())


def req_hash(req: Requirement) -> str:
    payload = f"{req.id}\n{req.version}\n{req.level}\n{normalize(req.text)}"
    return sha256_text(payload)


@lru_cache(maxsize=1)
def requirements() -> dict[str, Requirement]:
    found: dict[str, Requirement] = {}
    for path in sorted((ROOT / "specs" / "requirements").glob("*.toml")):
        for raw in load_toml(path).get("requirement", []):
            missing = {"id", "version", "status", "level", "principle",
                       "text", "verify", "source"} - raw.keys()
            if missing:
                raise ContractError(f"{path}: {raw.get('id')} missing "
                                    f"{sorted(missing)}")
            req = Requirement(
                id=raw["id"], version=int(raw["version"]),
                status=raw["status"], level=raw["level"],
                principle=tuple(raw["principle"]), text=raw["text"].strip(),
                verify=raw["verify"], source=raw["source"],
                file=str(path.relative_to(ROOT)),
                superseded_by=raw.get("superseded_by"),
            )
            if req.id in found:
                raise ContractError(f"duplicate {req.id} in {path} and "
                                    f"{found[req.id].file}")
            found[req.id] = req
    return found


# ------------------------------------------------------------ constitution

CORE_RE = re.compile(r"<!-- CORE:BEGIN -->\n(.*?)<!-- CORE:END -->", re.S)


def constitution_core() -> str:
    text = (ROOT / "governance" / "CONSTITUTION.md").read_text("utf-8")
    m = CORE_RE.search(text)
    if not m:
        raise ContractError("CONSTITUTION.md has no CORE block")
    return m.group(1).strip()


def principle_ids() -> set[str]:
    text = (ROOT / "governance" / "CONSTITUTION.md").read_text("utf-8")
    return set(CON_ID.findall(text))


# ------------------------------------------------------------- boundaries


@lru_cache(maxsize=1)
def boundaries() -> dict:
    return load_toml(ROOT / "specs" / "boundaries.toml")


def protected_globs() -> list[str]:
    p = boundaries()["protected"]
    return [*p["always"], *p["reference_data"], *p["canonical_config"]]


# ------------------------------------------------------------------ tasks


def task_files() -> list[Path]:
    return sorted(
        p for p in (ROOT / "tasks").rglob("*.toml")
        if "TEMPLATE" not in p.name
    )


def load_task(task_id: str) -> tuple[dict, Path]:
    for path in task_files():
        data = load_toml(path)
        if data.get("id") == task_id:
            return data, path
    raise ContractError(f"task {task_id} not found under tasks/")


def task_sha(path: Path) -> str:
    return sha256_text(path.read_text("utf-8"))


def feature_file(feature: str) -> Path | None:
    hits = sorted((ROOT / "specs" / "features").glob(f"{feature}-*.md"))
    return hits[0] if hits else None


def feature_hash(feature: str) -> str | None:
    path = feature_file(feature)
    return sha256_text(path.read_text("utf-8")) if path else None


# -------------------------------------------------------- git-derived state


def main_ref() -> str:
    for ref in ("origin/main", "main"):
        if git("rev-parse", "--verify", "--quiet", ref,
               check=False).strip():
            return ref
    raise ContractError("no main or origin/main ref")


@lru_cache(maxsize=1)
def merged_tasks() -> frozenset[str]:
    """Task IDs delivered to main, read from `Task:` commit trailers."""
    log = git("log", main_ref(), "--format=%(trailers:key=Task,valueonly)",
              check=False)
    return frozenset(t.strip() for t in log.split() if TASK_ID.match(t.strip()))


def task_branch(task_id: str) -> str:
    return f"{BRANCH_PREFIX}{task_id}"


def scopes_overlap(a: list[str], b: list[str]) -> list[tuple[str, str]]:
    # Compare the literal prefix before the first wildcard. Exact files
    # compare exactly; a directory glob overlaps anything beneath it. It
    # can over-report (that is safe: the fix is a depends_on), never
    # under-report.
    def prefix(g: str) -> str:
        return g.split("*", 1)[0].split("?", 1)[0]

    return [(x, y) for x in a for y in b
            if prefix(x).startswith(prefix(y))
            or prefix(y).startswith(prefix(x))]


# ------------------------------------------------------------------ globs


@lru_cache(maxsize=512)
def _glob_re(pattern: str) -> re.Pattern[str]:
    # `**` spans directories, `*` and `?` do not. fnmatch would let
    # `packages/*/examples/**` match across package boundaries, which
    # widens a worker's scope silently.
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(path: str, patterns: list[str]) -> bool:
    path = path.replace("\\", "/")
    return any(_glob_re(p).match(path) for p in patterns)


# --------------------------------------------------------- source excerpts


def symbol_span(path: Path, symbol: str) -> tuple[int, int]:
    """1-based inclusive line span of a top-level or Class.method symbol,
    decorators included."""
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    parts = symbol.split(".")
    body = tree.body
    node = None
    for part in parts:
        node = next(
            (n for n in body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)) and n.name == part),
            None,
        )
        if node is None:
            raise ContractError(f"{path}: symbol {symbol!r} not found")
        body = getattr(node, "body", [])
    assert node is not None
    start = min([d.lineno for d in node.decorator_list] + [node.lineno])
    return start, node.end_lineno or node.lineno


def excerpt(spec: dict) -> tuple[str, str]:
    """Return (header, text) for a [context].excerpts entry."""
    path = ROOT / spec["path"]
    if not path.is_file():
        raise ContractError(f"excerpt path missing: {spec['path']}")
    lines = path.read_text("utf-8").splitlines()
    if "symbol" in spec:
        a, b = symbol_span(path, spec["symbol"])
        label = f"{spec['path']}:{a}-{b} ({spec['symbol']})"
    elif "lines" in spec:
        a, b = (int(x) for x in str(spec["lines"]).split("-"))
        b = min(b, len(lines))
        label = f"{spec['path']}:{a}-{b}"
    else:
        raise ContractError(f"excerpt needs symbol or lines: {spec}")
    body = "\n".join(f"{n:>5} {lines[n - 1]}" for n in range(a, b + 1))
    return label, body
