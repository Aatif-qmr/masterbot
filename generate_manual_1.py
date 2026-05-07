import ast
import argparse
import json
import os
import re
import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


TEXT_EXTENSIONS = {
    ".py",
    ".pyi",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".md",
    ".txt",
    ".css",
    ".scss",
    ".html",
    ".htm",
    ".j2",
    ".ipynb",
    ".sh",
    ".ps1",
    ".bat",
    ".cmd",
    ".service",
    ".lock",
    ".gitignore",
    ".gitattributes",
    ".dockerignore",
    ".npmrc",
    ".nvmrc",
    ".prettierrc",
    ".editorconfig",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp"}
DATA_EXTENSIONS = {".pkl", ".feather", ".parquet", ".db", ".sqlite", ".csv", ".tsv", ".gz", ".zip"}
TEMPLATE_EXTENSIONS = {".j2"}

MAX_TEXT_BYTES = 200_000
MAX_SNIPPET_CHARS = 220
MAX_GEMINI_CHARS = 60_000

SENSITIVE_PATH_FRAGMENTS = [
    ".env",
    "secret",
    "secrets",
    "credential",
    "credentials",
    "token",
    "apikey",
    "api_key",
    "private",
    "id_rsa",
]

DEFAULT_GEMINI_CACHE_FILE = ".manual_gemini_cache.json"
DEFAULT_GEMINI_EXCLUDE_PREFIXES = ".git/,venv/,freqtrade/,data/,logs/"
DEFAULT_GEMINI_EXTENSIONS = ".py,.pyi,.ts,.tsx,.js,.mjs,.cjs,.sh,.md,.txt,.json,.yml,.yaml,.toml,.ini,.cfg,.conf"


@dataclass(frozen=True)
class NodeInfo:
    rel_path: str
    is_dir: bool
    ext: str
    size_bytes: Optional[int]


def is_probably_text_file(path: Path) -> bool:
    if path.is_dir():
        return False
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        with path.open("rb") as f:
            chunk = f.read(2048)
        if b"\x00" in chunk:
            return False
        try:
            chunk.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    except OSError:
        return False


def read_text_limited(path: Path) -> Optional[str]:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size > MAX_TEXT_BYTES:
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def normalize_rel(path: Path) -> str:
    p = path.as_posix()
    if p.startswith("./"):
        p = p[2:]
    if p == "":
        return "."
    return p


def classify_file(rel_path: str, ext: str) -> str:
    lower = rel_path.lower()
    if "/.git/" in f"/{lower}/" or lower == ".git":
        return "Git metadata"
    if "/venv/" in f"/{lower}/" or lower.startswith("venv/"):
        return "Python virtualenv artifact"
    if "/__pycache__/" in f"/{lower}/":
        return "Python bytecode cache"
    if lower.endswith(".sqlite") or lower.endswith(".sqlite-wal") or lower.endswith(".sqlite-shm"):
        return "SQLite database artifact"
    if rel_path.startswith(".") and "/" not in rel_path:
        return "Repo-level config"
    if ext in {".py", ".pyi"}:
        return "Python source"
    if ext in {".ts", ".tsx"}:
        return "TypeScript source"
    if ext in {".js", ".mjs", ".cjs"}:
        return "JavaScript source"
    if ext == ".sh":
        return "Shell script"
    if ext in {".ps1", ".bat", ".cmd"}:
        return "System script"
    if ext in {".json"}:
        if "config" in lower or lower.endswith("tsconfig.json") or lower.endswith("package.json"):
            return "JSON config"
        return "JSON data/config"
    if ext in {".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf"}:
        return "Config"
    if ext in {".md", ".txt"}:
        return "Documentation"
    if ext in IMAGE_EXTENSIONS:
        return "Image asset"
    if ext in DATA_EXTENSIONS:
        return "Data / binary asset"
    if ext in TEMPLATE_EXTENSIONS:
        return "Template"
    if ext in {".lock"}:
        return "Lockfile"
    if ext in {".service"}:
        return "Service definition"
    if ext in {".log"}:
        return "Log"
    if ext == "":
        return "Executable / script"
    return "Asset / misc"


def short_snippet(text: str) -> str:
    t = " ".join((text or "").strip().split())
    if not t:
        return ""
    if len(t) <= MAX_SNIPPET_CHARS:
        return t
    return t[: MAX_SNIPPET_CHARS - 3] + "..."


def looks_sensitive_path(rel: str) -> bool:
    lower = rel.lower()
    return any(frag in lower for frag in SENSITIVE_PATH_FRAGMENTS)


def redact_secrets(text: str, rel: str) -> str:
    if not text:
        return text
    redacted = text
    redacted = re.sub(
        r"""(?mi)^(\s*[A-Z0-9_]*(?:SECRET|TOKEN|PASS(?:WORD)?|KEY|API[_-]?KEY|PRIVATE)[A-Z0-9_]*\s*=\s*)(.+?)\s*$""",
        r"\1<REDACTED>",
        redacted,
    )
    redacted = re.sub(
        r"""(?mi)^(\s*[^#;\s][^=]{0,80}?(?:secret|token|pass(?:word)?|key|api[_-]?key)[^=]{0,40}?\s*:\s*)(.+?)\s*$""",
        r"\1<REDACTED>",
        redacted,
    )
    redacted = re.sub(
        r"""(?i)("?(?:secret|token|password|pass|api[_-]?key|private[_-]?key)"?\s*:\s*)"(?:\\.|[^"\\])*" """,
        r'\1"<REDACTED>" ',
        redacted,
    )
    if rel.lower().endswith(".env") or rel.lower().endswith(".env.bak"):
        redacted = re.sub(r"""(?m)^(\s*[^#\n=]+=\s*)(.*)$""", r"\1<REDACTED>", redacted)
    return redacted


def truncate_for_gemini(text: str) -> str:
    if len(text) <= MAX_GEMINI_CHARS:
        return text
    head = text[: int(MAX_GEMINI_CHARS * 0.75)]
    tail = text[-int(MAX_GEMINI_CHARS * 0.20) :]
    return head + "\n\n[TRUNCATED]\n\n" + tail


def load_gemini_cache(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    if not isinstance(obj, dict):
        return {}
    return obj


def save_gemini_cache(path: Path, cache: Dict[str, dict]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def cache_key_for_file(size_bytes: Optional[int], mtime_ns: Optional[int]) -> str:
    return f"{size_bytes if size_bytes is not None else 'unknown'}:{mtime_ns if mtime_ns is not None else 'unknown'}"


def parse_csv_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    parts = []
    for p in value.split(","):
        s = p.strip()
        if s:
            parts.append(s)
    return parts


def is_gemini_eligible(
    *,
    rel: str,
    ext: str,
    is_text: bool,
    exclude_prefixes: Sequence[str],
    allowed_exts: Set[str],
) -> bool:
    for p in exclude_prefixes:
        if p and rel.startswith(p):
            return False
    if not is_text:
        return False
    if allowed_exts and ext not in allowed_exts:
        return False
    return True


def extract_python_symbols(text: str) -> Tuple[List[str], List[str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ([], [])
    funcs: List[str] = []
    classes: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            funcs.append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            funcs.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
    return (funcs[:6], classes[:6])


def extract_python_imports(text: str) -> List[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            mod = node.module
            if node.level:
                mod = ("." * node.level) + mod
            imports.append(mod)
    uniq: List[str] = []
    seen: Set[str] = set()
    for i in imports:
        if i not in seen:
            uniq.append(i)
            seen.add(i)
    return uniq


IMPORT_RE_TS = re.compile(r"""(?:import\s+[^;]*?\s+from\s+|import\s*\(\s*|require\s*\(\s*)["']([^"']+)["']""")


def extract_ts_imports(text: str) -> List[str]:
    deps: List[str] = []
    for m in IMPORT_RE_TS.finditer(text):
        deps.append(m.group(1))
    uniq: List[str] = []
    seen: Set[str] = set()
    for d in deps:
        if d not in seen:
            uniq.append(d)
            seen.add(d)
    return uniq


def extract_shell_refs(text: str) -> List[str]:
    refs: Set[str] = set()
    for m in re.finditer(r"""(?:source|\.)\s+([^\s;]+)""", text):
        refs.add(m.group(1).strip("'\""))
    for m in re.finditer(r"""(?:bash|sh|python3?|node)\s+([^\s;]+)""", text):
        refs.add(m.group(1).strip("'\""))
    return sorted(refs)


def safe_relpath(candidate: Path) -> Optional[str]:
    try:
        rel = candidate.relative_to(Path.cwd())
        return normalize_rel(rel)
    except ValueError:
        return None


def resolve_python_import_to_path(
    importer_rel: str, module: str, existing_files: Set[str]
) -> Optional[str]:
    if module.startswith("."):
        level = len(module) - len(module.lstrip("."))
        base_dir = Path(importer_rel).parent
        for _ in range(level):
            base_dir = base_dir.parent
        mod = module.lstrip(".")
        mod_path = Path(*([p for p in mod.split(".") if p]))
        if str(mod_path) == ".":
            mod_path = Path()
        for candidate in (
            base_dir / mod_path.with_suffix(".py"),
            base_dir / mod_path / "__init__.py",
        ):
            rel = normalize_rel(candidate)
            if rel in existing_files:
                return rel
        return None

    mod_path = Path(*module.split("."))
    candidates = [
        mod_path.with_suffix(".py"),
        mod_path / "__init__.py",
        Path("freqtrade") / mod_path.with_suffix(".py"),
        Path("freqtrade") / mod_path / "__init__.py",
    ]
    for c in candidates:
        rel = normalize_rel(c)
        if rel in existing_files:
            return rel
    return None


def resolve_ts_import_to_path(importer_rel: str, spec: str, existing_files: Set[str]) -> Optional[str]:
    if not (spec.startswith(".") or spec.startswith("/")):
        return None
    base_dir = Path(importer_rel).parent
    p = Path(spec.lstrip("/"))
    candidates: List[Path] = []
    if spec.startswith("."):
        candidates.append((base_dir / p))
    else:
        candidates.append(p)
    expanded: List[Path] = []
    exts = [".ts", ".tsx", ".js", ".mjs", ".cjs", ".json"]
    for c in candidates:
        if c.suffix:
            expanded.append(c)
        else:
            for e in exts:
                expanded.append(c.with_suffix(e))
            for e in exts:
                expanded.append(c / ("index" + e))
    for c in expanded:
        rel = normalize_rel(c)
        if rel in existing_files:
            return rel
    return None


def resolve_shell_ref_to_path(importer_rel: str, ref: str, existing_files: Set[str]) -> Optional[str]:
    base_dir = Path(importer_rel).parent
    if ref.startswith("/"):
        rel = ref.lstrip("/")
        if rel in existing_files:
            return rel
        return None
    c = normalize_rel(base_dir / Path(ref))
    if c in existing_files:
        return c
    c2 = normalize_rel(Path(ref))
    if c2 in existing_files:
        return c2
    return None


def extract_json_keys(text: str) -> List[str]:
    try:
        obj = json.loads(text)
    except Exception:
        return []
    if isinstance(obj, dict):
        return list(obj.keys())[:12]
    return []


def build_tree(rel_paths: Sequence[str]) -> str:
    parts_list = [p.split("/") for p in rel_paths if p != "."]
    root: Dict[str, dict] = {}
    for parts in parts_list:
        node = root
        for part in parts:
            node = node.setdefault(part, {})

    def render(node: Dict[str, dict], prefix: str) -> List[str]:
        keys = sorted(node.keys())
        lines: List[str] = []
        for i, k in enumerate(keys):
            is_last = i == len(keys) - 1
            connector = "└── " if is_last else "├── "
            lines.append(prefix + connector + k)
            child = node[k]
            if child:
                ext_prefix = prefix + ("    " if is_last else "│   ")
                lines.extend(render(child, ext_prefix))
        return lines

    return "\n".join(["."] + render(root, ""))


def folder_purpose(dir_rel: str, files_in_dir: List[str], dirs_in_dir: List[str]) -> str:
    parts = [p for p in dir_rel.split("/") if p and p != "."]
    name = parts[-1] if parts else "."
    lower = dir_rel.lower()
    if "/.git" in f"/{lower}":
        return "This directory contains Git’s internal repository data (objects, refs, logs, hooks, and configuration)."
    if "/venv" in f"/{lower}":
        return "This directory contains a Python virtual environment (installed packages and interpreter entrypoints)."
    if "/__pycache__" in f"/{lower}":
        return "This directory contains Python bytecode caches generated by the interpreter."

    counts = f"It contains {len(files_in_dir)} file(s) and {len(dirs_in_dir)} subdirector(ies)."
    exts: Dict[str, int] = {}
    for f in files_in_dir:
        e = Path(f).suffix.lower() or "(no-ext)"
        exts[e] = exts.get(e, 0) + 1
    top_exts = ", ".join([f"{k}:{v}" for k, v in sorted(exts.items(), key=lambda kv: (-kv[1], kv[0]))[:6]]) or "none"
    mix = f"Most common file extensions here: {top_exts}."
    return f"This directory groups artifacts under `{name}`. {counts} {mix}"


def file_purpose(rel: str, ftype: str, snippet: str) -> str:
    if ftype in {"Git metadata", "Python virtualenv artifact", "Python bytecode cache"}:
        return f"This file exists as `{ftype}` at `{rel}` and is created/maintained by tooling rather than authored as application logic."
    if snippet:
        return f"This file exists as `{ftype}` at `{rel}`. The first non-empty line is: {snippet}"
    return f"This file exists as `{ftype}` at `{rel}`."


def file_functionality(rel: str, ftype: str, text: Optional[str]) -> str:
    ext = Path(rel).suffix.lower()
    if text is None:
        if ftype == "Git metadata":
            return "This file stores Git repository internals. It is read/written by Git commands."
        if ftype == "Python virtualenv artifact":
            return "This file is part of a Python virtual environment. It is used by the environment’s interpreter and installed packages."
        if ftype == "Python bytecode cache":
            return "This file is a Python interpreter cache artifact. It is regenerated from source when Python runs."
        if ftype == "SQLite database artifact":
            return "This file is part of an SQLite database (main database or WAL/SHM sidecar). It is read/written by SQLite clients."
        if ext in IMAGE_EXTENSIONS:
            return "This file is an image (binary) and is not parsed as text here."
        if ext in DATA_EXTENSIONS:
            return "This file stores binary/data content and is not parsed as text here."
        return "This file is not parsed as text here (binary, non-UTF8, or exceeds the configured size threshold)."
    if ext in {".md", ".txt"}:
        head = text.splitlines()[0].strip() if text.splitlines() else ""
        if head:
            return f"This is a text document. The first line is: {short_snippet(head)}"
        return "This is a text document with no non-empty first line detected."
    if ext == ".json":
        keys = extract_json_keys(text)
        if keys:
            return f"This JSON file encodes structured configuration/data. Top-level keys include: {', '.join(keys)}."
        return "This JSON file contains structured data, but it did not parse as a top-level object with keys."
    if ext in {".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf"}:
        first = ""
        for line in text.splitlines()[:30]:
            if line.strip() and not line.strip().startswith(("#", ";")):
                first = line.strip()
                break
        if first:
            return f"This is a configuration file. The first non-comment setting-like line is: {short_snippet(first)}"
        return "This is a configuration file consisting primarily of comments/whitespace in the scanned header."
    if ext in {".py"}:
        funcs, classes = extract_python_symbols(text)
        parts: List[str] = []
        if classes:
            parts.append("classes: " + ", ".join(classes))
        if funcs:
            parts.append("functions: " + ", ".join(funcs))
        sig = "; ".join(parts)
        if sig:
            return f"This Python module defines top-level {sig}."
        return "This Python module contains code but no top-level function/class definitions were detected by the parser."
    if ext in {".ts", ".tsx", ".js", ".mjs", ".cjs"}:
        exports = re.findall(r"\bexport\s+(?:class|function|const|type|interface)\s+([A-Za-z0-9_]+)", text)
        exports = exports[:8]
        if exports:
            return f"This source file defines exports, including: {', '.join(exports)}."
        return "This source file contains code, but no `export` declarations were detected by the scanner."
    if ext == ".sh":
        first = ""
        for line in text.splitlines()[:6]:
            if line.strip():
                first = line.strip()
                break
        commands: List[str] = []
        for m in re.finditer(r"""(?m)^\s*(python3?|bash|sh|node|curl|supervisorctl|scp|rsync)\b""", text):
            commands.append(m.group(1))
        uniq = []
        for c in commands:
            if c not in uniq:
                uniq.append(c)
        if first and uniq:
            return f"This is a shell script. It invokes: {', '.join(uniq[:10])}. The first non-empty line is: {short_snippet(first)}"
        if first:
            return f"This is a shell script. The first non-empty line is: {short_snippet(first)}"
        return "This is a shell script with no non-empty first line detected in the scanned header."
    return f"This `{ftype}` file contains text content used by tooling or runtime code. It is interpreted according to its format."


def file_role(rel: str, used_by: Sequence[str]) -> str:
    if used_by:
        return f"Static scanning found {len(used_by)} in-repo reference(s) to this file (see Used By)."
    return "Static scanning did not find any in-repo references to this file (see Used By)."


def file_notes(rel: str, ftype: str, text: Optional[str], size_bytes: Optional[int]) -> str:
    ext = Path(rel).suffix.lower()
    lower = rel.lower()
    if ftype == "Git metadata":
        return "This file is located under `.git/` and is part of Git’s internal storage layout."
    if ftype == "Python virtualenv artifact":
        return "This file is located under `venv/` and is part of an environment created by Python tooling."
    if ext == ".pyc" or "/__pycache__/" in rel:
        return "This is a Python bytecode cache file generated by the interpreter."
    if rel.endswith(".DS_Store") or rel.endswith("._.DS_Store"):
        return "This is a macOS Finder metadata file. It does not affect runtime behavior and is typically safe to delete/regenerate."
    if text is None:
        s = f"This file is classified as `{ftype}` and was not parsed as text."
        if size_bytes is not None:
            s += f" Its size on disk is {size_bytes} bytes."
        return s
    if size_bytes is not None and size_bytes > MAX_TEXT_BYTES:
        return f"This file is larger than the text-parsing threshold ({MAX_TEXT_BYTES} bytes), so only metadata-level documentation is produced. Its size on disk is {size_bytes} bytes."
    if ext in {".lock"}:
        return "This file pins dependency versions/resolutions for reproducible installs. It is usually generated by a package manager and should be edited through that tool."
    if ext in IMAGE_EXTENSIONS:
        return "This is a static image file. It is not executed as code."
    return "No additional special handling notes were detected from static inspection."


def gemini_generate_sections(
    *,
    rel: str,
    ftype: str,
    size_bytes: Optional[int],
    content: Optional[str],
    deps: Sequence[str],
    used_by: Sequence[str],
    model: Optional[str],
    timeout_s: int,
) -> Optional[Dict[str, str]]:
    payload_parts: List[str] = []
    payload_parts.append(f"PATH: {rel}")
    payload_parts.append(f"FILE_TYPE: {ftype}")
    payload_parts.append(f"SIZE_BYTES: {size_bytes if size_bytes is not None else 'unknown'}")
    payload_parts.append("DEPENDENCIES: " + (", ".join(deps) if deps else "None"))
    payload_parts.append("USED_BY: " + (", ".join(used_by) if used_by else "None"))
    if content is not None:
        ext = Path(rel).suffix.lower()
        symbols: List[str] = []
        if ext == ".py":
            funcs, classes = extract_python_symbols(content)
            if classes:
                symbols.append("python_classes=" + ",".join(classes))
            if funcs:
                symbols.append("python_functions=" + ",".join(funcs))
        elif ext in {".ts", ".tsx", ".js", ".mjs", ".cjs"}:
            exports = re.findall(r"\bexport\s+(?:class|function|const|type|interface)\s+([A-Za-z0-9_]+)", content)
            exports = exports[:12]
            if exports:
                symbols.append("exports=" + ",".join(exports))
        elif ext == ".sh":
            refs = extract_shell_refs(content)[:16]
            if refs:
                symbols.append("script_refs=" + ",".join(refs))
        elif ext == ".json":
            keys = extract_json_keys(content)
            if keys:
                symbols.append("json_keys=" + ",".join(keys))
        if symbols:
            payload_parts.append("SYMBOLS: " + " | ".join(symbols))
    payload_parts.append("")
    if content is None:
        payload_parts.append("CONTENT: <NOT PROVIDED>")
    else:
        safe_content = redact_secrets(content, rel) if looks_sensitive_path(rel) else content
        payload_parts.append("CONTENT:\n" + truncate_for_gemini(safe_content))

    payload = "\n".join(payload_parts)

    prompt = (
        "Using only the information provided on stdin (do not assume anything not present there), output STRICT JSON with keys "
        '"purpose","functionality","role","notes". Each value must be 2-6 concise sentences. '
        "If a detail is not explicitly present in the stdin content/metadata, write that it is not specified. "
        "Do not include markdown, code blocks, or extra keys."
    )

    cmd: List[str] = ["gemini", "--output-format", "text", "--skip-trust", "-p", prompt]
    if model:
        cmd.extend(["--model", model])

    try:
        res = subprocess.run(
            cmd,
            input=payload,
            text=True,
            capture_output=True,
            timeout=timeout_s,
        )
    except Exception:
        return None
    if res.returncode != 0:
        return None
    out = (res.stdout or "").strip()
    if not out:
        return None
    try:
        obj = json.loads(out)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", out)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except Exception:
            return None
    if not isinstance(obj, dict):
        return None
    required = {"purpose", "functionality", "role", "notes"}
    if not required.issubset(set(obj.keys())):
        return None
    cleaned: Dict[str, str] = {}
    for k in required:
        v = obj.get(k)
        if not isinstance(v, str):
            return None
        cleaned[k] = " ".join(v.strip().split())
    return cleaned


def main() -> int:
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    root = Path(__file__).resolve().parent
    os.chdir(root)

    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini", action="store_true")
    parser.add_argument("--gemini-model", default=None)
    parser.add_argument("--gemini-timeout", type=int, default=180)
    parser.add_argument("--gemini-cache-file", default=DEFAULT_GEMINI_CACHE_FILE)
    parser.add_argument("--gemini-no-run", action="store_true")
    parser.add_argument("--gemini-exclude-prefixes", default=DEFAULT_GEMINI_EXCLUDE_PREFIXES)
    parser.add_argument("--gemini-extensions", default=DEFAULT_GEMINI_EXTENSIONS)
    parser.add_argument("--gemini-max-calls", type=int, default=None)
    parser.add_argument("--single", default=None)
    parser.add_argument("--out", default="MANUAL-1.md")
    parser.add_argument("--max-files", type=int, default=None)
    args = parser.parse_args()

    out_path = root / args.out
    cache_path = root / args.gemini_cache_file
    gemini_cache = load_gemini_cache(cache_path) if args.gemini_cache_file else {}
    gemini_exclude_prefixes = [p if p.endswith("/") else (p + "/") for p in parse_csv_list(args.gemini_exclude_prefixes)]
    gemini_allowed_exts = {e.strip() for e in parse_csv_list(args.gemini_extensions)}
    gemini_calls_made = [0]

    dir_set: Set[str] = set()
    file_set: Set[str] = set()
    files_by_dir: Dict[str, List[str]] = {}
    dirs_by_dir: Dict[str, List[str]] = {}

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        rel_dir = normalize_rel(Path(dirpath).relative_to(root))
        dir_set.add(rel_dir)
        rel_files = [normalize_rel(Path(rel_dir) / f) for f in filenames]
        rel_dirs = [normalize_rel(Path(rel_dir) / d) for d in dirnames]
        files_by_dir[rel_dir] = sorted(rel_files)
        dirs_by_dir[rel_dir] = sorted(rel_dirs)
        for f in rel_files:
            file_set.add(f)

    all_paths = sorted([p for p in dir_set if p != "."]) + sorted(file_set)
    tree_text = build_tree(sorted([p for p in dir_set if p != "."] + sorted(file_set)))

    deps_map: Dict[str, Set[str]] = {f: set() for f in file_set}

    for rel in sorted(file_set):
        abs_path = root / rel
        text = read_text_limited(abs_path) if is_probably_text_file(abs_path) else None
        ext = abs_path.suffix.lower()
        if ext == ".py" and text is not None:
            for m in extract_python_imports(text):
                resolved = resolve_python_import_to_path(rel, m, file_set)
                if resolved:
                    deps_map[rel].add(resolved)
        elif ext in {".ts", ".tsx", ".js", ".mjs", ".cjs"} and text is not None:
            for spec in extract_ts_imports(text):
                resolved = resolve_ts_import_to_path(rel, spec, file_set)
                if resolved:
                    deps_map[rel].add(resolved)
        elif ext == ".sh" and text is not None:
            for ref in extract_shell_refs(text):
                resolved = resolve_shell_ref_to_path(rel, ref, file_set)
                if resolved:
                    deps_map[rel].add(resolved)
        else:
            deps_map[rel] = deps_map[rel]

    reverse_map: Dict[str, Set[str]] = {f: set() for f in file_set}
    for src, deps in deps_map.items():
        for d in deps:
            if d in reverse_map:
                reverse_map[d].add(src)

    def render_one(rel: str) -> str:
        abs_path = root / rel
        try:
            size_bytes = abs_path.stat().st_size
        except OSError:
            size_bytes = None
        try:
            mtime_ns = abs_path.stat().st_mtime_ns
        except OSError:
            mtime_ns = None
        ext = abs_path.suffix.lower()
        ftype = classify_file(rel, ext)
        is_text = is_probably_text_file(abs_path)
        text = read_text_limited(abs_path) if is_text else None

        used_by = sorted(reverse_map.get(rel, set()))
        deps = sorted(deps_map.get(rel, set()))

        sections: Optional[Dict[str, str]] = None
        cache_entry = gemini_cache.get(rel) if gemini_cache else None
        cache_key = cache_key_for_file(size_bytes, mtime_ns)
        if cache_entry and isinstance(cache_entry, dict) and cache_entry.get("k") == cache_key:
            s = cache_entry.get("s")
            if isinstance(s, dict) and {"purpose", "functionality", "role", "notes"}.issubset(set(s.keys())):
                if all(isinstance(s.get(k), str) for k in ("purpose", "functionality", "role", "notes")):
                    sections = {k: " ".join(str(s[k]).strip().split()) for k in ("purpose", "functionality", "role", "notes")}

        gemini_allowed = is_gemini_eligible(
            rel=rel,
            ext=ext,
            is_text=is_text,
            exclude_prefixes=gemini_exclude_prefixes,
            allowed_exts=gemini_allowed_exts,
        )
        if args.gemini and sections is None and not args.gemini_no_run and gemini_allowed:
            if args.gemini_max_calls is None or gemini_calls_made[0] < args.gemini_max_calls:
                sections = gemini_generate_sections(
                    rel=rel,
                    ftype=ftype,
                    size_bytes=size_bytes,
                    content=text,
                    deps=deps,
                    used_by=used_by,
                    model=args.gemini_model,
                    timeout_s=args.gemini_timeout,
                )
                gemini_calls_made[0] += 1
                if sections is not None and gemini_cache is not None:
                    gemini_cache[rel] = {"k": cache_key, "s": dict(sections)}

        snippet = ""
        if text is not None:
            first_non_empty = ""
            for line in text.splitlines()[:12]:
                if line.strip():
                    first_non_empty = line.strip()
                    break
            snippet = short_snippet(first_non_empty)

        purpose = sections["purpose"] if sections else file_purpose(rel, ftype, snippet)
        functionality = sections["functionality"] if sections else file_functionality(rel, ftype, text)
        role = sections["role"] if sections else file_role(rel, used_by)
        notes = sections["notes"] if sections else file_notes(rel, ftype, text, size_bytes)

        parts: List[str] = []
        parts.append(f"### File: {Path(rel).name}\nPath: {rel}\n")
        parts.append(f"Purpose:\n{purpose}\n")
        parts.append(f"Functionality:\n{functionality}\n")
        parts.append(f"Role in System:\n{role}\n")
        parts.append("Dependencies:\n" + ("\n".join([f"- {d}" for d in deps]) if deps else "- None") + "\n")
        parts.append("Used By:\n" + ("\n".join([f"- {u}" for u in used_by]) if used_by else "- None") + "\n")
        parts.append(f"Notes:\n{notes}\n")
        parts.append("---\n")
        return "".join(parts)

    if args.single:
        rel = normalize_rel(Path(args.single))
        if rel not in file_set:
            raise SystemExit(2)
        content = render_one(rel)
        if args.gemini_cache_file and args.gemini and gemini_cache is not None:
            save_gemini_cache(cache_path, gemini_cache)
        if args.out == "-":
            print(content, end="")
        else:
            out_path.write_text(content, encoding="utf-8")
        return 0

    folder_docs: List[str] = []
    for d in sorted(dir_set):
        if d == ".":
            continue
        folder_docs.append(f"### Folder: {Path(d).name}\nPath: {d}\n")
        p = folder_purpose(d, files_by_dir.get(d, []), dirs_by_dir.get(d, []))
        folder_docs.append(f"Purpose:\n{p}\n")
        folder_docs.append("Role in System:\nThis folder’s contents are referenced via import paths, script invocations, or tool configuration based on the repository structure.\n")
        folder_docs.append("---\n")

    file_docs: List[str] = []
    count = 0
    for rel in sorted(file_set):
        if args.max_files is not None and count >= args.max_files:
            break
        file_docs.append(render_one(rel))
        count += 1
        if args.gemini_cache_file and args.gemini and gemini_cache is not None and count % 50 == 0:
            save_gemini_cache(cache_path, gemini_cache)

    overview = [
        "# Project Manual\n",
        "## 1. Project Overview\n",
        "- This repository contains multiple subsystems under a single project root, including Python-based trading/automation code and a Node/TypeScript-based CLI/tooling workspace.\n",
        "- The top-level directory layout and presence of process/config files indicates a multi-process setup driven by scripts and configuration rather than a single monolithic binary.\n\n",
        "## 2. Directory Structure\n",
        "```text\n",
        tree_text + "\n",
        "```\n\n",
        "## 3. Detailed File Documentation\n\n",
    ]

    system_flow = [
        "## 4. Folder-Level Architecture\n\n",
        *folder_docs,
        "## 5. System Flow\n",
        "- Static analysis of imports and script references indicates that execution is orchestrated by scripts/config, which then call into Python modules and/or Node-based tooling.\n",
        "- Dependency and reverse-dependency lists in each file section show the detected call/import graph within the repository.\n",
    ]

    content = "".join(overview + file_docs + system_flow)
    out_path.write_text(content, encoding="utf-8")
    if args.gemini_cache_file and args.gemini and gemini_cache is not None:
        save_gemini_cache(cache_path, gemini_cache)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
