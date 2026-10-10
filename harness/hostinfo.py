"""Writes results/exp3/host.json once per make exp3-all.

OS, CPU model and cores, memory, the container engine and the tool versions,
captured from the host itself.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _cmd(*args: str) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _macos(name: str) -> str:
    return _cmd("sysctl", "-n", name)


def collect() -> dict[str, object]:
    cpu_model = _macos("machdep.cpu.brand_string")
    memory_bytes = _macos("hw.memsize")
    engine = "docker" if shutil.which("docker") else "podman"
    kubectl_version = _cmd("kubectl", "version", "--client")
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.machine})",
        "cpu_model": cpu_model,
        "cpu_cores": os.cpu_count(),
        "memory_gb": round(int(memory_bytes) / 1e9, 1) if memory_bytes.isdigit() else "",
        "container_engine": _cmd(engine, "--version").split(",")[0] if engine else "",
        "k3d": _cmd("k3d", "version").splitlines()[0],
        "kubectl": next((line for line in kubectl_version.splitlines() if "Version" in line), kubectl_version),
        "k6": _cmd("k6", "version").splitlines()[0],
    }


def write() -> Path:
    path = REPO / "results" / "exp3" / "host.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collect(), indent=2) + "\n", encoding="utf-8")
    print(f"hostinfo: wrote {path.relative_to(REPO)}")
    return path


if __name__ == "__main__":
    write()
