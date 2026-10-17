# Platform plan: Kubernetes objects, Istio and OpenTelemetry

Status: **step 2 (ServiceAccounts, RBAC, Secret reference, securityContext) applied on 2026-10-17;
step 3 (NetworkPolicy) is next.** Steps 5 and 6 (OpenTelemetry, Istio) are not built yet. The diagrams are in
`docs/review/platform-istio-otel.drawio` (six pages, with a PNG preview of each page next to it).

The plan starts with the Python stack. .NET and Java follow the same pattern afterwards, because rule G8 needs the
same behaviour in every stack.

## 1. What the cluster has today

Validated against the live cluster on 2026-10-17 (`k3d-wcf-physics`, k3s v1.36.4+k3s1, one arm64
server node), after plan step 2 was applied: `python3 docs/review/istio/validate_cluster_state.py`
runs 23 checks, one per claim below, and all pass. Run it again after any change to the cluster or
these manifests.

| Object | Today | Evidence |
| --- | --- | --- |
| Namespace | yes: `wcf-physics` | `infra/k8s/namespace.yaml` |
| Deployment | yes: 1 replica, CPU request 1 and limit 2, 1 Gi, readiness probe on `/health` | `infra/k8s/python.yaml:2-46` |
| Service | yes: NodePort 30083 to port 8080 (host 8083) | `infra/k8s/python.yaml:48-63` |
| Secret | yes: `postgres-local`, Opaque, 3 keys, local-development defaults | `infra/k8s/postgres.yaml` |
| Secret use | yes since step 2: the python Deployment composes `DATABASE_URL` from `secretKeyRef`s; no literal password in the manifest | `infra/k8s/python.yaml` |
| ServiceAccount, RBAC | yes since step 2: python runs as the `python` service account with no API token mounted; six workload accounts and the `otel-agent-read` and `otel-cluster-read` ClusterRoles exist | `infra/k8s/rbac.yaml` |
| NetworkPolicy | none anywhere in the cluster; k3s would enforce one out of the box (embedded kube-router controller) | `infra/k8s/` |
| Job | no app Job (only k3s's own completed `helm-install-traefik` Jobs in kube-system); schemas are applied with `kubectl exec` from the host | `infra/scripts/apply-schema.sh:10` |
| CronJob | no | `infra/k8s/` |
| DaemonSet | no app DaemonSet (k3s runs its `svclb-traefik` DaemonSet in kube-system) | `infra/k8s/` |
| Traefik | **yes:** k3s deployed Traefik (Deployment, LoadBalancer Service, svclb DaemonSet in kube-system). `infra/k3d/cluster.yaml` sets no `--disable=traefik`, so section 3.2's assumption needs the cluster recreated | live cluster; `infra/k3d/cluster.yaml` |
| Istio, access policy | no: no `istio-system` namespace, no Istio CRDs | `infra/` |
| OpenTelemetry, dashboard | no: no `opentelemetry` package in the stack | `stacks/python/pyproject.toml:6-10` |
| Liveness probe | no | `infra/k8s/python.yaml` |
| securityContext | yes since step 2: non-root (uid/gid 1000), `runAsNonRoot`, seccomp `RuntimeDefault`, `allowPrivilegeEscalation: false`, capabilities dropped | `infra/k8s/python.yaml` |

## 2. Decisions for the author

| # | Decision | Options | Recommendation |
| --- | --- | --- | --- |
| D1 | Istio data plane | ambient (ztunnel per node, waypoint where L7 is needed), or sidecar (Envoy in every pod) | **Ambient.** No sidecar injection or pod restarts, less memory on one k3d node, and Istio documents k3d support (`global.platform=k3d`). |
| D2 | The mesh and telemetry versus the measured matrix | an opt-in overlay with the 54-run matrix unchanged, or the mesh and telemetry always on | **Opt-in overlay.** Both add work to every request, and the spec fixes the measured setup. If you want them measured, add a separate, labelled variant later. |
| D3 | What the CronJob does | a read-only duplicate audit, request-key retention (deletes old keys, which changes the spec), or both | **Read-only duplicate audit.** It changes nothing, and it shows the experiment's invariant on the dashboard. |
| D4 | How host traffic enters once mTLS is STRICT | through an Istio ingress gateway on a new host port, or the NodePorts stay PERMISSIVE | **Gateway for the mesh demo; NodePorts unchanged for the spec setup.** The gateway needs a new k3d port mapping, which is a spec change. |
| D5 | Dashboard backend | `grafana/otel-lgtm` (one pod: Grafana, a Prometheus-compatible store, Tempo, Loki), or kube-prometheus-stack plus Tempo and Loki | **otel-lgtm.** Grafana describes it as an image for development, demos and testing, which fits one k3d node. |
| D6 | Scope | Python first, then .NET and Java; or all three at once | **Python first.** Keep the overlay off in measured runs until all three stacks have it (G8). |

**Decided by the author on 2026-10-15:** D1 ambient, D2 opt-in overlay, D3 read-only duplicate audit, D6 Python
first. D4 and D5 follow the recommendation unless the author says otherwise.

### 2.1 Decision record: D1, the ambient data plane

- **Decision:** ambient mesh. ztunnel runs once per node; a waypoint proxy is added only where L7
  rules are needed (the python Service). No sidecar containers in application pods.
- **Context:** one k3d server node (arm64, k3s v1.36.4) shared by the measured stacks and the
  observability overlay. Istio documents k3d support (`global.platform=k3d`). Enrolment is a
  namespace label (`istio.io/dataplane-mode=ambient`), so no pod restarts and no injection
  annotations; the measured matrix (D2, overlay off) is untouched by the mesh's presence.
- **Consequences:**
  - L4 security (STRICT mTLS, the postgres AuthorizationPolicy) is enforced by ztunnel with zero
    application change. L7 (retries, timeouts, route rules, the python AuthorizationPolicy)
    requires attaching a waypoint to the python Service.
  - Applications keep plain HTTP service-to-service; nothing in `stacks/` changes.
  - The cluster must be recreated with `--disable=traefik` before install (section 1: Traefik runs
    today because `infra/k3d/cluster.yaml` sets no disable flag).
  - Memory cost is one ztunnel per node plus one waypoint, instead of one Envoy per pod.
  - Escape hatch: sidecar mode stays available per namespace if a future workload needs it.
- **Rejected: sidecar mode.** Injection mutates every pod template and restarts every pod on
  enrolment; one Envoy sidecar per pod multiplies memory on the single node; and this experiment
  needs L7 rules on one service only, which the waypoint covers.

## 3. Proposed design

### 3.1 Kubernetes objects

| Object | Name | Purpose here | File |
| --- | --- | --- | --- |
| ServiceAccount | `python`, `postgres`, `schema-job`, `duplicate-audit`, `otel-agent`, `otel-cluster` | One identity per workload. `automountServiceAccountToken: false` unless the workload needs the API. Istio uses the account as the pod's mTLS identity. | new `infra/k8s/rbac.yaml` |
| ClusterRole and binding | `otel-agent-read` | `get, list, watch` on pods, namespaces, nodes, `nodes/stats`, replicasets (kubeletstats and k8sattributes) | `infra/k8s/rbac.yaml` |
| ClusterRole and binding | `otel-cluster-read` | read-only on the objects the `k8s_cluster` receiver reports: nodes, pods, Deployments, ReplicaSets, DaemonSets, Jobs, CronJobs | `infra/k8s/rbac.yaml` |
| Role and binding (optional) | `matrix-runner` | `get, patch` on `deployments/scale`, restricted by `resourceNames` to dotnet, java and python; only needed if the matrix ever runs in the cluster | `infra/k8s/rbac.yaml` |
| NetworkPolicy | `default-deny`, plus one allow rule per arrow on page 5 of the diagrams | Ingress and egress denied by default. Then allow: host and gateway to python:8080, python to postgres:5432, to DNS on port 53 and to the collector on 4317, the Job and the CronJob to postgres, and the host to the Postgres NodePort for the harness. With ambient mode, also allow port 15008 and the probe address `169.254.7.127`. | new `infra/k8s/network-policy.yaml` |
| Job | `schema-apply` | Runs the rendered `db/schema.sql` once per stack schema inside the cluster. `apply-schema.sh` renders the SQL into a ConfigMap and waits for the Job instead of calling `kubectl exec`. | new `infra/k8s/schema-job.yaml` |
| CronJob | `duplicate-audit` (D3) | Every few minutes it counts `bookings_total - count(distinct client_ref)` per schema and exposes the count as a metric. Read-only. The matrix suspends it during measured runs. | new `infra/k8s/duplicate-audit.yaml` |
| DaemonSet | `otel-agent` | One OpenTelemetry Collector per node. Receivers: otlp, kubeletstats, filelog, prometheus (ztunnel and waypoint). Processors: memory_limiter, k8sattributes, batch. | new `infra/observability/otel-agent.yaml` |
| Deployment | `otel-cluster`, `lgtm` | `k8s_cluster` receiver (replicas, restarts, pod phase); the backend with Grafana | new `infra/observability/otel-cluster.yaml`, `lgtm.yaml` |
| Deployment changes | `python` | `serviceAccountName: python`, the password from `secretKeyRef`, a non-root `securityContext`, a liveness probe, the Service port named `http` | `infra/k8s/python.yaml` |

### 3.2 Istio (ambient, Istio 1.31)

- **Install:** Gateway API CRDs, then the Helm charts `base`, `istiod`, `cni` and `ztunnel` into `istio-system`, with
  `global.platform=k3d`. The cluster is created with `--disable=traefik`, as Istio's k3d guide does.
- **Enrol:** label `wcf-physics` with `istio.io/dataplane-mode=ambient`. Add a waypoint for the namespace only where L7 rules
  are needed (retries, timeouts, HTTP-level policy).
- **Discovery:** nothing changes for the apps. They keep calling `postgres:5432`, and clients keep calling
  `python.wcf-physics.svc:8080`. istiod watches Services and EndpointSlices and pushes them to ztunnel and the waypoint
  over xDS (page 3).
- **Security:** `PeerAuthentication` set to STRICT for the namespace, with the host-facing exception from D4.
  AuthorizationPolicy on postgres (L4, enforced by ztunnel) allows port 5432 only from the service accounts python,
  dotnet, java, schema-job and duplicate-audit. AuthorizationPolicy on python (L7, enforced by the waypoint) allows
  only the gateway's identity, and only on `POST /naive/bookings`, `POST /v2/bookings` and `GET /health` (page 5).
- **Traffic:** a `Gateway` and an `HTTPRoute` for host traffic, and route timeouts. Retries are allowed only on
  `/v2/bookings`; `/naive/bookings` gets `attempts: 0`, so the control group stays naive. Weighted routes can send a
  share of traffic to a new python version (page 4).
- **Fault injection:** Istio's delay and abort happen before the request reaches the app, so they cannot replace the
  app's hold-after-commit hook (page 4). The experiment keeps its own fault hook.

### 3.3 OpenTelemetry and the dashboard

- **Python app:** `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc`,
  `opentelemetry-instrumentation-fastapi` and `opentelemetry-instrumentation-asyncpg`, pinned with `==` as
  `pyproject.toml` requires. The SDK is set up in `bootstrap` (service name, resource attributes, OTLP endpoint from
  `OTEL_*` environment variables). An outcome counter (created, replayed, conflict, in-flight) lives in the inbound
  HTTP adapter, where outcomes are already mapped to status codes. The domain and application layers stay unchanged;
  `check_hexagonal.py` already rejects any non-standard-library import there.
- **Off by default:** the Deployment sets `OTEL_SDK_DISABLED=true`, and the overlay switches it on. The measured
  matrix and contract test 8 see the same service as today.
- **Collectors:** the `otel-agent` DaemonSet and the `otel-cluster` Deployment from section 3.1 send OTLP to `lgtm`.
- **Dashboard** `wcf-physics overview`, provisioned from a JSON file in a ConfigMap (page 6):
  - Services: requests per second, 4xx and 5xx responses, p50, p95 and p99 latency, outcomes, and database time per request.
  - Pods and scale: ready replicas per Deployment, CPU against request and limit, memory against limit, restarts and pod phase, node CPU and memory.
  - Experiment: duplicate bookings per stack (from the audit), run markers (annotations from the harness), and traces of retried requests.
- **Scale:** the spec fixes one replica per stack, so there is no HorizontalPodAutoscaler. The "ready replicas"
  panel shows the matrix scaling stacks to 0 and 1. It would have exposed the java and python runs that were measured
  at 0 replicas (TASKS.md step 5).

## 4. What the author needs to add to CLAUDE.md first

`CLAUDE.md` is protected, so these entries are for the author to add, and `AGENTS.md` must mirror them. Each new
folder is marked optional, so the spec setup stays complete without them.

```text
infra/
  k8s/
    rbac.yaml                             # ServiceAccounts, Roles, ClusterRoles and bindings
    network-policy.yaml                   # default deny plus one allow rule per permitted connection
    schema-job.yaml                       # Job: applies the rendered schema per stack
    duplicate-audit.yaml                  # CronJob: read-only duplicate count per schema
  mesh/                                   # (optional) Istio ambient overlay
    gateway.yaml                          # Gateway and HTTPRoutes for host traffic
    security.yaml                         # PeerAuthentication and AuthorizationPolicies
    traffic.yaml                          # timeouts, retries (v2 only), weighted routes
  observability/                          # (optional) OpenTelemetry overlay
    otel-agent.yaml                       # DaemonSet collector
    otel-cluster.yaml                     # Deployment collector (k8s_cluster)
    lgtm.yaml                             # grafana/otel-lgtm backend and Grafana
    dashboards/
      wcf-physics-overview.json           # provisioned dashboard
  scripts/
    mesh-up.sh                            # make mesh-up
    observe-up.sh                         # make observe-up
stacks/python/src/booking/bootstrap/telemetry.py               # OTel SDK setup
stacks/python/src/booking/adapters/inbound/http/metrics.py     # outcome counter
```

The commands table also needs `make mesh-up` and `make observe-up`. The spec's Infrastructure section needs one
sentence saying that both overlays are opt-in and off for measured runs, plus the gateway and Grafana host ports from
D4. That changes `infra/k3d/cluster.yaml`, so the cluster has to be recreated once.

**Done on 2026-10-17:** the tree entries above are in CLAUDE.md and AGENTS.md (checker passes), the
commands table has both commands, and the spec sentence names the ports: host 8090 -> NodePort 30090
(Istio ingress gateway) and host 8091 -> NodePort 30091 (Grafana). `check_hexagonal.py --all
--complete` now also expects these files to exist: the four `infra/k8s/` manifests, both overlay
scripts, `telemetry.py` and `metrics.py`; they appear as the steps build them (README.md was already
outstanding from P5).

## 5. Sequence and acceptance criteria

Each step is one pull request. The scenarios follow the repository's BDD standards, and they move into
`bdd/features/` when their step starts.

1. **Author: decisions D1 to D6, the CLAUDE.md and AGENTS.md entries, and the spec sentence.**

2. **ServiceAccounts, RBAC, the Secret reference and the securityContext.**

   ```gherkin
   @rule-G7
   Scenario: The python service cannot use the Kubernetes API
     Given the python Deployment runs as the python service account
     When its permission to list pods in wcf-physics is checked
     Then the permission is denied
     And the pod has no API token mounted
   ```

3. **NetworkPolicy.**

   ```gherkin
   @spec-infrastructure
   Scenario Outline: Only permitted connections reach the booking database
     Given default-deny NetworkPolicy is applied in wcf-physics
     When <client> opens a connection to postgres on port 5432
     Then the connection is <result>

     Examples:
       | client        | result   |
       | python        | accepted |
       | schema-job    | accepted |
       | otel-agent    | refused  |
   ```

   ```gherkin
   @contract-2
   Scenario: The host still reaches the python stack through its NodePort
     Given default-deny NetworkPolicy is applied in wcf-physics
     When the contract tests run against the python stack
     Then every contract test passes
   ```

4. **The schema-apply Job and the duplicate-audit CronJob.**

   ```gherkin
   @spec-infrastructure
   Scenario: make up applies every schema through a Job
     Given a fresh k3d cluster
     When make up finishes
     Then the schema-apply Job has completed
     And the dotnet, java and python schemas each hold the three tables
   ```

   ```gherkin
   @spec-measurement
   Scenario: The duplicate audit never writes
     Given the python schema holds bookings with repeated client references
     When the duplicate-audit CronJob runs
     Then it reports the duplicate count
     And the row counts in every table are unchanged
   ```

5. **OpenTelemetry in the Python stack, the collectors, lgtm and the dashboard.**

   ```gherkin
   @rule-G0
   Scenario: A keyed booking leaves one trace with its database work
     Given the observability overlay is on for the python stack
     When a client books a session with an idempotency key
     Then one trace shows the HTTP request span
     And the trace shows the database spans inside it
   ```

   ```gherkin
   @spec-run-matrix
   Scenario: The dashboard shows which stack is under test
     Given the observability overlay is on
     When the matrix scales python to 0 replicas
     Then the ready replicas panel shows python at 0
   ```

   ```gherkin
   @contract-8
   Scenario: Telemetry is off unless the overlay switches it on
     Given the python Deployment from infra/k8s/python.yaml
     When the contract tests run against the python stack
     Then every contract test passes
     And the python pod exports no telemetry
   ```

6. **The Istio ambient overlay: install, enrolment, STRICT mTLS, AuthorizationPolicy, gateway, waypoint and routes.**

   ```gherkin
   @rule-G2
   Scenario: A mesh retry of a keyed booking replays it
     Given the mesh retries /v2/bookings on connection reset
     When the reply to a committed keyed booking is reset
     Then the mesh sends the request again with the same key
     And the database holds one booking for that client reference
   ```

   ```gherkin
   @contract-2
   Scenario: The control group gets no mesh retries
     Given the route rules for /naive/bookings are applied
     When the reply to a committed naive booking is reset
     Then the mesh does not send the request again
     And the database holds one booking for that client reference
   ```

   ```gherkin
   @rule-G7
   Scenario: Postgres refuses a workload with the wrong identity
     Given STRICT mTLS and the postgres AuthorizationPolicy are applied
     When a pod running as the otel-agent service account connects to postgres
     Then the connection is refused
   ```

7. **The same objects, instrumentation and policies for .NET and Java (G8).**
8. **README section and versions.md entries** for every chart, image and package actually used.

## 6. Versions checked on 2026-10-15

| Component | Version | Source |
| --- | --- | --- |
| Istio | 1.31 is current; the docs footer shows 1.31.1 | [istio.io k3d guide](https://istio.io/latest/docs/setup/platform-setup/k3d/), [ambient prerequisites](https://istio.io/latest/docs/ambient/install/platform-prerequisites) |
| opentelemetry-api, -sdk, -exporter-otlp-proto-grpc | 1.45.1 (2026-10-06, Python 3.14 classifier) | PyPI JSON API |
| opentelemetry-instrumentation-fastapi, -asyncpg | 0.66b1 (2026-10-06, Python 3.14 classifier) | PyPI JSON API |
| OpenTelemetry Collector contrib | v0.163.0 is the newest release listed | [newreleases.io](https://newreleases.io/project/github/open-telemetry/opentelemetry-collector-contrib/release/v0.154.0) |
| k8sattributes processor | v1.0.0 (stable), announced 2026-09-16 | [opentelemetry.io blog](https://opentelemetry.io/blog/2026/k8s-attributes-processor-v1/) |
| grafana/otel-lgtm | for development, demos and testing; ships a Kubernetes manifest | [Grafana docs](https://grafana.com/docs/opentelemetry/docker-lgtm.md) |
| k3s NetworkPolicy | enforced by default (embedded kube-router controller) | [docs.k3s.io](https://docs.k3s.io/networking/networking-services) |

Not verified from this session: container image tags (Docker Hub was unreachable) and the Gateway API CRD
version. Both get checked and recorded in `versions.md` when they are built.

## 7. Risks

- **NodePort sources under NetworkPolicy.** Host traffic reaches pods from the node's address. If the allow rules miss
  it, k6, the harness and the contract tests lose access. Prove this with the contract tests before anything else.
- **STRICT mTLS rejects the host's plain HTTP.** D4 decides whether host traffic goes through the gateway or the
  NodePorts stay PERMISSIVE.
- **Mesh retries on the naive endpoint** would create the duplicates the control group is meant to show, but from
  the mesh rather than the client. `/naive/bookings` gets `attempts: 0`.
- **Measurement drift.** The SDK, ztunnel and the waypoint add work to every request. Keep the overlays off for the
  54-run matrix (D2), and record whether they were on in `versions.md`.
- **Resources.** istiod, ztunnel, the collectors and lgtm share the k3d node with the measured stack. Check their CPU
  and memory on the dashboard before any measured run with the overlays on.
