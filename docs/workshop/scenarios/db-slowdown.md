# Scenario: db-slowdown

## Instructor setup

```bash
make scenario-reset
make scenario-start NAME=db-slowdown
```

## Story for students

Checkout is slow, but CPU is not the most convincing explanation.

## Student-visible symptoms

- Checkout latency rises on one backend replica.
- Error rate remains near baseline.
- Traces show time spent around backend checkout and database work.

## Investigation path

1. Open `01 Operations Overview` and identify latency as the main symptom.
2. Open `03 Checkout Journey` to follow frontend, backend, and database spans.
3. Compare CPU utilization with request duration.
4. Use logs and traces to decide whether this looks CPU-bound or wait-bound.

## Expected evidence

- `backend-2` is the affected replica.
- `/api/checkout` latency rises.
- CPU is not the strongest signal.
- Trace timing points toward waiting around checkout database work.

## If students get stuck

Ask: If latency is high but CPU is not high, what kind of waiting could explain it?

## Reset

```bash
make scenario-reset
```
