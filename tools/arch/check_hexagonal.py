#!/usr/bin/env python3
"""Static hexagonal-architecture, naming and folder-structure checker for this repo.

Fast (no build, no SDK) and language-aware:
  structure  the tree between <!-- structure:begin --> and <!-- structure:end --> in CLAUDE.md is
             the whole repository: no file may exist outside it (ignored build and cache folders
             aside), and a stack is complete only when every listed file exists
  python     imports parsed with ast (relative imports resolved); PEP 8 module and package names
  java       package and import declarations, fully qualified references, Maven module poms;
             folders mirror packages, lowercase packages, UpperCamelCase class files
  dotnet     using directives, fully qualified references, .csproj SDK and references;
             namespaces mirror project and folders, PascalCase file names

Layers, from the inside out:
  domain       entities and value objects; standard library only
  application  driving ports (port in), driven ports (port out) and the services that implement
               the driving ports; may use domain; standard library only
  inbound:X    driving adapter X (http, mcp); may use application ports and domain
  outbound:Y   driven adapter Y (postgres); may use application ports and domain
  bootstrap    composition root; may use everything

Adapters never depend on other adapters or on application services (they call ports).
Frameworks and drivers live only in adapters and bootstrap. Each stack must carry an
unmodified copy of its architecture-test template from tools/arch/templates/.

Usage:
  check_hexagonal.py python|java|dotnet [--root REPO_ROOT]
      one stack: its layers and names, no files outside its part of the tree, and every listed
      file present (make arch)
  check_hexagonal.py --all [--complete] [--root REPO_ROOT]
      the whole repo: no files outside the tree, plus layers and names of every stack that exists
      (the Stop hook); --complete also requires every listed, non-optional file (publish check)

Exit codes: 0 no violations, 1 violations found, 2 usage error.

Generated with Claude and reviewed by the author. Protected from agent edits by
.claude/hooks/protect-files.sh: the agent being graded must not edit its grader.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

PY_PACKAGE = "booking"
JAVA_BASE = "work.rajc.booking"
DOTNET_BASE = "Rajc.Bookings"

TEMPLATES = Path(__file__).resolve().parent / "templates"
ARCH_TEST_COPIES = {
    "python": ("python/importlinter.toml", "stacks/python/importlinter.toml"),
    "java": ("java/HexagonalArchitectureTest.java",
             "stacks/java/booking-bootstrap/src/test/java/work/rajc/booking/architecture/HexagonalArchitectureTest.java"),
    "dotnet": ("dotnet/HexagonalArchitectureTests.cs",
               "stacks/dotnet/tests/Rajc.Bookings.ArchitectureTests/HexagonalArchitectureTests.cs"),
}

CORE = ("domain", "application")


@dataclass(frozen=True)
class Violation:
    stack: str
    file: str
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        loc = f"{self.file}:{self.line}" if self.line else self.file
        return f"[{self.stack}] {loc}  {self.rule}: {self.detail}"


def kind(layer: str) -> str:
    return layer.split(":", 1)[0]


def edge_allowed(src: str, dst: str) -> bool:
    """May code in layer src depend on code in layer dst?"""
    s, d = kind(src), kind(dst)
    if s == "bootstrap":
        return True
    if s == "domain":
        return d == "domain"
    if s == "application":
        return d in ("application", "domain")
    if s in ("inbound", "outbound"):
        return dst == src or d in ("application", "domain")
    return False


def edge_reason(src: str, dst: str) -> str:
    s, d = kind(src), kind(dst)
    if s in ("inbound", "outbound") and d in ("inbound", "outbound"):
        return "adapters must not depend on other adapters"
    if d == "bootstrap":
        return "only the composition root may depend on bootstrap"
    return f"{s} must not depend on {d}"


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def normalise(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip() + "\n"


def check_arch_test_copy(stack: str, root: Path) -> list[Violation]:
    template_rel, copy_rel = ARCH_TEST_COPIES[stack]
    template, copy = TEMPLATES / template_rel, root / copy_rel
    if not template.exists():
        return [Violation(stack, f"tools/arch/templates/{template_rel}", 0, "missing template", "restore it from the starter kit")]
    if not copy.exists():
        return [Violation(stack, copy_rel, 0, "missing architecture tests",
                          f"copy tools/arch/templates/{template_rel} here verbatim")]
    if normalise(copy.read_text(encoding="utf-8")) != normalise(template.read_text(encoding="utf-8")):
        return [Violation(stack, copy_rel, 0, "architecture tests modified",
                          f"must match tools/arch/templates/{template_rel} exactly; never weaken architecture tests")]
    return []


# --------------------------------------------------------------------------- structure (CLAUDE.md tree)
#
# Tree syntax, one entry per line between the markers (code-fence lines are skipped):
#   <indent><name>[  # comment]
#   indent       two spaces per level; a child is exactly one level below its directory
#   name         ends in "/" for a directory; may hold several segments ("src/main/java/work/");
#                "*" matches within one name, "**" matches any path below the directory
#   comment      two or more spaces, then "#"; "(optional)" in it makes the entry and everything
#                under it optional
# Files are what is checked; directories exist only to hold them.

STRUCTURE_FILE = "CLAUDE.md"
STRUCTURE_BEGIN = "<!-- structure:begin -->"
STRUCTURE_END = "<!-- structure:end -->"
IGNORED_DIRS = frozenset({".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
                          ".import_linter_cache", "node_modules", "target", "bin", "obj", "TestResults", ".idea", ".vscode"})
IGNORED_DIR_SUFFIXES = (".egg-info",)
IGNORED_FILES = frozenset({".DS_Store"})
TREE_LINE = re.compile(r"^(?P<name>\S+)(?:\s{2,}#\s?(?P<comment>.*))?$")
SEGMENT = re.compile(r"^[A-Za-z0-9_.*?\-]+$")


def is_ignored_dir(name: str) -> bool:
    return name in IGNORED_DIRS or name.endswith(IGNORED_DIR_SUFFIXES)


def is_ignored_path(path: Path, base: Path) -> bool:
    """Is any folder between base and path one of the ignored build or cache folders?"""
    try:
        parts = path.relative_to(base).parts[:-1]
    except ValueError:
        return False
    return any(is_ignored_dir(p) for p in parts) or path.name in IGNORED_FILES


@dataclass(frozen=True)
class Entry:
    path: str          # repo-relative, "/" separated, no trailing slash
    is_dir: bool
    optional: bool
    glob: bool
    line: int          # line number in CLAUDE.md


def glob_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".+")
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


class Structure:
    def __init__(self, entries: list[Entry]):
        self.entries = entries
        self.files = {e.path for e in entries if not e.is_dir and not e.glob}
        self.globs = [glob_regex(e.path) for e in entries if e.glob]
        self.open_dirs = [e.path.rsplit("/", 1)[0] if "/" in e.path else "" for e in entries if e.glob and e.path.endswith("**")]
        self.dirs: set[str] = set()
        for e in entries:
            parts = e.path.split("/")
            upto = len(parts) if e.is_dir else len(parts) - 1
            for n in range(1, upto + 1):
                self.dirs.add("/".join(parts[:n]))

    def allows(self, path: str) -> bool:
        return path in self.files or any(g.match(path) for g in self.globs)

    def knows_dir(self, path: str) -> bool:
        return path in self.dirs or any(d == "" or path.startswith(d + "/") for d in self.open_dirs)

    def first_unknown_dir(self, path: str) -> str | None:
        parts = path.split("/")[:-1]
        for n in range(1, len(parts) + 1):
            d = "/".join(parts[:n])
            if not self.knows_dir(d):
                return d
        return None

    def required(self, scope: str | None = None) -> list[Entry]:
        return [e for e in self.entries if not e.is_dir and not e.glob and not e.optional
                and (scope is None or e.path.startswith(scope + "/"))]


def parse_structure(text: str) -> tuple[Structure | None, list[Violation]]:
    def invalid(line: int, detail: str) -> Violation:
        return Violation("structure", f"{STRUCTURE_FILE}:{line}", 0, "structure tree invalid", detail)

    lines = text.splitlines()
    begins = [i for i, l in enumerate(lines) if l.strip() == STRUCTURE_BEGIN]
    ends = [i for i, l in enumerate(lines) if l.strip() == STRUCTURE_END]
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        return None, [Violation("structure", STRUCTURE_FILE, 0, "structure tree missing",
                                f"CLAUDE.md must hold the folder tree once, between {STRUCTURE_BEGIN} and {STRUCTURE_END}")]
    errors: list[Violation] = []
    entries: list[Entry] = []
    seen: set[str] = set()
    parents: list[tuple[int, str, bool]] = []  # (level, path, optional) of the open directories
    for i in range(begins[0] + 1, ends[0]):
        raw, lineno = lines[i].rstrip(), i + 1
        if not raw.strip() or raw.lstrip().startswith("```"):
            continue
        body = raw.lstrip(" ")
        indent = len(raw) - len(body)
        if "\t" in raw:
            errors.append(invalid(lineno, "use spaces, not tabs"))
            continue
        if indent % 2:
            errors.append(invalid(lineno, "indent by two spaces per level"))
            continue
        m = TREE_LINE.match(body)
        if not m:
            errors.append(invalid(lineno, "expected '<name>' optionally followed by two spaces and '# comment'"))
            continue
        name, comment = m.group("name"), m.group("comment") or ""
        level = indent // 2
        while parents and parents[-1][0] >= level:
            parents.pop()
        if level and (not parents or parents[-1][0] != level - 1):
            errors.append(invalid(lineno, f"'{name}' is not exactly one level below a directory (only directories, ending in '/', hold entries)"))
            continue
        parent_path, parent_optional = (parents[-1][1], parents[-1][2]) if parents else ("", False)
        is_dir = name.endswith("/")
        segments = name.rstrip("/").split("/")
        if name.startswith("/") or any(s in ("", ".", "..") or not SEGMENT.match(s) for s in segments):
            errors.append(invalid(lineno, f"'{name}' is not a relative name (letters, digits, '.', '_', '-', globs)"))
            continue
        glob = any(c in name for c in "*?")
        if glob and (is_dir or any(c in s for s in segments[:-1] for c in "*?")):
            errors.append(invalid(lineno, f"'{name}': globs are allowed only in the last segment of a file entry"))
            continue
        path = "/".join(filter(None, [parent_path, *segments]))
        if path in seen:
            errors.append(invalid(lineno, f"'{path}' is listed twice"))
            continue
        seen.add(path)
        optional = parent_optional or "(optional)" in comment
        entries.append(Entry(path, is_dir, optional, glob, lineno))
        if is_dir:
            parents.append((level, path, optional))
    if not entries and not errors:
        errors.append(invalid(begins[0] + 1, "the tree is empty"))
    if errors:
        return None, errors
    return Structure(entries), []


def load_structure(root: Path) -> tuple[Structure | None, list[Violation]]:
    path = root / STRUCTURE_FILE
    if not path.is_file():
        return None, [Violation("structure", STRUCTURE_FILE, 0, "structure tree missing",
                                "CLAUDE.md with the folder tree is required at the repo root")]
    return parse_structure(path.read_text(encoding="utf-8"))


def repo_files(base: Path, root: Path) -> list[str]:
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not is_ignored_dir(d))
        for name in sorted(filenames):
            if name not in IGNORED_FILES:
                found.append(Path(dirpath, name).relative_to(root).as_posix())
    return found


def check_structure(root: Path, structure: Structure, label: str, scope: str | None, complete: bool) -> list[Violation]:
    """No file outside the tree (within scope); with complete, every listed file inside scope exists."""
    out: list[Violation] = []
    base = root / scope if scope else root
    reported: set[str] = set()
    if base.is_dir():
        for f in repo_files(base, root):
            if structure.allows(f):
                continue
            unknown = structure.first_unknown_dir(f)
            if unknown is not None:
                if unknown in reported:
                    continue
                reported.add(unknown)
                out.append(Violation(label, unknown + "/", 0, "not in the folder structure",
                                     "this folder is not in the CLAUDE.md tree; remove it, or stop and ask the author to add it"))
            else:
                out.append(Violation(label, f, 0, "not in the folder structure",
                                     "this file is not in the CLAUDE.md tree; remove or rename it, or stop and ask the author to add it"))
    if complete:
        missing = [e for e in structure.required(scope) if not (root / e.path).is_file()]
        if scope and not base.is_dir() and missing:
            return out + [Violation(label, scope + "/", 0, "missing from the folder structure",
                                    f"the stack does not exist yet; CLAUDE.md lists {len(missing)} files for it")]
        for e in missing:
            out.append(Violation(label, e.path, 0, "missing from the folder structure",
                                 f"listed in CLAUDE.md line {e.line}; create it (a stub is fine while building)"))
    return out


# --------------------------------------------------------------------------- python

PY_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


def py_layer_of_module(module: str) -> str | None:
    parts = module.split(".")
    if not parts or parts[0] != PY_PACKAGE or len(parts) < 2:
        return None
    if parts[1] in ("domain", "application", "bootstrap"):
        return parts[1]
    if parts[1] == "adapters" and len(parts) >= 4 and parts[2] in ("inbound", "outbound"):
        return f"{parts[2]}:{parts[3]}"
    return None


def check_python(root: Path) -> list[Violation]:
    stack = "python"
    src = root / "stacks" / "python" / "src"
    pkg = src / PY_PACKAGE
    out: list[Violation] = []
    if not (root / "stacks" / "python").exists():
        return out
    out += check_arch_test_copy(stack, root)
    if not pkg.is_dir():
        return out + [Violation(stack, rel(pkg, root), 0, "missing layer", f"expected package {PY_PACKAGE} under stacks/python/src")]

    for required in ("domain", "application", "application/ports", "application/services", "bootstrap"):
        if not (pkg / required).is_dir():
            out.append(Violation(stack, rel(pkg / required, root), 0, "missing layer", f"{required} directory is required"))
    for direction in ("inbound", "outbound"):
        d = pkg / "adapters" / direction
        if not d.is_dir() or not any(p.is_dir() and not is_ignored_dir(p.name) for p in d.iterdir()):
            out.append(Violation(stack, rel(d, root), 0, "missing layer", f"at least one {direction} adapter is required"))

    stdlib = set(sys.stdlib_module_names) | {"__future__", "annotationlib", "compression"}
    container_inits = {
        pkg / "__init__.py",
        pkg / "adapters" / "__init__.py",
        pkg / "adapters" / "inbound" / "__init__.py",
        pkg / "adapters" / "outbound" / "__init__.py",
    }

    for f in sorted(src.rglob("*.py")):
        if is_ignored_path(f, src):
            continue
        rel_parts = f.relative_to(src).with_suffix("").parts
        bad = [p for p in rel_parts if not PY_NAME.match(p)]
        if bad:
            out.append(Violation(stack, rel(f, root), 0, "naming",
                                 f"'{bad[0]}' is not a PEP 8 module or package name (lowercase_with_underscores)"))
        module_parts = list(rel_parts)
        is_init = module_parts[-1] == "__init__"
        if is_init:
            module_parts = module_parts[:-1]
        module = ".".join(module_parts)
        layer = py_layer_of_module(module)
        if layer and kind(layer) in ("inbound", "outbound") and not is_init and len(module_parts) == 4:
            layer = None  # a module beside the adapters, not inside an adapter package
        if layer is None:
            if f in container_inits:
                continue
            out.append(Violation(stack, rel(f, root), 0, "file outside layers",
                                 "put it in domain, application, adapters/inbound/<name>, adapters/outbound/<name> or bootstrap"))
            continue
        package = module if is_init else ".".join(module_parts[:-1])
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError as e:
            out.append(Violation(stack, rel(f, root), e.lineno or 0, "syntax error", str(e.msg)))
            continue
        in_ports = module.startswith(f"{PY_PACKAGE}.application.ports")
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = package.split(".")
                    if node.level > 1:
                        base = base[: len(base) - (node.level - 1)]
                    prefix = ".".join(base)
                    targets = [f"{prefix}.{node.module}"] if node.module else [f"{prefix}.{a.name}" for a in node.names]
                elif node.module:
                    targets = [node.module]
                    if node.module.split(".")[0] == PY_PACKAGE:
                        targets = [f"{node.module}.{a.name}" for a in node.names] or targets
            for t in targets:
                top = t.split(".")[0]
                if top == PY_PACKAGE:
                    dst = py_layer_of_module(t)
                    if dst is None:
                        continue  # importing a container package is harmless
                    if not edge_allowed(layer, dst):
                        out.append(Violation(stack, rel(f, root), node.lineno, "forbidden dependency",
                                             f"{layer} -> {dst} ({t}); {edge_reason(layer, dst)}"))
                    elif t.startswith(f"{PY_PACKAGE}.application.services") and (kind(layer) in ("inbound", "outbound") or in_ports):
                        who = "ports" if in_ports else "adapters"
                        out.append(Violation(stack, rel(f, root), node.lineno, "forbidden dependency",
                                             f"{who} must use driving ports, not service implementations ({t})"))
                elif kind(layer) in CORE and top not in stdlib:
                    out.append(Violation(stack, rel(f, root), node.lineno, "framework in core",
                                         f"{layer} imports '{t}'; domain and application may use only the standard library"))
    return out


# --------------------------------------------------------------------------- java

JAVA_MODULES = {
    "booking-domain": "domain",
    "booking-application": "application",
    "booking-bootstrap": "bootstrap",
}
JAVA_FORBIDDEN_CORE = re.compile(r"\b(org\.springframework|jakarta\.|javax\.|com\.zaxxer|org\.postgresql|com\.fasterxml|java\.sql\.|java\.net\.)")
JAVA_PACKAGE_SEGMENT = re.compile(r"^[a-z][a-z0-9]*$")
JAVA_CLASS_FILE = re.compile(r"^[A-Z][A-Za-z0-9]*\.java$")


def java_module_layer(name: str) -> str | None:
    if name in JAVA_MODULES:
        return JAVA_MODULES[name]
    m = re.fullmatch(r"booking-adapter-(in|out)-([a-z0-9]+)", name)
    if m:
        return f"{'inbound' if m.group(1) == 'in' else 'outbound'}:{m.group(2)}"
    return None


def java_layer_of_package(pkg: str) -> str | None:
    if not pkg.startswith(JAVA_BASE + "."):
        return None
    rest = pkg[len(JAVA_BASE) + 1:].split(".")
    if rest[0] in ("domain", "application", "bootstrap"):
        return rest[0]
    if rest[0] == "adapter" and len(rest) >= 3 and rest[1] in ("in", "out"):
        return f"{'inbound' if rest[1] == 'in' else 'outbound'}:{rest[2]}"
    return None


def strip_java_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    return text


def check_java(root: Path) -> list[Violation]:
    stack = "java"
    base = root / "stacks" / "java"
    out: list[Violation] = []
    if not base.exists():
        return out
    out += check_arch_test_copy(stack, root)
    if not (base / "pom.xml").exists():
        out.append(Violation(stack, rel(base / "pom.xml", root), 0, "missing layer", "parent pom.xml (packaging pom) listing the modules is required"))
    modules = {p.name: p for p in base.iterdir() if p.is_dir() and not is_ignored_dir(p.name) and (p / "pom.xml").exists()}
    layers = {name: java_module_layer(name) for name in modules}
    for name, layer in layers.items():
        if layer is None:
            out.append(Violation(stack, rel(modules[name], root), 0, "unknown module",
                                 "modules are booking-domain, booking-application, booking-adapter-in-<name>, booking-adapter-out-<name>, booking-bootstrap"))
    present = {l for l in layers.values() if l}
    for required in ("domain", "application", "bootstrap"):
        if required not in present:
            out.append(Violation(stack, rel(base, root), 0, "missing layer", f"module for {required} is required"))
    for direction in ("inbound", "outbound"):
        if not any(kind(l) == direction for l in present):
            out.append(Violation(stack, rel(base, root), 0, "missing layer", f"at least one {direction} adapter module is required"))

    ns = {"m": "http://maven.apache.org/POM/4.0.0"}
    for name, path in modules.items():
        src_layer = layers.get(name)
        if not src_layer:
            continue
        try:
            pom = ET.parse(path / "pom.xml").getroot()
        except ET.ParseError as e:
            out.append(Violation(stack, rel(path / "pom.xml", root), 0, "invalid pom", str(e)))
            continue
        deps = pom.findall("m:dependencies/m:dependency", ns) or pom.findall("dependencies/dependency")
        for dep in deps:
            def text(tag: str) -> str:
                el = dep.find(f"m:{tag}", ns)
                if el is None:
                    el = dep.find(tag)
                return (el.text or "").strip() if el is not None else ""
            artifact, scope = text("artifactId"), text("scope")
            if scope == "test":
                continue
            dst = java_module_layer(artifact) if artifact.startswith("booking-") else None
            if dst:
                if not edge_allowed(src_layer, dst):
                    out.append(Violation(stack, rel(path / "pom.xml", root), 0, "forbidden dependency",
                                         f"{src_layer} -> {dst} (module {artifact}); {edge_reason(src_layer, dst)}"))
            elif kind(src_layer) in CORE:
                out.append(Violation(stack, rel(path / "pom.xml", root), 0, "framework in core",
                                     f"{src_layer} module depends on {text('groupId')}:{artifact}; core modules may depend only on inner booking modules"))

    for f in sorted(base.rglob("*.java")):
        parts = f.relative_to(base).parts
        if is_ignored_path(f, base) or (len(parts) > 2 and parts[1] == "src" and parts[2] == "test"):
            continue
        module = parts[0]
        module_layer = layers.get(module)
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^\s*package\s+([\w.]+)\s*;", text, flags=re.M)
        pkg = m.group(1) if m else ""
        if f.name not in ("package-info.java", "module-info.java") and not JAVA_CLASS_FILE.match(f.name):
            out.append(Violation(stack, rel(f, root), 0, "naming", "class files are UpperCamelCase, e.g. BookingController.java"))
        bad = [s for s in pkg.split(".") if s and not JAVA_PACKAGE_SEGMENT.match(s)]
        if bad:
            out.append(Violation(stack, rel(f, root), 0, "naming",
                                 f"package segment '{bad[0]}' must be lowercase letters and digits, no underscores or capitals"))
        expected_dir = Path(module, "src", "main", "java", *pkg.split("."))
        if pkg and f.parent.relative_to(base) != expected_dir:
            out.append(Violation(stack, rel(f, root), 0, "package does not match folder",
                                 f"package {pkg} must live in stacks/java/{expected_dir.as_posix()}/"))
        layer = java_layer_of_package(pkg)
        if layer is None:
            out.append(Violation(stack, rel(f, root), 0, "file outside layers",
                                 f"package '{pkg}' is not under {JAVA_BASE}.(domain|application|adapter.in.<name>|adapter.out.<name>|bootstrap)"))
            continue
        if module_layer and module_layer != layer:
            out.append(Violation(stack, rel(f, root), 0, "wrong module",
                                 f"package layer {layer} lives in module {module} ({module_layer})"))
        in_ports = pkg.startswith(f"{JAVA_BASE}.application.port")
        code = strip_java_comments(text)
        for i, line in enumerate(code.splitlines(), start=1):
            im = re.match(r"\s*import\s+(?:static\s+)?([\w.]+)(?:\.\*)?\s*;", line)
            if im:
                target = im.group(1)
                if target.startswith(JAVA_BASE + "."):
                    dst = None
                    segs = target.split(".")
                    for cut in range(len(segs), 0, -1):
                        dst = java_layer_of_package(".".join(segs[:cut]))
                        if dst:
                            break
                    if dst and not edge_allowed(layer, dst):
                        out.append(Violation(stack, rel(f, root), i, "forbidden dependency",
                                             f"{layer} -> {dst} ({target}); {edge_reason(layer, dst)}"))
                    elif target.startswith(f"{JAVA_BASE}.application.service.") and (kind(layer) in ("inbound", "outbound") or in_ports):
                        who = "ports" if in_ports else "adapters"
                        out.append(Violation(stack, rel(f, root), i, "forbidden dependency",
                                             f"{who} must use driving ports, not service implementations ({target})"))
                elif kind(layer) in CORE and (not target.startswith("java.") or JAVA_FORBIDDEN_CORE.search(target)):
                    out.append(Violation(stack, rel(f, root), i, "framework in core",
                                         f"{layer} imports '{target}'; domain and application may use only java.* (no java.sql, java.net)"))
                continue
            if line.lstrip().startswith("package"):
                continue
            if kind(layer) in CORE:
                fq = JAVA_FORBIDDEN_CORE.search(line)
                if fq:
                    out.append(Violation(stack, rel(f, root), i, "framework in core",
                                         f"{layer} references '{fq.group(1)}' by fully qualified name"))
            for ref in re.finditer(re.escape(JAVA_BASE) + r"\.adapter\.(in|out)\.(\w+)", line):
                dst = f"{'inbound' if ref.group(1) == 'in' else 'outbound'}:{ref.group(2)}"
                if not edge_allowed(layer, dst):
                    out.append(Violation(stack, rel(f, root), i, "forbidden dependency",
                                         f"{layer} -> {dst} by fully qualified name; {edge_reason(layer, dst)}"))
    return out


# --------------------------------------------------------------------------- dotnet

DOTNET_FORBIDDEN_FQ = re.compile(r"\b(Microsoft\.AspNetCore|Microsoft\.Extensions|Npgsql|System\.Data|System\.Net|System\.Text\.Json|System\.IO)\b")
DOTNET_CORE_SYSTEM_DENY = ("System.Data", "System.Net", "System.Text.Json", "System.IO")
DOTNET_FILE = re.compile(r"^[A-Z][A-Za-z0-9]*(\.[A-Z][A-Za-z0-9]*)*\.cs$")
DOTNET_FOLDER = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def dotnet_layer_of_namespace(ns: str) -> str | None:
    if not ns.startswith(DOTNET_BASE + "."):
        return None
    rest = ns[len(DOTNET_BASE) + 1:].split(".")
    if rest[0] in ("Domain", "Application", "Bootstrap"):
        return rest[0].lower()
    if rest[0] == "Adapters" and len(rest) >= 3 and rest[1] in ("Inbound", "Outbound"):
        return f"{rest[1].lower()}:{rest[2].lower()}"
    return None


def dotnet_layer_of_project(name: str) -> str | None:
    layer = dotnet_layer_of_namespace(name)
    if layer is None:
        return None
    expected = {"domain": "Domain", "application": "Application", "bootstrap": "Bootstrap"}
    if layer in expected:
        return layer if name == f"{DOTNET_BASE}.{expected[layer]}" else None
    return layer if name.count(".") == DOTNET_BASE.count(".") + 3 else None


def strip_cs_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'@?"(?:\\.|[^"\\])*"', '""', text)
    return text


def check_dotnet(root: Path) -> list[Violation]:
    stack = "dotnet"
    base = root / "stacks" / "dotnet"
    src = base / "src"
    out: list[Violation] = []
    if not base.exists():
        return out
    out += check_arch_test_copy(stack, root)
    if not src.is_dir():
        return out + [Violation(stack, rel(src, root), 0, "missing layer", "projects live under stacks/dotnet/src/<Project>/")]
    projects = {p.name: p for p in src.iterdir() if p.is_dir() and not is_ignored_dir(p.name) and (p / f"{p.name}.csproj").exists()}
    layers = {name: dotnet_layer_of_project(name) for name in projects}
    for name, layer in layers.items():
        if layer is None:
            out.append(Violation(stack, rel(projects[name], root), 0, "unknown project",
                                 f"projects are {DOTNET_BASE}.Domain, .Application, .Adapters.Inbound.<Name>, .Adapters.Outbound.<Name>, .Bootstrap"))
    for p in src.iterdir():
        if p.is_dir() and p.name not in projects and not is_ignored_dir(p.name):
            out.append(Violation(stack, rel(p, root), 0, "unknown project", f"folder has no {p.name}.csproj; folder and project names must match"))
    present = {l for l in layers.values() if l}
    for required in ("domain", "application", "bootstrap"):
        if required not in present:
            out.append(Violation(stack, rel(src, root), 0, "missing layer", f"project for {required} is required"))
    for direction in ("inbound", "outbound"):
        if not any(kind(l) == direction for l in present):
            out.append(Violation(stack, rel(src, root), 0, "missing layer", f"at least one {direction} adapter project is required"))

    for name, path in projects.items():
        src_layer = layers.get(name)
        if not src_layer:
            continue
        csproj = path / f"{name}.csproj"
        try:
            proj = ET.parse(csproj).getroot()
        except ET.ParseError as e:
            out.append(Violation(stack, rel(csproj, root), 0, "invalid csproj", str(e)))
            continue
        sdk = proj.get("Sdk", "")
        if kind(src_layer) in ("domain", "application", "outbound") and sdk != "Microsoft.NET.Sdk":
            out.append(Violation(stack, rel(csproj, root), 0, "framework in core" if kind(src_layer) in CORE else "wrong sdk",
                                 f"{src_layer} must use Sdk=\"Microsoft.NET.Sdk\", not \"{sdk}\" (the Web SDK pulls in ASP.NET Core)"))
        for ref in proj.iter("ProjectReference"):
            target = Path(ref.get("Include", "").replace("\\", "/")).stem
            dst = dotnet_layer_of_project(target)
            if dst and not edge_allowed(src_layer, dst):
                out.append(Violation(stack, rel(csproj, root), 0, "forbidden dependency",
                                     f"{src_layer} -> {dst} (ProjectReference {target}); {edge_reason(src_layer, dst)}"))
        if kind(src_layer) in CORE:
            for tag in ("PackageReference", "FrameworkReference"):
                for ref in proj.iter(tag):
                    out.append(Violation(stack, rel(csproj, root), 0, "framework in core",
                                         f"{src_layer} has {tag} {ref.get('Include')}; core projects take no packages"))
            for using in proj.iter("Using"):
                out.append(Violation(stack, rel(csproj, root), 0, "framework in core",
                                     f"{src_layer} declares a global using {using.get('Include')} in the project file"))

    for f in sorted(src.rglob("*.cs")):
        parts = f.relative_to(src).parts
        if is_ignored_path(f, src):
            continue
        project = parts[0]
        layer = layers.get(project)
        if layer is None:
            if project not in projects:
                out.append(Violation(stack, rel(f, root), 0, "file outside layers", "every .cs file belongs to a layer project"))
            continue
        if not DOTNET_FILE.match(f.name):
            out.append(Violation(stack, rel(f, root), 0, "naming", "C# files are PascalCase, e.g. BookingEndpoints.cs"))
        bad_folders = [p for p in parts[1:-1] if not DOTNET_FOLDER.match(p)]
        if bad_folders:
            out.append(Violation(stack, rel(f, root), 0, "naming", f"folder '{bad_folders[0]}' must be PascalCase"))
        expected_ns = ".".join((project, *parts[1:-1]))
        in_ports = expected_ns.startswith(f"{DOTNET_BASE}.Application.Ports")
        code = strip_cs_comments(f.read_text(encoding="utf-8"))
        for i, line in enumerate(code.splitlines(), start=1):
            nm = re.match(r"\s*namespace\s+([\w.]+)", line)
            if nm:
                if nm.group(1) != expected_ns:
                    out.append(Violation(stack, rel(f, root), i, "namespace does not match folder",
                                         f"namespace {nm.group(1)} should be {expected_ns} (project name plus folder path)"))
                continue
            um = re.match(r"\s*(?:global\s+)?using\s+(?:static\s+)?(?:\w+\s*=\s*)?([\w.]+)\s*;", line)
            if um:
                target = um.group(1)
                if target == DOTNET_BASE or target.startswith(DOTNET_BASE + "."):
                    dst = dotnet_layer_of_namespace(target)
                    if dst and not edge_allowed(layer, dst):
                        out.append(Violation(stack, rel(f, root), i, "forbidden dependency",
                                             f"{layer} -> {dst} ({target}); {edge_reason(layer, dst)}"))
                    elif target.startswith(f"{DOTNET_BASE}.Application.Services") and (kind(layer) in ("inbound", "outbound") or in_ports):
                        who = "ports" if in_ports else "adapters"
                        out.append(Violation(stack, rel(f, root), i, "forbidden dependency",
                                             f"{who} must use driving ports, not service implementations ({target})"))
                elif kind(layer) in CORE:
                    allowed = (target == "System" or target.startswith("System.")) and not target.startswith(DOTNET_CORE_SYSTEM_DENY)
                    if not allowed:
                        out.append(Violation(stack, rel(f, root), i, "framework in core",
                                             f"{layer} uses '{target}'; domain and application may use only System.* (no data, network, IO or JSON)"))
                continue
            if kind(layer) in CORE:
                fq = DOTNET_FORBIDDEN_FQ.search(line)
                if fq:
                    out.append(Violation(stack, rel(f, root), i, "framework in core",
                                         f"{layer} references '{fq.group(1)}' by fully qualified name"))
            for ref in re.finditer(re.escape(DOTNET_BASE) + r"\.Adapters\.(Inbound|Outbound)\.(\w+)", line):
                dst = f"{ref.group(1).lower()}:{ref.group(2).lower()}"
                if not edge_allowed(layer, dst):
                    out.append(Violation(stack, rel(f, root), i, "forbidden dependency",
                                         f"{layer} -> {dst} by fully qualified name; {edge_reason(layer, dst)}"))
    return out


CHECKS = {"python": check_python, "java": check_java, "dotnet": check_dotnet}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stack", nargs="?", choices=sorted(CHECKS))
    ap.add_argument("--all", action="store_true", help="whole repo: no files outside the tree, every existing stack")
    ap.add_argument("--complete", action="store_true", help="with --all: every listed, non-optional file must exist")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]), help="repo root")
    args = ap.parse_args(argv)
    if bool(args.stack) == bool(args.all) or (args.complete and not args.all):
        ap.print_usage(sys.stderr)
        return 2
    root = Path(args.root).resolve()
    structure, violations = load_structure(root)
    checked: list[str] = []
    if args.all:
        if structure:
            violations += check_structure(root, structure, "structure", None, complete=args.complete)
        checked.append("folder structure" + (" (complete)" if args.complete else ""))
        stacks = [s for s in sorted(CHECKS) if (root / "stacks" / s).is_dir()]
    else:
        if structure:
            violations += check_structure(root, structure, args.stack, f"stacks/{args.stack}", complete=True)
        checked.append(f"stacks/{args.stack} folder structure (complete)")
        stacks = [args.stack] if (root / "stacks" / args.stack).is_dir() else []
    for s in stacks:
        checked.append(s)
        violations.extend(CHECKS[s](root))
    for v in violations:
        print(v)
    if args.all and not stacks:
        checked.append("no stacks to check yet")
    if violations:
        print(f"hexagonal check FAILED: {len(violations)} violation(s); checked {', '.join(checked)}")
        return 1
    print(f"hexagonal check passed: {', '.join(checked)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
