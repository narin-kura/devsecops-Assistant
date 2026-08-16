# DevSecOps Assistant — Roadmap

Vision: **a one-stop-shop DevOps/DevSecOps assistant** — a coordinator you
talk to in chat, backed by a *group of agents*, each a specialist that
covers one full slice of the platform lifecycle and can actually act (scan,
generate, provision, remediate), not just advise. In scope end-to-end:

1. Onboarding new applications to any tool
2. Automation frameworks — create, and keep updated
3. Security scans, remediation, and action items
4. Tracking exceptions (risk waivers/acceptances)
5. Containerization support
6. Infra management
7. Cloud platform management
8. Networking
9. Secret management
10. Certificate management
11. DNS and hostname management
12. Developer support — reading logs, root-causing issues
13. Performance issue identification and suggestions

This is comparable in ambition to an internal developer platform (think
Backstage/Port/Cortex) with an agentic layer on top — a multi-year build, not
a sprint. The point of the multi-agent architecture is that it doesn't need
to be built as one monolith: each numbered item above becomes one specialist,
added to the coordinator's roster one at a time, without the earlier
specialists needing to change.

Status as of 2026-08-16: Phase 0 and Phase 1 are done — CI Onboarding
(item 1, 7 CI tools) is live behind the coordinator/chat surface with a
shared registry. Phase 2 is now done in full — Containerization (item 5)
and Automation Frameworks (item 2) are both shipped; see Phase 2 below for
detail. K8s/Helm generation (split out of Containerization to keep it
shippable) is the one loose end before Phase 3 (Security & governance).

## Interface direction (decided 2026-08-16)

- **Primary interface: a chat surface**, not flags — describe what you need,
  the assistant asks follow-ups and acts.
- **It's a *group* of agents.** A coordinator delegates to specialist agents,
  one per domain (the 13 items above map roughly 1:1 to specialists). This
  stops being optional at this scope — a single flat toolset covering all 13
  domains would be unmanageable; the coordinator/specialist split is what
  keeps each conversation focused and each specialist's toolset small.
- **It's agentic.** Specialists call tools that actually do the work — scan,
  render, provision, query — the same as the CLI does today, just reached
  through conversation.
- **The CLI stays** as a secondary, scriptable interface. Its functions
  become the tools the agents call — one core, two front doors.

**Recommended build approach (unchanged):** Claude API + Tool Runner, run
locally, not Anthropic's hosted Managed Agents — this tool's job is acting on
things the user has local/direct access to (a project directory, cloud
credentials, internal log systems), which a cloud sandbox doesn't reach.
Revisit only if this becomes a hosted multi-tenant product (Phase 8).

**Delegation depth — not every specialist gets subagents.** The default is
**one level**: coordinator → specialist, full stop. Each extra hop of
delegation re-establishes context from scratch and costs real latency and
money — it's the same reason the model-migration guidance for these Claude
models explicitly warns that agents "delegate more readily" than earlier
ones and need an deliberate cap, not encouragement. So: a specialist gets
its *own* subagents only when its domain genuinely splits into independent,
parallelizable workstreams, not just because it's "a big topic." Concrete
examples where it's earned: the **Cloud Platform** specialist fanning out
AWS/GCP/Azure checks in parallel when a question spans providers; the
**Security Scanning** specialist fanning out SAST/dependency/secret-scan
sub-tasks that don't depend on each other. Examples where it's *not*
earned: **DNS & Hostnames** or **Certs** — narrow domains, sequential work,
one agent handles the whole thing. Add sub-delegation per specialist, as
needed, when its own workload demonstrably justifies it — not as a blanket
rule applied to all thirteen up front.

**Autonomy model — a team, not just a chat window.** The end state isn't
"wait for a human to ask" — it's specialists that behave like a real
DevSecOps team: scheduled scans, monitoring, and proactive action items,
the same way a team has on-call rotations and dashboards instead of only
reacting to tickets. Concretely, once enough specialists exist to make it
worthwhile: a lightweight local scheduler wakes specific specialists on a
cadence — nightly security scans, daily cert/secret expiry checks, periodic
infra drift detection, continuous or interval-based log/performance
monitoring — and those runs write findings to the shared registry exactly
like an interactive run would, then notify a human (the chat surface first,
Slack/email later) so the finding doesn't sit invisible until someone
happens to ask. This has one hard consequence for how every specialist gets
built, starting now: **design each specialist's actions to be safe to run
unattended from day one** — idempotent, side-effect-aware, and respecting
the safety model below (autonomous *read/scan/detect/report* can run and
notify freely; autonomous *mutate* still stops and asks a human, no
exceptions, scheduled or not). Retrofitting "safe to run without a human
watching" onto a specialist built assuming one always is would mean
redoing it. The scheduler itself is a dedicated phase (below) — it needs
several specialists and the registry to already exist to be worth
building — but the unattended-safe design constraint applies from Phase 1.

