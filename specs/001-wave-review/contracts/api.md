# API Contract: Review Delivery Wave

**Status**: Implemented; actual HTTP 200 and independent persisted audit read-back verified.
**Operation**: `POST /agent/review-delivery-wave`
**Content type**: `application/json`

## Request

```json
{
  "depotId": "SEA-01",
  "deliveryWaveId": "wave-2026-10-19-1400"
}
```

Exactly these fields are accepted. Both are strict strings matching `^[A-Za-z0-9_-]{1,128}$`; no coercion, trimming or unknown fields. Clock and model mode are server configuration, not caller-controlled request fields. A malformed JSON document is a 422 input error.

## Success: HTTP 200

Golden shape below uses a symbolic hash to illustrate the field; implementation computes a 64-character lowercase hexadecimal hash.

```json
{
  "depotId": "SEA-01",
  "deliveryWaveId": "wave-2026-10-19-1400",
  "recommendation": "rebalanceCharging",
  "assignments": [
    {
      "vehicleId": "van-042",
      "chargerId": "charger-fast-03",
      "start": "2026-10-19T12:30:00-07:00",
      "durationMinutes": 11,
      "reason": "Battery state is below route requirement with safety buffer"
    }
  ],
  "routeRisks": [
    {
      "routeId": "route-77",
      "vehicleId": "van-042",
      "risk": "batteryShortfall"
    }
  ],
  "evidence": [
    "charger-fast-03",
    "policy-SEA-01",
    "route-77",
    "route-88",
    "telemetry-van-042-latest",
    "telemetry-van-088-latest",
    "vehicle-van-042",
    "vehicle-van-088",
    "wave-2026-10-19-1400"
  ],
  "reviewedAt": "2026-10-19T12:30:00-07:00",
  "auditId": "review-<sha256-of-deliveryWaveId>",
  "decisionHash": "<computed-sha256>"
}
```

The outline's original core fields remain. `reviewedAt`, `auditId`, and `decisionHash` make the demo clock and audit result inspectable. Evidence is a string array publicly; source partition provenance is in the audit/test trace.

### Deterministic ordering and enums

- `recommendation`: `noAction`, `rebalanceCharging`, `unableToSchedule`.
- Assignments: ascending `(start instant, vehicleId, chargerId)`.
- Risks: ascending `(routeId, vehicleId, risk)`.
- Evidence: ascending unique document IDs.
- `risk`: `maintenanceHold`, `vehicleUnavailable`, `energyRequirementUnachievable`, `batteryShortfall`, `noFeasibleCharger`.
- Held vehicles emit only `maintenanceHold`; unavailable vehicles emit only `vehicleUnavailable`; target >100% emits only `energyRequirementUnachievable`. Otherwise battery shortfall emits `batteryShortfall` and, when no feasible assignment exists, `noFeasibleCharger` as well.
- Healthy wave: `noAction`, empty assignments/risks, populated evidence/audit.
- Mixed feasible/unserviceable wave: `unableToSchedule`, retaining feasible assignments and all applicable risks. This is an operational result, not HTTP failure.
- Maintain the fixed golden assignment reason exactly as shown. A decision does not remove the original battery-shortfall risk merely because charging is recommended.

Response models are strict and disallow extra fields; percentages, powers, intervals, and document ownership are validated before response construction. Do not expose raw SDK metadata or exception bodies.

## Error responses

All errors use this envelope, including request validation (override framework defaults consistently):

```json
{
  "error": {
    "code": "sourceDataInvalid",
    "message": "Latest valid telemetry is unavailable for vehicle van-042.",
    "retryable": false
  }
}
```

| HTTP | Code | Trigger | Audit behavior |
|---|---|---|---|
| 422 | `invalidRequest` | Invalid JSON, types, IDs or unknown request fields | No write |
| 404 | `waveNotFound` | Requested wave is absent in the requested depot | No write |
| 409 | `sourceDataInvalid` | Missing policy/reference/eligible telemetry; invalid values; inconsistent depot or references; departure not after review time; wrong wave status | No write |
| 500 | `agentExecutionFailed` | Unexpected tools/turns, proposal mismatch, exhausted script, invalid terminal content or other framework failure | No write before persistence; may already exist after an acknowledged write |
| 503 | `dataStoreUnavailable` | SDK connection/timeout/service errors or failed write | Write outcome can be unknown on transport failure |
| 504 | `reviewTimedOut` | Review exceeds 60-second application deadline | Write outcome can be unknown if persistence started |

Missing expected source documents are translated explicitly; do not catch every SDK exception as a missing record. Log structured operation/tool/partition context and exception type without keys/tokens. Unexpected failures retain an explicit error log and a sanitized 500 response rather than a fake operational result.

The model-turn limit is 20; exceeding it maps to `agentExecutionFailed`. Cancel in-flight operations where supported, but do not claim a response timeout rolls back Cosmos DB. The write tool is the last domain operation. After a successful write, the only allowed turn is a terminal acknowledgement; if that terminal turn fails, the audit is retained and the error log indicates persistence had completed.

## Audit replacement and concurrency

The audit identity is deterministic per depot/wave. Every valid review recomputes the result, then upserts that identity. Identical reviews are idempotent in stored identity and normalized contents, not in invocation count. Changed inputs replace it. Concurrent reviews are last-write-wins; a response's hash may already be superseded in storage.

For ten sequential identical requests, assert one audit document and identical responses. For two concurrent equivalent requests, assert both succeed and the final audit has that same validated decision. No guarantee is made for concurrent different snapshots beyond one final identity with one complete validated payload.
