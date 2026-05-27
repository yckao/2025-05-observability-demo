# Workshop Refactor Design

Date: 2026-05-27

## Goal

Refactor the observability demo into a polished 60–90 minute instructor-led workshop for a mixed audience. The instructor runs the shared stack and hidden fault scenarios. Students use a student UI and Grafana to investigate symptoms with metrics, logs, traces, and profiles.

## Decisions

- Optimize for full workshop polish, not only code cleanup or only documentation.
- Target a 60–90 minute instructor-led lesson.
- Assume a mixed audience: beginner-friendly main path with optional deeper challenges.
- Assume the instructor runs the shared stack.
- Use only two student-facing public surfaces:
  - Student UI on port `8080`.
  - Grafana dashboard portal on port `3000`.
- Keep Pyroscope internal to Docker Compose and teach profiles through Grafana's Pyroscope datasource and panels. Do not require a separate public Pyroscope URL.

## Workshop Structure

Add a workshop documentation spine:

- `docs/workshop/instructor-guide.md`
  - Timed 60–90 minute runbook.
  - Setup and baseline checks.
  - Scenario order.
  - Instructor prompts.
  - Expected observations.
  - Recovery and reset steps.
- `docs/workshop/student-worksheet.md`
  - Beginner-friendly investigation path.
  - Optional deeper challenges for experienced students.
  - Spaces for observations and hypotheses.
- `docs/workshop/scenarios/`
  - One scenario card per named scenario.
  - Each card includes instructor setup, student-visible symptoms, investigation hints, expected signals, and reset guidance.

Update `README.md` into a concise landing page with quick start, URLs, common commands, and links to the workshop docs. Move detailed teaching flow out of the README and into the instructor guide.

## Lesson Flow

The main class flow is:

1. Orient students to the app, telemetry stack, and dashboards.
2. Start normal/background traffic.
3. Read baseline RED and USE signals.
4. Run a hidden instructor scenario.
5. Students investigate in Grafana using the worksheet.
6. Discuss hypotheses and expected evidence.
7. Correlate metrics, logs, traces, and profiles.
8. Optionally run a harder scenario for experienced students.
9. Reset to baseline and recap.

## Scenario Workflow

Keep fault controls hidden from the student port. Add a named scenario layer for repeatable instructor use:

- `make scenario-list` lists available workshop scenarios.
- `make scenario-start NAME=<scenario>` applies a preset.
- `make scenario-status` summarizes instructor-side fault state.
- `make scenario-reset` clears all replicas and returns to baseline.

Initial scenario set:

1. `checkout-latency`
   - A checkout path on one backend replica is slow.
   - Students use request duration, route, replica, logs, and traces.
2. `products-errors`
   - Product API requests intermittently fail with 5xx responses.
   - Students use error rate, logs, and trace IDs.
3. `cpu-hot-replica`
   - One backend replica burns CPU.
   - Students connect container utilization to profile evidence in Grafana.
4. `db-slowdown`
   - Optional deeper challenge focused on database wait symptoms.

Scenario commands must include clear failure messages and always provide a reset path.

## Cloudflare-Friendly Public Surface

Students should only need two public URLs:

- Student UI: port `8080`.
- Grafana: port `3000`.

Remove browser-facing hardcoded links to `localhost:4040`. Replace them with instructions and dashboard links that keep students inside Grafana for profile exploration.

Pyroscope stays available on the Docker network for ingestion and for Grafana datasource queries. It does not need a separate public tunnel.

Where practical, make non-student services internal-only by default:

- Prometheus
- Loki
- Tempo
- Pyroscope
- CockroachDB UI
- Alloy

If local debugging access is still useful, add it later as an explicit debug profile or documented optional override rather than exposing those ports in the default workshop path.

## Light Code and Infrastructure Refactor

Keep the runtime topology recognizable for teaching:

- Docker Compose remains the orchestration layer.
- The load balancer continues to expose the student app and hidden instructor port locally.
- Frontend and backend remain separate FastAPI services.
- Fault logic remains backend-specific.

Targeted maintainability improvements:

- Extract duplicated Python telemetry, logging, and request-metrics helpers into a small shared package copied into both frontend and backend images.
- Keep app-specific routes and fault behavior in their current services.
- Avoid deep Docker Compose templating unless needed. Existing YAML anchors are acceptable; too much indirection would make the lab harder to explain.
- Add fast validation via `make check`.

## Student and Instructor Data Flow

Student flow:

1. Open the student UI on port `8080`.
2. Generate traffic from the UI or observe background traffic.
3. Open Grafana on port `3000`.
4. Start at `00 Start Here`.
5. Follow worksheet prompts through metrics, logs, traces, and profile panels.

Instructor flow:

1. Start the stack.
2. Start consistent traffic.
3. Confirm baseline dashboards look healthy.
4. Run a named scenario.
5. Facilitate investigation using the instructor guide.
6. Reset the scenario.
7. Repeat or move to recap.

## Error Handling and Recovery

- Scenario commands check that the stack is reachable before applying faults.
- Scenario commands report missing command-line dependencies clearly.
- Every scenario card includes a reset command.
- `make scenario-reset` resets all backend replicas.
- Student-facing routes continue to hide `/admin` and `/api/fault` behavior.
- Workshop docs include a short recovery section for common failures: stack not up, traffic generator not running, dashboards empty, or stale active faults.

## Validation and Tests

Add a fast test/check layer that does not require the full observability stack to boot:

- Verify required Make targets exist.
- Verify scenario definition names and referenced scripts are valid.
- Verify student-facing Nginx routes hide instructor-only endpoints.
- Verify dashboard links no longer point students to `localhost:4040`.
- Verify README links to workshop docs.
- Verify required workshop docs and scenario cards exist.

Add `make check` as the primary local validation command.

Full-stack smoke testing remains documented as a manual verification path because the observability stack is slower and environment-dependent.

## Non-Goals

- Do not build a new web application or replace Grafana dashboards.
- Do not require students to run Docker locally for the main path.
- Do not expose Pyroscope as a separate public URL.
- Do not redesign all dashboards before the workshop flow is usable.
- Do not make large Compose abstractions that obscure the teaching topology.

## Open Implementation Notes

- The shared Python helper package should be small and boring. It should reduce duplication without changing service behavior.
- The scenario layer can start as shell scripts plus a simple scenario definition file if that keeps dependencies low.
- Cloudflare Tunnel setup should be documented as expected public URLs rather than hardcoding a specific domain.
