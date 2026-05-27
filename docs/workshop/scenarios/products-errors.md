# Scenario: products-errors

## Instructor setup

```bash
make scenario-reset
make scenario-start NAME=products-errors
```

## Story for students

Some product page requests fail, but the application still responds successfully part of the time.

## Student-visible symptoms

- 5xx error ratio increases for product requests.
- Logs include backend error events with trace IDs.
- Successful traffic continues on other routes and replicas.

## Investigation path

1. Open `01 Operations Overview` and identify errors as the main symptom.
2. Open `02 Service Drilldown` and filter to `backend`.
3. Compare route and status labels.
4. Open logs for backend services.
5. Use a failed request trace ID to inspect the trace.

## Expected evidence

- Error ratio increases for `/api/products`.
- `backend-1` is the affected replica.
- Backend JSON error logs include status `503`.
- Trace IDs from failed responses connect logs to Tempo.

## If students get stuck

Ask: Which route has 5xx responses? Are the failures evenly spread across replicas?

## Reset

```bash
make scenario-reset
```
