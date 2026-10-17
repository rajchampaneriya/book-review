#!/usr/bin/env python3
"""Validate every row of PLATFORM_PLAN.md section 1 against the live k3d cluster.

Usage: python3 docs/review/istio/validate_cluster_state.py
Exit 0 = every check passed, exit 1 = at least one FAILED.
Stdlib only; talks to kubectl.
"""

import json
import subprocess
import sys
from pathlib import Path

NS = "wcf-physics"
REPO = Path(__file__).resolve().parents[3]
FAILURES = []


def run(*args):
    return subprocess.run(
        ["kubectl", *args], capture_output=True, text=True, check=False
    )


def get_json(*args):
    r = run(*args, "-o", "json")
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)


def check(name, ok, detail=""):
    line = f"{'PASS' if ok else 'FAIL'}  {name}"
    if detail:
        line += f"  [{detail}]"
    print(line)
    if not ok:
        FAILURES.append(name)


# Namespace
ns = get_json("get", "ns", NS)
check("namespace wcf-physics exists", ns is not None)

# Deployment python
deploy = get_json("get", "deploy", "python", "-n", NS)
if deploy is None:
    check("deployment python exists", False)
else:
    spec = deploy["spec"]["template"]["spec"]
    c = spec["containers"][0]
    res = c.get("resources", {})
    check(
        "deployment python: 1 replica",
        deploy["spec"].get("replicas") == 1,
        f"replicas={deploy['spec'].get('replicas')}",
    )
    check(
        "deployment python: cpu request 1 / limit 2, memory limit 1Gi",
        res.get("requests", {}).get("cpu") == "1"
        and res.get("limits", {}).get("cpu") == "2"
        and res.get("limits", {}).get("memory") == "1Gi",
        f"resources={json.dumps(res)}",
    )
    rp = c.get("readinessProbe")
    check(
        "deployment python: readiness probe on /health:8080",
        bool(rp)
        and rp.get("httpGet", {}).get("path") == "/health"
        and rp.get("httpGet", {}).get("port") == 8080,
    )
    check("deployment python: no liveness probe", not c.get("livenessProbe"))
    env = {e["name"]: e for e in c.get("env", [])}
    pw = env.get("DB_PASSWORD", {})
    check(
        "deployment python: password from the postgres-local Secret (secretKeyRef)",
        pw.get("valueFrom", {}).get("secretKeyRef", {}).get("key") == "POSTGRES_PASSWORD",
    )
    manifest = (REPO / "infra" / "k8s" / "python.yaml").read_text()
    check("no literal password in infra/k8s/python.yaml", "wcf-local" not in manifest)
    check(
        "deployment python: serviceAccountName python, API token not mounted",
        spec.get("serviceAccountName") == "python"
        and spec.get("automountServiceAccountToken") is False,
        f"serviceAccountName={spec.get('serviceAccountName')!r}",
    )
    sc = spec.get("securityContext", {})
    check(
        "deployment python: non-root securityContext (uid 1000, seccomp RuntimeDefault)",
        sc.get("runAsNonRoot") is True
        and sc.get("runAsUser") == 1000
        and sc.get("seccompProfile", {}).get("type") == "RuntimeDefault",
    )

# Service python
svc = get_json("get", "svc", "python", "-n", NS)
if svc is None:
    check("service python exists", False)
else:
    p = svc["spec"]["ports"][0]
    check(
        "service python: NodePort 30083 -> 8080",
        svc["spec"].get("type") == "NodePort"
        and p.get("nodePort") == 30083
        and p.get("port") == 8080,
        f"{p.get('port')}:{p.get('nodePort')}",
    )

# Secret
secret = get_json("get", "secret", "postgres-local", "-n", NS)
check(
    "secret postgres-local exists (local-development defaults)",
    secret is not None and secret.get("type") == "Opaque",
)

# Pod identity: default SA + mounted API token
pod = get_json("get", "pod", "-n", NS, "-l", "app.kubernetes.io/name=python")
items = (pod or {}).get("items", [])
if not items:
    check("python pod exists", False)
else:
    pspec = items[0]["spec"]
    mounts = items[0]["spec"]["containers"][0].get("volumeMounts", [])
    check(
        "pod runs as the python service account with no API token mounted",
        pspec.get("serviceAccountName") == "python"
        and not any(
            m.get("mountPath") == "/var/run/secrets/kubernetes.io/serviceaccount"
            for m in mounts
        ),
    )
    sa = get_json("get", "sa", "-n", NS)
    sa_names = sorted(
        i["metadata"]["name"] for i in (sa or {}).get("items", [])
    )
    expected_sas = [
        "default", "duplicate-audit", "otel-agent", "otel-cluster",
        "postgres", "python", "schema-job",
    ]
    check(
        "six workload service accounts exist",
        sa_names == expected_sas,
        ",".join(sa_names),
    )
    crb = get_json("get", "clusterrolebinding")
    crb_names = {i["metadata"]["name"] for i in (crb or {}).get("items", [])}
    check(
        "otel-agent-read and otel-cluster-read ClusterRoleBindings exist",
        {"otel-agent-read", "otel-cluster-read"} <= crb_names,
    )

# Absent object types in wcf-physics. The observability overlay is opt-in,
# so its otel-agent DaemonSet may or may not be present; nothing else may be.
for kind in ("job", "cronjob"):
    r = get_json("get", kind, "-n", NS)
    items = (r or {}).get("items", [])
    check(f"no {kind} in wcf-physics", not items, f"count={len(items)}")
ds = get_json("get", "daemonset", "-n", NS)
ds_names = sorted(i["metadata"]["name"] for i in (ds or {}).get("items", []))
check(
    "only the overlay's otel-agent DaemonSet may exist in wcf-physics",
    set(ds_names) <= {"otel-agent"},
    ",".join(ds_names),
)

# NetworkPolicy since step 3
np = get_json("get", "networkpolicy", "-n", NS)
np_names = sorted(i["metadata"]["name"] for i in (np or {}).get("items", []))
check(
    "the five core NetworkPolicies exist in wcf-physics",
    set([
        "allow-duplicate-audit", "allow-postgres", "allow-python",
        "allow-schema-job", "default-deny",
    ]) <= set(np_names),
    ",".join(np_names),
)
r = get_json("get", "networkpolicy", "-A")
outside = [
    i["metadata"]["name"] for i in (r or {}).get("items", [])
    if i["metadata"]["namespace"] != NS
]
check("no NetworkPolicy outside wcf-physics", not outside, ",".join(outside))

# Istio absent
ns_list = get_json("get", "ns")
names = [n["metadata"]["name"] for n in (ns_list or {}).get("items", [])]
check("no istio-system namespace (no Istio)", "istio-system" not in names)
crds = run("get", "crds")
check(
    "no Istio CRDs",
    crds.returncode != 0 or "istio" not in crds.stdout.lower(),
)

# Traefik present (k3s default ingress, relevant to section 3.2 --disable=traefik)
traefik = get_json("get", "deploy", "traefik", "-n", "kube-system")
check(
    "traefik present in kube-system (cluster was NOT created with --disable=traefik)",
    traefik is not None,
)

# No OpenTelemetry in the python stack
pyproject = (REPO / "stacks" / "python" / "pyproject.toml").read_text()
deps_start = pyproject.index("dependencies = [")
deps_end = pyproject.index("]", deps_start)
check(
    "no opentelemetry package in stacks/python/pyproject.toml",
    "opentelemetry" not in pyproject[deps_start:deps_end].lower(),
)

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
    sys.exit(1)
print("all checks passed")
