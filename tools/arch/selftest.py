#!/usr/bin/env python3
"""Self-test for check_hexagonal.py.

Fixtures are generated from the folder tree in CLAUDE.md, so the test always matches the tree the
agent is told to build. For each stack, the complete tree must pass; then every deliberate violation
must be caught with the expected rule: layering, frameworks in the core, naming conventions, folders
against packages and namespaces, files outside the tree, files missing from the tree, and missing or
modified architecture tests. Ignored build and cache folders and optional entries must not fail.
The same is checked for the whole repo (--all, --all --complete) and for a malformed tree.

Run: python3 tools/arch/selftest.py   (exit 0 = every case behaved as expected)
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_hexagonal as ch  # noqa: E402

CHECKER = HERE / "check_hexagonal.py"
TEMPLATES = HERE / "templates"
KIT = HERE.parents[1]
CLAUDE_MD = (KIT / "CLAUDE.md").read_text(encoding="utf-8")
STRUCTURE, _tree_errors = ch.parse_structure(CLAUDE_MD)
if STRUCTURE is None:
    print("CLAUDE.md folder tree is invalid:", *map(str, _tree_errors), sep="\n  ")
    sys.exit(1)


def write(root: Path, files: dict[str, str]) -> None:
    for path, content in files.items():
        p = root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def stub(path: str) -> str:
    """Smallest content that is valid for the checker at this path."""
    name = path.rsplit("/", 1)[-1]
    if not path.startswith("stacks/"):
        return f"# self-test stub for {path}\n"
    if name.endswith(".py"):
        return ""
    if name.endswith(".java"):
        package = re.search(r"/src/(?:main|test)/java/(.+)/[^/]+\.java$", path).group(1).replace("/", ".")
        return f"package {package};\n\nfinal class {name[:-5]} {{\n}}\n"
    if name.endswith(".cs"):
        parts = path.split("/")
        i = 3  # stacks/dotnet/(src|tests)/<Project>/...
        return f"namespace {'.'.join([parts[i], *parts[i + 1:-1]])};\n\ninternal static class {name[:-3]}\n{{\n}}\n"
    if name.endswith(".csproj"):
        return '<Project Sdk="Microsoft.NET.Sdk"></Project>\n'
    if name.endswith(".xml"):
        return '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion></project>\n'
    if name.endswith(".json"):
        return "{}\n"
    return f"# self-test stub for {path}\n"


def skeleton(scope: str | None = None) -> dict[str, str]:
    """Every required (listed, non-glob, non-optional) file in scope, as a stub, plus CLAUDE.md."""
    files = {e.path: stub(e.path) for e in STRUCTURE.required(scope)}
    files["CLAUDE.md"] = CLAUDE_MD
    return files


# ----------------------------------------------------------------- python: overlays on the tree
P = "stacks/python/src/booking"
PY_GOOD = {
    "stacks/python/importlinter.toml": template("python/importlinter.toml"),
    "stacks/python/pyproject.toml": "[project]\nname = \"booking\"\n",
    f"{P}/domain/booking.py": "from dataclasses import dataclass\nimport uuid\n\n@dataclass(frozen=True)\nclass Booking:\n    id: uuid.UUID\n    deposit_cents: int\n",
    f"{P}/domain/errors.py": "class InvalidDepositError(ValueError):\n    pass\n",
    f"{P}/application/ports/inbound.py": "from typing import Protocol\nfrom booking.domain.booking import Booking\n\nclass BookSessionIdempotentUseCase(Protocol):\n    async def book(self, key: str, command: object) -> object: ...\n",
    f"{P}/application/ports/outbound.py": "from typing import Protocol\n\nclass KeyAlreadyClaimedError(Exception):\n    pass\n\nclass BookingStore(Protocol):\n    async def find_key(self, key: str) -> object: ...\n",
    f"{P}/application/services/request_hash.py": "import hashlib\n",
    f"{P}/application/services/book_session_naive.py": "from booking.application.ports.outbound import BookingStore\n",
    f"{P}/application/services/book_session_idempotent.py": "from ..ports.outbound import BookingStore, KeyAlreadyClaimedError\nfrom .request_hash import *\n",
    f"{P}/adapters/inbound/http/routes_v2.py": "from fastapi import APIRouter\nfrom booking.application.ports.inbound import BookSessionIdempotentUseCase\n",
    f"{P}/adapters/inbound/http/schemas.py": "from pydantic import BaseModel, ConfigDict\n",
    f"{P}/adapters/inbound/http/fault_hook.py": "import asyncio\n",
    f"{P}/adapters/outbound/postgres/booking_store.py": "import psycopg\nfrom booking.application.ports.outbound import BookingStore, KeyAlreadyClaimedError\n",
    f"{P}/bootstrap/container.py": "from booking.application.services.book_session_idempotent import *\nfrom booking.adapters.outbound.postgres.booking_store import *\n",
    f"{P}/bootstrap/main.py": "from booking.adapters.inbound.http import routes_v2\nimport uvicorn\n",
    "stacks/python/tests/unit/test_book_session_idempotent.py": "from booking.adapters.outbound.postgres.booking_store import *\n",
}
PY_MCP = {
    f"{P}/adapters/inbound/mcp/__init__.py": "",
    f"{P}/adapters/inbound/mcp/schemas.py": "from pydantic import BaseModel, ConfigDict\n",
    f"{P}/adapters/inbound/mcp/tools.py": "from booking.application.ports.inbound import BookSessionIdempotentUseCase\nfrom .schemas import *\n",
}
PY_BAD = [
    ("domain imports a framework", {f"{P}/domain/booking.py": "from pydantic import BaseModel\n"}, "framework in core"),
    ("application imports a driver", {f"{P}/application/services/book_session_naive.py": "import psycopg\n"}, "framework in core"),
    ("application imports an outbound adapter", {f"{P}/application/services/book_session_naive.py": "from booking.adapters.outbound.postgres.booking_store import X\n"}, "forbidden dependency"),
    ("relative import from application into adapters", {f"{P}/application/services/book_session_naive.py": "from ...adapters.outbound.postgres import booking_store\n"}, "forbidden dependency"),
    ("inbound adapter imports outbound adapter", {f"{P}/adapters/inbound/http/routes_v2.py": "from booking.adapters.outbound.postgres.booking_store import X\n"}, "adapters must not depend on other adapters"),
    ("MCP adapter imports the HTTP adapter", {**PY_MCP, f"{P}/adapters/inbound/mcp/tools.py": "from booking.adapters.inbound.http.schemas import BookingRequest\n"}, "adapters must not depend on other adapters"),
    ("adapter imports a service instead of a port", {f"{P}/adapters/inbound/http/routes_v2.py": "from booking.application.services.book_session_idempotent import BookSessionIdempotentService\n"}, "not service implementations"),
    ("port imports a service", {f"{P}/application/ports/inbound.py": "from booking.application.services.request_hash import request_hash\n"}, "not service implementations"),
    ("domain imports application", {f"{P}/domain/booking.py": "from booking.application.ports.outbound import BookingStore\n"}, "forbidden dependency"),
    ("adapter imports bootstrap", {f"{P}/adapters/outbound/postgres/booking_store.py": "from booking.bootstrap.main import app\n"}, "only the composition root may depend on bootstrap"),
    ("file outside the layers", {f"{P}/utils.py": "x = 1\n"}, "file outside layers"),
    ("file directly in adapters/inbound", {f"{P}/adapters/inbound/helpers.py": "x = 1\n"}, "file outside layers"),
    ("module name not PEP 8", {f"{P}/domain/BookingModel.py": "x = 1\n"}, "naming"),
    ("module inside a layer but not in the tree", {f"{P}/application/services/helpers.py": "x = 1\n"}, "services/helpers.py  not in the folder structure"),
    ("package not in the tree (reported once)", {f"{P}/application/use_cases/__init__.py": "", f"{P}/application/use_cases/book.py": "x = 1\n"}, "application/use_cases/  not in the folder structure"),
    ("lock file not in the tree", {"stacks/python/uv.lock": "version = 1\n"}, "uv.lock  not in the folder structure"),
    ("test helper not in the tree", {"stacks/python/tests/unit/conftest.py": ""}, "conftest.py  not in the folder structure"),
    ("architecture tests modified", {"stacks/python/importlinter.toml": template("python/importlinter.toml").replace('"mcp"]', '"mcp", "x"]').replace('type = "independence"', 'type = "forbidden"')}, "architecture tests modified"),
]
PY_MISSING = [
    ("missing bootstrap layer", f"{P}/bootstrap", "missing layer"),
    ("missing services package", f"{P}/application/services", "missing layer"),
    ("missing architecture tests", "stacks/python/importlinter.toml", "missing architecture tests"),
    ("missing listed module", f"{P}/adapters/inbound/http/health.py", "http/health.py  missing from the folder structure"),
    ("missing package marker", f"{P}/domain/__init__.py", "domain/__init__.py  missing from the folder structure"),
    ("missing Dockerfile", "stacks/python/Dockerfile", "Dockerfile  missing from the folder structure"),
    ("missing unit-test fake", "stacks/python/tests/unit/fakes.py", "fakes.py  missing from the folder structure"),
]
PY_ALLOWED = [
    ("ignored caches, virtualenv and egg-info", {
        "stacks/python/.venv/lib/python3.14/site-packages/fastapi/__init__.py": "import starlette\n",
        f"{P}/domain/__pycache__/booking.cpython-314.pyc": "",
        "stacks/python/.pytest_cache/v/cache/nodeids": "[]\n",
        "stacks/python/.import_linter_cache/cache.json": "{}\n",
        "stacks/python/src/booking.egg-info/PKG-INFO": "Name: booking\n",
        f"{P}/.DS_Store": "",
    }),
    ("optional MCP adapter (P6) present", PY_MCP),
]

# ----------------------------------------------------------------- java: overlays on the tree
J = "stacks/java"
JP = "src/main/java/work/rajc/booking"
JAVA_ARCH_TEST = f"{J}/booking-bootstrap/src/test/java/work/rajc/booking/architecture/HexagonalArchitectureTest.java"


def pom(artifact: str, deps: list[tuple[str, str, str]] = ()) -> str:
    d = "".join(f"<dependency><groupId>{g}</groupId><artifactId>{a}</artifactId>{f'<scope>{s}</scope>' if s else ''}</dependency>" for g, a, s in deps)
    return f'<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><artifactId>{artifact}</artifactId><dependencies>{d}</dependencies></project>'


def jfile(module: str, pkg: str, cls: str, body: str) -> tuple[str, str]:
    path = f"{J}/{module}/src/main/java/{pkg.replace('.', '/')}/{cls}.java"
    return path, f"package {pkg};\n\n{body}"


J_GOOD = dict([
    (f"{J}/pom.xml", '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><artifactId>booking-parent</artifactId><packaging>pom</packaging></project>'),
    (f"{J}/booking-domain/pom.xml", pom("booking-domain", [("org.junit.jupiter", "junit-jupiter", "test")])),
    jfile("booking-domain", "work.rajc.booking.domain", "Booking", "import java.util.UUID;\n\npublic record Booking(UUID id, int depositCents) {}\n"),
    (f"{J}/booking-application/pom.xml", pom("booking-application", [("work.rajc", "booking-domain", "")])),
    jfile("booking-application", "work.rajc.booking.application.port.in", "BookSessionIdempotentUseCase", "import work.rajc.booking.domain.Booking;\n\npublic interface BookSessionIdempotentUseCase { BookingOutcome book(String key, BookSessionCommand c); }\n"),
    jfile("booking-application", "work.rajc.booking.application.port.out", "BookingStore", "public interface BookingStore {}\n"),
    jfile("booking-application", "work.rajc.booking.application.port.out", "KeyAlreadyClaimedException", "public final class KeyAlreadyClaimedException extends RuntimeException {}\n"),
    jfile("booking-application", "work.rajc.booking.application.service", "BookSessionIdempotentService",
          "import java.security.MessageDigest;\nimport work.rajc.booking.application.port.in.BookSessionIdempotentUseCase;\nimport work.rajc.booking.application.port.out.BookingStore;\n// org.springframework in a comment is fine\npublic final class BookSessionIdempotentService { String s = \"jakarta. in a string is fine\"; }\n"),
    (f"{J}/booking-adapter-in-http/pom.xml", pom("booking-adapter-in-http", [("work.rajc", "booking-application", ""), ("org.springframework.boot", "spring-boot-starter-web", "")])),
    jfile("booking-adapter-in-http", "work.rajc.booking.adapter.in.http", "BookingController",
          "import org.springframework.web.bind.annotation.RestController;\nimport work.rajc.booking.application.port.in.BookSessionIdempotentUseCase;\n\n@RestController\nclass BookingController {}\n"),
    jfile("booking-adapter-in-http", "work.rajc.booking.adapter.in.http", "NaiveBookingController", "class NaiveBookingController {}\n"),
    (f"{J}/booking-adapter-out-postgres/pom.xml", pom("booking-adapter-out-postgres", [("work.rajc", "booking-application", ""), ("org.postgresql", "postgresql", "")])),
    jfile("booking-adapter-out-postgres", "work.rajc.booking.adapter.out.postgres", "PostgresBookingStore",
          "import java.sql.SQLException;\nimport work.rajc.booking.application.port.out.BookingStore;\n\nclass PostgresBookingStore {}\n"),
    (f"{J}/booking-bootstrap/pom.xml", pom("booking-bootstrap", [("work.rajc", "booking-adapter-in-http", ""), ("work.rajc", "booking-adapter-out-postgres", ""), ("com.tngtech.archunit", "archunit-junit5", "test")])),
    jfile("booking-bootstrap", "work.rajc.booking.bootstrap", "BookingApplication",
          "import org.springframework.boot.autoconfigure.SpringBootApplication;\nimport work.rajc.booking.application.service.BookSessionIdempotentService;\nimport work.rajc.booking.adapter.in.http.BookingController;\nimport work.rajc.booking.adapter.out.postgres.PostgresBookingStore;\n\n@SpringBootApplication\npublic class BookingApplication {}\n"),
    (JAVA_ARCH_TEST, template("java/HexagonalArchitectureTest.java")),
])
J_BAD = [
    ("domain imports Spring", dict([jfile("booking-domain", "work.rajc.booking.domain", "Booking", "import org.springframework.stereotype.Component;\n\n@Component public record Booking() {}\n")]), "framework in core"),
    ("application uses JDBC", dict([jfile("booking-application", "work.rajc.booking.application.service", "BookSessionIdempotentService", "import java.sql.Connection;\n\nclass BookSessionIdempotentService {}\n")]), "framework in core"),
    ("application uses Spring by fully qualified name", dict([jfile("booking-application", "work.rajc.booking.application.service", "BookSessionIdempotentService", "@org.springframework.transaction.annotation.Transactional\nclass BookSessionIdempotentService {}\n")]), "fully qualified name"),
    ("application imports an outbound adapter", dict([jfile("booking-application", "work.rajc.booking.application.service", "BookSessionIdempotentService", "import work.rajc.booking.adapter.out.postgres.PostgresBookingStore;\n\nclass BookSessionIdempotentService {}\n")]), "forbidden dependency"),
    ("http adapter imports postgres adapter", dict([jfile("booking-adapter-in-http", "work.rajc.booking.adapter.in.http", "BookingController", "import work.rajc.booking.adapter.out.postgres.PostgresBookingStore;\n\nclass BookingController {}\n")]), "adapters must not depend on other adapters"),
    ("controller imports a service instead of a port", dict([jfile("booking-adapter-in-http", "work.rajc.booking.adapter.in.http", "BookingController", "import work.rajc.booking.application.service.BookSessionIdempotentService;\n\nclass BookingController {}\n")]), "not service implementations"),
    ("application pom depends on Spring", {f"{J}/booking-application/pom.xml": pom("booking-application", [("work.rajc", "booking-domain", ""), ("org.springframework", "spring-tx", "")])}, "framework in core"),
    ("http adapter pom depends on postgres adapter", {f"{J}/booking-adapter-in-http/pom.xml": pom("booking-adapter-in-http", [("work.rajc", "booking-application", ""), ("work.rajc", "booking-adapter-out-postgres", "")])}, "adapters must not depend on other adapters"),
    ("domain class placed in application module", dict([jfile("booking-application", "work.rajc.booking.domain", "Stray", "class Stray {}\n")]), "wrong module"),
    ("package outside the base package", dict([jfile("booking-domain", "com.example", "Util", "class Util {}\n")]), "file outside layers"),
    ("package does not match folder", {f"{J}/booking-domain/{JP}/domain/model/Charge.java": "package work.rajc.booking.domain;\n\nrecord Charge() {}\n"}, "package does not match folder"),
    ("package segment with underscore", dict([jfile("booking-domain", "work.rajc.booking.domain.value_objects", "DepositAmount", "record DepositAmount(int cents) {}\n")]), "naming"),
    ("class file not UpperCamelCase", {f"{J}/booking-domain/{JP}/domain/charges.java": "package work.rajc.booking.domain;\n\nrecord charges() {}\n"}, "naming"),
    ("class inside a layer but not in the tree", dict([jfile("booking-application", "work.rajc.booking.application.service", "BookingMapper", "final class BookingMapper {}\n")]), "BookingMapper.java  not in the folder structure"),
    ("Maven wrapper not in the tree", {f"{J}/mvnw": "#!/bin/sh\n"}, "mvnw  not in the folder structure"),
    ("module not in the tree", {f"{J}/booking-common/pom.xml": pom("booking-common")}, "booking-common/  not in the folder structure"),
    ("architecture tests modified", {JAVA_ARCH_TEST: template("java/HexagonalArchitectureTest.java").replace('"java.sql..",\n', "")}, "architecture tests modified"),
]
J_MISSING = [
    ("missing outbound adapter module", f"{J}/booking-adapter-out-postgres", "missing layer"),
    ("missing parent pom", f"{J}/pom.xml", "parent pom.xml"),
    ("missing architecture tests", JAVA_ARCH_TEST, "missing architecture tests"),
    ("missing listed class", f"{J}/booking-adapter-in-http/{JP}/adapter/in/http/FaultHook.java", "FaultHook.java  missing from the folder structure"),
    ("missing application.yaml", f"{J}/booking-bootstrap/src/main/resources/application.yaml", "application.yaml  missing from the folder structure"),
    ("missing unit test", f"{J}/booking-application/src/test/java/work/rajc/booking/application/service/RequestHashTest.java", "RequestHashTest.java  missing from the folder structure"),
]
J_ALLOWED = [
    ("ignored build output and IDE files", {
        f"{J}/booking-domain/target/classes/work/rajc/booking/domain/Booking.class": "",
        f"{J}/booking-domain/target/maven-status/inputFiles.lst": "",
        f"{J}/booking-bootstrap/target/generated-sources/Stray.java": "package x;\nimport org.springframework.x;\nclass stray {}\n",
        f"{J}/.idea/workspace.xml": "<project/>",
    }),
]

# ----------------------------------------------------------------- dotnet: overlays on the tree
D = "stacks/dotnet/src"
DOTNET_ARCH_TEST = "stacks/dotnet/tests/Rajc.Bookings.ArchitectureTests/HexagonalArchitectureTests.cs"


def csproj(sdk: str = "Microsoft.NET.Sdk", projects: list[str] = (), packages: list[str] = (), extra: str = "") -> str:
    pr = "".join(f'<ProjectReference Include="..\\{p}\\{p}.csproj" />' for p in projects)
    pk = "".join(f'<PackageReference Include="{p}" />' for p in packages)
    return f'<Project Sdk="{sdk}"><ItemGroup>{pr}{pk}{extra}</ItemGroup></Project>'


def cs(project: str, folder: str, cls: str, body: str, usings: str = "") -> tuple[str, str]:
    ns = project + ("." + folder.replace("/", ".") if folder else "")
    path = f"{D}/{project}/{folder + '/' if folder else ''}{cls}.cs"
    return path, f"{usings}namespace {ns};\n\n{body}"


DOM, APP = "Rajc.Bookings.Domain", "Rajc.Bookings.Application"
HTTP, PG, BOOT = "Rajc.Bookings.Adapters.Inbound.Http", "Rajc.Bookings.Adapters.Outbound.Postgres", "Rajc.Bookings.Bootstrap"
D_GOOD = dict([
    (f"{D}/{DOM}/{DOM}.csproj", csproj()),
    cs(DOM, "", "Booking", "public sealed record Booking(Guid Id, int DepositCents);\n", "using System;\n\n"),
    (f"{D}/{APP}/{APP}.csproj", csproj(projects=[DOM])),
    cs(APP, "Ports/Inbound", "IBookSessionIdempotent", "public interface IBookSessionIdempotent { }\n", f"using {DOM};\n\n"),
    cs(APP, "Ports/Outbound", "IBookingStore", "public interface IBookingStore { Task Add(Booking b); }\n", f"using System.Threading.Tasks;\nusing {DOM};\n\n"),
    cs(APP, "Ports/Outbound", "KeyAlreadyClaimedException", "public sealed class KeyAlreadyClaimedException : Exception { }\n", "using System;\n\n"),
    cs(APP, "Services", "BookSessionIdempotentService", "// Npgsql in a comment is fine\npublic sealed class BookSessionIdempotentService { string s = \"Microsoft.AspNetCore in a string is fine\"; }\n",
       f"using System.Security.Cryptography;\nusing {APP}.Ports.Inbound;\nusing {APP}.Ports.Outbound;\n\n"),
    (f"{D}/{HTTP}/{HTTP}.csproj", csproj(sdk="Microsoft.NET.Sdk.Web", projects=[APP])),
    cs(HTTP, "", "BookingEndpoints", "public static class BookingEndpoints { }\n", f"using Microsoft.AspNetCore.Builder;\nusing {APP}.Ports.Inbound;\n\n"),
    cs(HTTP, "", "NaiveBookingEndpoints", "public static class NaiveBookingEndpoints { }\n"),
    (f"{D}/{PG}/{PG}.csproj", csproj(projects=[APP], packages=["Npgsql"])),
    cs(PG, "", "PostgresBookingStore", "public sealed class PostgresBookingStore { }\n", f"using Npgsql;\nusing {APP}.Ports.Outbound;\n\n"),
    (f"{D}/{BOOT}/{BOOT}.csproj", csproj(sdk="Microsoft.NET.Sdk.Web", projects=[APP, HTTP, PG])),
    cs(BOOT, "", "Program", "public static class Program { }\n", f"using {APP}.Services;\nusing {HTTP};\nusing {PG};\n\n"),
    (DOTNET_ARCH_TEST, template("dotnet/HexagonalArchitectureTests.cs")),
])
D_BAD = [
    ("domain uses ASP.NET Core", dict([cs(DOM, "", "Booking", "public sealed record Booking();\n", "using Microsoft.AspNetCore.Http;\n\n")]), "framework in core"),
    ("application uses JSON serialisation", dict([cs(APP, "Services", "BookSessionIdempotentService", "public sealed class BookSessionIdempotentService { }\n", "using System.Text.Json;\n\n")]), "framework in core"),
    ("application uses Npgsql by fully qualified name", dict([cs(APP, "Services", "BookSessionIdempotentService", "public sealed class BookSessionIdempotentService { Npgsql.NpgsqlConnection? c; }\n")]), "fully qualified name"),
    ("application references the postgres project", {f"{D}/{APP}/{APP}.csproj": csproj(projects=[DOM, PG])}, "forbidden dependency"),
    ("http adapter references postgres adapter", {f"{D}/{HTTP}/{HTTP}.csproj": csproj(sdk="Microsoft.NET.Sdk.Web", projects=[APP, PG])}, "adapters must not depend on other adapters"),
    ("http adapter uses a service instead of a port", dict([cs(HTTP, "", "BookingEndpoints", "public static class BookingEndpoints { }\n", f"using {APP}.Services;\n\n")]), "not service implementations"),
    ("application uses the Web SDK", {f"{D}/{APP}/{APP}.csproj": csproj(sdk="Microsoft.NET.Sdk.Web", projects=[DOM])}, "Web SDK"),
    ("domain takes a package", {f"{D}/{DOM}/{DOM}.csproj": csproj(packages=["Npgsql"])}, "core projects take no packages"),
    ("application declares a global using in the csproj", {f"{D}/{APP}/{APP}.csproj": csproj(projects=[DOM], extra='<Using Include="Npgsql" />')}, "global using"),
    ("http adapter uses the postgres namespace", dict([cs(HTTP, "", "BookingEndpoints", "public static class BookingEndpoints { }\n", f"using {PG};\n\n")]), "adapters must not depend on other adapters"),
    ("namespace does not match folder", {f"{D}/{APP}/Ports/Outbound/StoredKey.cs": f"namespace {APP};\n\npublic sealed record StoredKey();\n"}, "namespace does not match folder"),
    ("file name not PascalCase", dict([cs(DOM, "", "charges", "public sealed record Charges();\n")]), "naming"),
    ("folder name not PascalCase", dict([cs(APP, "helpers", "IClock", "public interface IClock { }\n")]), "naming"),
    ("class inside a layer but not in the tree", dict([cs(APP, "Services", "BookingMapper", "internal static class BookingMapper { }\n")]), "BookingMapper.cs  not in the folder structure"),
    ("NuGet.config not in the tree", {"stacks/dotnet/NuGet.config": "<configuration/>"}, "NuGet.config  not in the folder structure"),
    ("project not in the tree", {f"{D}/Rajc.Bookings.Shared/Rajc.Bookings.Shared.csproj": csproj()}, "Rajc.Bookings.Shared/  not in the folder structure"),
    ("architecture tests modified", {DOTNET_ARCH_TEST: template("dotnet/HexagonalArchitectureTests.cs").replace('        "Npgsql",\n', "")}, "architecture tests modified"),
]
D_MISSING = [
    ("missing bootstrap project", f"{D}/{BOOT}", "missing layer"),
    ("missing architecture tests", DOTNET_ARCH_TEST, "missing architecture tests"),
    ("missing listed class", f"{D}/{HTTP}/FaultHook.cs", "FaultHook.cs  missing from the folder structure"),
    ("missing solution file", "stacks/dotnet/Rajc.Bookings.slnx", "Rajc.Bookings.slnx  missing from the folder structure"),
    ("missing unit-test project", "stacks/dotnet/tests/Rajc.Bookings.Application.Tests", "Rajc.Bookings.Application.Tests.csproj  missing from the folder structure"),
]
D_ALLOWED = [
    ("ignored build output, test results and IDE files", {
        f"{D}/{DOM}/bin/Debug/net10.0/{DOM}.dll": "",
        f"{D}/{DOM}/obj/project.assets.json": "{}\n",
        f"{D}/{DOM}/obj/Debug/net10.0/{DOM}.AssemblyInfo.cs": "using Npgsql;\nnamespace Wrong;\n",
        "stacks/dotnet/tests/Rajc.Bookings.ArchitectureTests/TestResults/run.trx": "<TestRun/>",
        "stacks/dotnet/.vscode/settings.json": "{}\n",
    }),
]

# ----------------------------------------------------------------- whole repo (--all)
STARTER_PREFIXES = (".claude/", "docs/", "prompts/", "tools/")
STARTER_FILES = {".gitignore", ".gitattributes", "CLAUDE.md", "LICENSE"}
REPO_ALLOWED = {
    "observations/exp3/python/META.md": "# P0\n",
    "observations/exp3/python/output/app/main.py": "from fastapi import FastAPI\n",
    "observations/exp3/java/output/src/main/java/com/example/Demo.java": "package com.example;\n",
    ".claude/settings.local.json": "{}\n",
    "CLAUDE.local.md": "notes\n",
    "results/exp3/raw/python_v2_f0.05_r1.json": "{}\n",
    ".github/workflows/contract.yml": "on: push\n",
    ".venv/bin/python": "",
    "harness/__pycache__/db.cpython-312.pyc": "",
    "contracts/.pytest_cache/v/cache/lastfailed": "{}\n",
}
REPO_BAD = [
    ("harness module not in the tree", {"harness/helpers.py": ""}, "harness/helpers.py  not in the folder structure"),
    ("extra results file", {"results/exp3/runs_backup.csv": ""}, "runs_backup.csv  not in the folder structure"),
    ("raw result in a subfolder", {"results/exp3/raw/old/x.json": "{}\n"}, "results/exp3/raw/old/  not in the folder structure"),
    ("extra doc", {"docs/notes.md": ""}, "docs/notes.md  not in the folder structure"),
    ("extra workflow under an optional folder", {".github/workflows/release.yml": ""}, "release.yml  not in the folder structure"),
    ("top-level folder not in the tree (reported once)", {"scripts/fix.sh": "", "scripts/more.sh": ""}, "scripts/  not in the folder structure"),
    ("docker compose instead of k3d", {"docker-compose.yaml": ""}, "docker-compose.yaml  not in the folder structure"),
    ("a fourth stack", {"stacks/go/main.go": ""}, "stacks/go/  not in the folder structure"),
    ("layer violation still caught by --all", dict([cs(DOM, "", "Booking", "public sealed record Booking();\n", "using Npgsql;\n\n")]), "framework in core"),
]
REPO_MISSING = [
    ("README.md", "README.md  missing from the folder structure"),
    ("results/exp3/host.json", "host.json  missing from the folder structure"),
    ("figures/exp3_duplicates.svg", "exp3_duplicates.svg  missing from the folder structure"),
    ("stacks/java/Dockerfile", "stacks/java/Dockerfile  missing from the folder structure"),
]


def broken_trees() -> list[tuple[str, str, str]]:
    lines = CLAUDE_MD.splitlines(keepends=True)
    hooks = next(i for i, l in enumerate(lines) if l.strip().startswith("hooks/"))
    licence = next(i for i, l in enumerate(lines) if l.startswith("LICENSE "))
    makefile = next(i for i, l in enumerate(lines) if l.startswith("Makefile "))
    def edit(i: int, new: str) -> str:
        return "".join(lines[:i] + [new] + lines[i + 1:])
    return [
        ("markers removed", CLAUDE_MD.replace(ch.STRUCTURE_BEGIN, "").replace(ch.STRUCTURE_END, ""), "structure tree missing"),
        ("odd indentation", edit(hooks, " " + lines[hooks]), "two spaces per level"),
        ("an entry under a file", edit(licence, lines[licence] + "  NOTICE\n"), "not exactly one level below a directory"),
        ("an entry listed twice", edit(licence, lines[licence] * 2), "listed twice"),
        ("comment after one space", edit(makefile, "Makefile # commands\n"), "structure tree invalid"),
        ("glob in a folder name", edit(licence, lines[licence] + "*/\n"), "globs are allowed only"),
    ]


def run(root: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-B", str(CHECKER), *args, "--root", str(root)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    failures = 0
    total = 0

    def record(ok: bool, label: str, out: str = "") -> None:
        nonlocal failures, total
        total += 1
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"\n{out}"))

    def scenario(files: dict[str, str], *args: str, drop: str | None = None) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, {k: v for k, v in files.items() if drop is None or (k != drop and not k.startswith(drop + "/"))})
            return run(root, *args)

    overlays = {"python": PY_GOOD, "java": J_GOOD, "dotnet": D_GOOD}
    for stack, overlay in overlays.items():
        stray = [k for k in overlay if not STRUCTURE.allows(k)]
        record(not stray, f"{stack:6}  fixtures use only files listed in the CLAUDE.md tree", f"  not in tree: {stray}")

    suites = [("python", PY_BAD, PY_MISSING, PY_ALLOWED), ("java", J_BAD, J_MISSING, J_ALLOWED), ("dotnet", D_BAD, D_MISSING, D_ALLOWED)]
    for stack, bad_cases, missing_cases, allowed_cases in suites:
        good = {**skeleton(f"stacks/{stack}"), **overlays[stack]}
        code, out = scenario(good, stack)
        record(code == 0, f"{stack:6}  complete tree from CLAUDE.md passes", out)
        code, out = scenario({"CLAUDE.md": CLAUDE_MD}, stack)
        record(code == 1 and "does not exist yet" in out, f"{stack:6}  catches: stack not created yet", out)
        for name, change in allowed_cases:
            code, out = scenario({**good, **change}, stack)
            record(code == 0, f"{stack:6}  allows: {name}", out)
        for name, change, expect in bad_cases:
            code, out = scenario({**good, **change}, stack)
            record(code == 1 and expect in out, f"{stack:6}  catches: {name}", f"  expected '{expect}', exit {code}:\n{out}")
        for name, prefix, expect in missing_cases:
            code, out = scenario(good, stack, drop=prefix)
            record(code == 1 and expect in out, f"{stack:6}  catches: {name}", f"  expected '{expect}', exit {code}:\n{out}")

    code, out = scenario({**skeleton(f"stacks/python"), **PY_GOOD,
                          f"{P}/application/use_cases/__init__.py": "", f"{P}/application/use_cases/a.py": "", f"{P}/application/use_cases/b.py": ""}, "python")
    record(out.count("not in the folder structure") == 1, "python  an unlisted folder is reported once, not file by file", out)

    repo = {**skeleton(), **PY_GOOD, **J_GOOD, **D_GOOD}
    starter = {k: v for k, v in skeleton().items() if k in STARTER_FILES or k.startswith(STARTER_PREFIXES)}
    code, out = scenario(repo, "--all")
    record(code == 0, "repo    complete tree passes --all", out)
    code, out = scenario(repo, "--all", "--complete")
    record(code == 0, "repo    complete tree passes --all --complete", out)
    code, out = scenario(starter, "--all")
    record(code == 0 and "no stacks to check yet" in out, "repo    starter kit alone passes --all", out)
    code, out = scenario(starter, "--all", "--complete")
    record(code == 1 and "Makefile  missing from the folder structure" in out, "repo    starter kit alone fails --all --complete", out)
    code, out = scenario({**repo, **REPO_ALLOWED}, "--all")
    record(code == 0, "repo    allows: observations/**, raw/*.json, optional and ignored paths", out)
    for name, change, expect in REPO_BAD:
        code, out = scenario({**repo, **change}, "--all")
        record(code == 1 and expect in out, f"repo    catches: {name}", f"  expected '{expect}', exit {code}:\n{out}")
    for path, expect in REPO_MISSING:
        code, out = scenario(repo, "--all", drop=path)
        record(code == 0, f"repo    --all tolerates work in progress: {path} not written yet", out)
        code, out = scenario(repo, "--all", "--complete", drop=path)
        record(code == 1 and expect in out, f"repo    --complete catches: {path} missing", f"  expected '{expect}', exit {code}:\n{out}")

    code, out = scenario({"LICENSE": "MIT\n"}, "--all")
    record(code == 1 and "structure tree missing" in out, "tree    catches: no CLAUDE.md", out)
    for name, text, expect in broken_trees():
        code, out = scenario({**starter, "CLAUDE.md": text}, "--all")
        record(code == 1 and expect in out, f"tree    catches: {name}", f"  expected '{expect}', exit {code}:\n{out}")
    code, out = scenario(starter, "python", "--complete")
    record(code == 2, "usage   --complete is only for --all", out)

    print(f"\n{total - failures}/{total} cases behaved as expected")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