**How specialists link — the shared registry.** Without a deliberate
mechanism, thirteen specialists are just thirteen silos with a chat UI in
front — and worse, a coordinator delegating to a specialist doesn't
automatically hand it the rest of the conversation's context (each
delegated task is scoped to what the coordinator explicitly includes in the
handoff). What actually connects them is a small, shared **registry/catalog**
— a single local source of truth about what exists: applications/services,
keyed by an ID, and everything every specialist has done to or learned about
each one. Concretely:

- Onboarding registers an app (name, repo, language, owning team).
- Automation/containerization link the frameworks and container specs they
  generated back to that app.
- Security scanning looks up an app's registry entry to know what's there,
  and writes findings and remediation status back against it, linked.
- Exceptions tracking is entries in the same registry, linked to the app and
  the specific finding they waive.
- Infra/Cloud/Networking link the resources they provision to the app that
  owns them.
- Secrets/Certs/DNS link what they manage the same way — which secret,
  which cert, which record belongs to which app.
- Log/Performance specialists, when investigating an app, pull its *whole*
  registry entry — infra it runs on, recent security exceptions, cert/DNS
  state — not just logs in isolation. This is what makes "why is
  checkout-service slow" answerable by reasoning across domains instead of
  guessing from telemetry alone.
- The coordinator uses the registry to brief a specialist with cross-domain
  context at handoff time — since a delegated specialist doesn't inherit the
  coordinator's full conversation, the registry is what closes that gap.

Practically: start this as something as simple as one JSON file or a small
SQLite DB (`.devsecops/registry.*`) that every specialist's tool surface can
read and write, alongside its domain-specific actions. Introduce it in
**Phase 1**, with the first specialist, not later — retrofitting cross-
linking after twelve more specialists exist would be far more painful than
building every specialist against a registry contract from the start. Every
phase below that adds a specialist implicitly includes "register/link its
work in the catalog" as a standing requirement, not a separate task.

**Safety model — this matters more as scope grows.** Items 1–5 (onboarding,
automation, security scanning, containerization) mostly act on local files —
low blast radius, safe to let a specialist act with light confirmation.
Items 6–11 (infra, cloud, networking, secrets, certs, DNS) act on **live
infrastructure with real credentials** — a mutating action here (deleting a
DNS record, rotating a secret, changing a security group) is a different
risk class entirely. Every specialist in that group needs a confirm-before-
mutate gate by design (mirroring the "ask before destructive/hard-to-reverse
actions" principle this assistant already needs to follow generally) —
read/inspect/suggest can be autonomous, anything that changes live state
needs an explicit human go-ahead, every time, no exceptions baked in later.

## Phase 0 — Stabilize the foundation
*Land what's already built before adding more.*

- Wire `onboard_cli` into [core/cli.py](core/cli.py) as a real subparser.
- Commit the pending work: `devsecops_assistant/` → `core/` rename, the
  `ci_onboard` module, the 6 CI templates, README rewrite.
- Add automated tests for `detector.py` and `profiles.py`.
- Decouple `onboard()`'s logic from CLI printing/arg-handling so the same
  function is callable from `argparse` *and* an agent tool wrapper.

## Phase 1 — The multi-agent core: coordinator + first specialist
*Prove the architecture with one working specialist before building twelve more.*

- Coordinator agent (Claude Opus): mostly delegation, plus enough judgment
  to ask clarifying questions before handing off.
- **App/Tool Onboarding specialist** (item 1, generalized beyond CI): wraps
  `detector.py` + `profiles.py` + template rendering. Starts with CI/CD, but
  "starts with CI/CD" means **broad CI/CD tool coverage is itself a near-term
  priority, not a solved problem to move past.** Today's `CI_TOOLS` mapping
  in [onboard.py](core/modules/ci_onboard/onboard.py) covers GitHub Actions,
  GitLab CI, Jenkins, Azure DevOps, Bitbucket, and CircleCI — that's a
  reasonable start but not "the majority of tools" yet. **Harness is a
  known, named gap** (CD/GitOps-oriented, distinct enough from the classic
  CI runners above that it likely needs its own pipeline profile, not just
  another template) — add it in this phase. Also worth covering before
  calling CI/CD "done": TeamCity, Buildkite, Drone, AWS CodePipeline/
  CodeBuild, Google Cloud Build. Only once CI/CD breadth is solid does the
  specialist grow into onboarding an app to *other* tool categories
  (artifact registries, monitoring agents, ticketing/chatops) — same
  specialist, bigger toolset, but CI/CD coverage comes first.
- Chat surface for v1: a terminal chat REPL. Simplest thing that proves
  coordinator → specialist → real filesystem action end-to-end.
- **Introduce the registry here, not later** (see "How specialists link"
  above): the onboarding specialist's first write is registering the app it
  just onboarded. Every specialist added in later phases builds against this
  same contract from day one instead of bolting it on after the fact.

## Phase 2 — Scaffolding & automation wave
*Extends what Phase 1 proved, still local-file-scoped.*

- **Containerization specialist** (item 5) — **done, 2026-08-16.** Dockerfile
  + `.dockerignore` (+ optional `docker-compose.yml`) generation, reusing
  the same detect-project-profile approach as the onboarding specialist:
  `core/modules/containerize/` (`container_profiles.py` for smart defaults,
  `containerize.py` orchestrator, `agent_tools.py`, Jinja templates),
  `core/agents/specialists/containerization.py`, wired into the coordinator
  and the CLI (`devsecops-assistant containerize`). Covers Python, JS/TS,
  Java, Kotlin, Go, Rust, C#/.NET, and Ruby, with multi-stage builds for the
  compiled languages so the runtime image doesn't ship build tooling; an
  unrecognized language still gets a valid (if manual-review-needed)
  Dockerfile rather than erroring. Registers/links `containerization` in
  the shared registry the same way CI onboarding links `ci_cd`. K8s
  manifest / Helm chart generation was scoped out of this pass — still
  open, see below.
- **Automation Frameworks specialist** (item 2) — **done, 2026-08-16.**
  Interpreted "automation frameworks — create, and keep updated" as the
  recurring dev-workflow automation every project needs, not a new IaC
  domain (that's Infra Management, Phase 4): `core/modules/automation/`
  (`ecosystem_profiles.py` mapping language+package-manager to Dependabot's
  `package-ecosystem` identifiers, `automate.py` orchestrator reusing
  `ci_onboard/profiles.py`'s `get_profile()` for install/build/test/lint
  commands rather than re-deriving them, `agent_tools.py`, Jinja templates),
  `core/agents/specialists/automation.py`, wired into the coordinator
  (`delegate_to_automation`) and the CLI (`automate` subcommand,
  `--targets` to pick a subset). Generates three artifacts: a `Makefile`
  (install/build/test/lint/clean), a `.github/dependabot.yml` (covers the
  detected language ecosystem, plus `docker`/`github-actions` ecosystems
  when a Dockerfile or workflow already exists — the literal "keep
  [dependencies] updated" reading, since Dependabot runs on its own
  schedule once committed), and a `.pre-commit-config.yaml` (baseline
  hygiene hooks always included — trailing-whitespace, end-of-file-fixer,
  check-merge-conflict — plus local lint/test hooks when detected).
  Dependabot generation is skipped (not an error) when nothing recognizable
  exists to point it at — same never-hard-fail posture as Containerization.
  Links an `automation` entry in the shared registry, same contract as
  `ci_cd` and `containerization`.
- **Still open:** K8s manifest / Helm chart generation (originally bundled
  with Containerization, deferred to keep that pass shippable in one
  session — same detect-project-profile approach would extend naturally;
  this is now the one remaining loose end from Phase 2).

## Phase 3 — Security & governance wave

- **Security Scanning + Remediation specialist** (item 3) — SAST,
  dependency, and secret scanning (deferred from the original roadmap,
  now scheduled here), plus actually proposing or opening remediation
  PRs — "action items" means it closes the loop, not just reports.
- **Exceptions Tracking specialist** (item 4) — a lightweight system of
  record for accepted risks/waivers: what was accepted, why, by whom, and
  when it expires, with reminders as expiry approaches. This is the first
  specialist that needs persistent state beyond the local filesystem
  (a small store, not just files it renders and forgets).

## Phase 4 — Infra & platform wave
*First wave touching live infrastructure — safety model above applies.*

- **Infra Management specialist** (item 6) — provisions, drift-detects, and
  updates IaC (this absorbs the earlier standalone "infra scaffolding"
  idea — same Terraform work, framed as ongoing management rather than a
  one-time render).
- **Cloud Platform specialist** (item 7) — AWS/GCP/Azure account and
  service management, cost visibility.
- **Networking specialist** (item 8) — VPCs, subnets, load balancers,
  firewalls/security groups.

## Phase 5 — Identity & edge wave

- **Secrets Management specialist** (item 9) — Vault / Secrets Manager /
  KMS integration, rotation tracking and reminders.
- **Certificate Management specialist** (item 10) — TLS lifecycle,
  issuance, renewal alerts (ACM, Let's Encrypt, etc.).
- **DNS & Hostnames specialist** (item 11) — zone management; a natural
  extension of the existing `akamai_engine` module, which already touches
  CDN/hostnames.

## Phase 6 — Developer support & observability wave
*Different in kind from everything above — read-only against live systems.*

- **Log Analysis / Root Cause specialist** (item 12).
- **Performance specialist** (item 13) — reads metrics/traces, suggests
  optimizations.
- These two need integrations with wherever the team's logs/metrics/traces
  actually live (CloudWatch, Datadog, Splunk, Grafana, etc.) — likely the
  first place this project reaches for MCP server connections rather than
  hand-written tool wrappers, since it's read access to third-party
  platforms rather than local files or IaC state. No filesystem writes, no
  mutation — lowest-risk specialists in the roster despite touching
  production data, precisely because they only read.

## Phase 7 — Autonomous operation: heartbeats, tasks, governance, budgets
*Turns the reactive assistant into the "team functioning autonomously" — needs Phases 3-6 done first.*

Reference point: Paperclip (`github.com/paperclipai/paperclip`) models an
agent team as an org — roles, reporting lines, scheduled "heartbeat"
activation, a task queue with atomic checkout, governance/approval
workflows, and cross-provider budget enforcement. The concepts transfer
directly even though we're not adopting its Node/React/Postgres stack —
this project stays Python-native (`core/`), Claude-API-only.

- **Heartbeats, not a continuous process.** A specialist doesn't poll or
  run forever — it wakes on a schedule (cron-like), does bounded work, and
  goes back to sleep. Nightly security scans, daily cert/secret expiry
  checks, periodic infra drift detection, interval-based log/performance
  monitoring are all heartbeats, not daemons.
- **A task queue with atomic checkout, layered on the registry.** The
  registry (Phase 1) is *state* — what exists and what's known about it.
  This adds *work* — a queue of tasks with dependencies, so a scheduled
  security-scan heartbeat and an interactive chat request can't both grab
  the same unit of work, and a remediation task can declare it depends on
  its scan task finishing first.
- **Governance, not just a confirm prompt.** Formalizes the safety model
  from earlier: mutate-class actions go through an approval workflow with
  a record of who approved what, and — where the underlying change is
  reversible (IaC applies, config pushes) — a rollback path, not just a
  yes/no gate in the moment.
- **Budget enforcement, designed in from this phase, not bolted on.**
  Track token/cost spend per specialist and per run against a cap; hard-
  stop rather than silently overrun. This project doesn't have Managed
  Agents' server-side session budgets (we're running the Tool Runner
  locally, per the earlier architecture call), so this is homegrown:
  accumulate `usage` from every Claude API call per specialist run and
  enforce the cap in our own scheduler loop.
- **Org chart, made explicit.** The coordinator/specialist/occasional-
  subagent structure already in this roadmap *is* an org chart — this
  phase is where it's worth naming roles and reporting lines explicitly,
  since that's also the natural place to hang per-role permissions (which
  specialist can act without asking, which always needs governance
  sign-off).
- **Portfolio/multi-project isolation — worth an early nod, not just a
  Phase 9 concern.** Narin runs several projects day to day (this one,
  ArchLens, CareerCompass, NewsToStocks, Kaal). A single local deployment
  managing more than one project's registry/task-queue, cleanly isolated
  per project, is closer to how this tool will actually get used than a
  single-project assumption — keep the registry and task queue scoped per
  project from the start so this isn't a rearchitecture later.
- A notification path so autonomous findings actually reach a human: the
  chat surface at minimum, Slack/email as a natural next step.
- Every specialist scheduled here must already satisfy the "safe to run
  unattended" constraint from Phase 1 — this phase wires up heartbeats,
  the task queue, governance, and budgets; it doesn't retrofit safety into
  specialists that assumed a human was always watching.

## Phase 8 — Distribution & packaging

- `pyproject.toml` with console-script entry points for both the CLI
  (`devsecops-assistant onboard ...`) and the chat surface
  (`devsecops-assistant chat`).
- Document the `ANTHROPIC_API_KEY` / `ant auth login` requirement clearly —
  the chat surface is the primary interface and depends on the Claude API.
- Publish to PyPI / pipx once the chat flow is stable.

## Phase 9 — Productize (stretch)

- Revisit Managed Agents if this ever needs to serve people who won't
  install a CLI — a hosted product can trade "your local directory" for
  "your mounted GitHub repo" without it being a step down.

---
*Sequencing note: this is a proposed order, not a locked one — items 1–5
follow naturally from what already exists; 6–11 are grouped by shared
"touches live infra, needs a confirm gate" risk profile; 12–13 are grouped
because they're read-only and need different (observability) integrations
than anything else in the roadmap. Reshuffle freely if a different domain
matters more sooner. Phase 0 remains the hard prerequisite for all of it —
there's real, working code sitting uncommitted right now.*
