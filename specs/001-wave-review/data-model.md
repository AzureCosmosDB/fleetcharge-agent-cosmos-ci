# Data Model: Wave Review

**Status**: Implemented typed models and complete fixtures; tested against the real emulator.

## Containers and identity

| Container | Partition key | Identity convention |
|---|---|---|
| `depots` | `/depotId` | `policy-<depotId>` |
| `routes` | `/depotId` | Wave ID and route ID; distinguish `type=deliveryWave` / `type=route` |
| `vehicles` | `/depotId` | `vehicle-<vehicleId>` |
| `chargers` | `/depotId` | Charger ID; same ID can exist in different depots |
| `telemetry` | `/vehicleId` | Unique reading ID within a vehicle partition |
| `recommendations` | `/depotId` | `review-` + lowercase SHA-256 of UTF-8 deliveryWaveId |

All documents have nonempty `id` and correct partition property. Ownership/reference mismatches are errors. Do not assume an ID is globally unique. The depot partition plus hashed wave identity defines audit identity.

## Required fields and validation

| Document type | Required domain fields |
|---|---|
| Depot policy | `depotId`, `type`, `timezone`, `minimumBatteryBufferPercent` (0..100), `telemetryMaxAgeMinutes` (30), `chargerReservationWindowMinutes` (45), `allowRouteSwap` (false), `allowPartialCharge` (false) |
| Delivery wave | `depotId`, `type`, `startTime` (aware timestamp), nonempty distinct `routeIds`, `status=planning` |
| Route | `depotId`, `type`, `deliveryWaveId`, `assignedVehicleId`, `requiredBatteryPercent` (0..100), `weatherAdjustmentPercent` (0..100) |
| Vehicle | `depotId`, `type`, `vehicleId`, `status` (`available` or `unavailable`), `maintenanceHold`, `connectorType`, `maxChargeKw` (>0), `usableBatteryKwh` (>0), `batteryPercent` (summary, 0..100), `assignedRouteId` |
| Telemetry | `vehicleId`, `depotId`, `type`, `observedAt` (aware), `batteryPercent` (0..100) |
| Charger | `depotId`, `type`, `chargerId`, `status` (`available`, `occupied`, `offline`), `connectorType`, `maxKw` (>0), `reservations` of vehicle/start/end |
| Recommendation | `depotId`, `type=chargingRecommendation`, `deliveryWaveId`, `reviewedAt`, `rulesVersion`, `decisionHash`, `inputHash`, validated response payload, `evidenceRecords`, `sourceVersions` |

Charge efficiency is a fixed rules-version constant of 0.90, not an invented model parameter. Reject NaN/infinity, nonpositive duration, invalid interval ordering, duplicate routes, duplicate assigned vehicle across routes, or wave/route/vehicle reference disagreement. JSON booleans are not numbers. Parse observation times before comparison, not by original offset-bearing strings.

## Complete golden fixture

| Container | Document | Key scenario values |
|---|---|---|
| depots | `policy-SEA-01` | SEA-01; America/Los_Angeles; 12-point buffer; 30-minute freshness; 45-minute max charge |
| depots | `policy-PDX-02` | Explicit ownership fixture; not consumed by SEA-01 |
| routes | `wave-2026-10-19-1400` | SEA-01; 14:00 -07:00; route-77 and route-88 |
| routes | `route-77` | SEA-01; van-042; 64-point requirement; +6-point weather |
| routes | `route-88` | SEA-01; van-088; 40-point requirement; +0 weather |
| vehicles | `vehicle-van-042` | SEA-01; available; no hold; CCS; 150 kW; 100 kWh; summary 95%; route-77 |
| vehicles | `vehicle-van-088` | SEA-01; available; no hold; CCS; 150 kW; 100 kWh; summary 90%; route-88 |
| vehicles | `vehicle-van-099` | SEA-01; maintenance hold; 92%; otherwise valid; unassigned in golden fixture (assignedRouteId null permitted only when not in the wave) |
| telemetry | `telemetry-van-042-old` | van-042; SEA-01; 11:00 -07:00; 92% |
| telemetry | `telemetry-van-042-latest` | van-042; SEA-01; 12:20 -07:00; 58% |
| telemetry | `telemetry-van-088-latest` | van-088; SEA-01; 12:20 -07:00; 90% |
| telemetry | `telemetry-van-099-latest` | van-099; SEA-01; 12:20 -07:00; 92% |
| chargers | `charger-fast-03` | SEA-01; available CCS; 150 kW; no reservations |
| chargers | `charger-fast-01` | SEA-01; occupied CCS; 150 kW; reserved 12:15..13:10 |
| chargers | `charger-fast-03` | PDX-02; available CCS; 350 kW; no reservations |

All timestamps are on 2026-10-19. Fixtures are explicit JSON with stable IDs, not random generation. SDK metadata such as `_etag` comes from reads, not the fixture.

## Scenario variants

Each integration test starts from its own golden database and applies only its named change:

- **maintenance**: route-88's assigned vehicle becomes van-099; vehicle-van-099 assignedRouteId becomes route-88; van-088 is unassigned. Held vehicle gets no charge even at high battery.
- **stale/missing/future telemetry**: replace or remove readings within the isolated database to exercise explicit failures; never mutate a shared baseline.
- **freshness boundary/tie**: use 12:00 readings (valid at 12:30), 11:59:59 (stale), and equal observation times with distinct IDs.
- **charger constraints**: insert offline/incompatible/reserved candidates and boundary reservations; compute feasibility from the same clock.
- **changed-input review**: change latest battery from 58% to 90%; next review becomes `noAction` with the same audit ID and changed hash.
- **ownership mismatch**: insert a PDX telemetry record in the van-042 partition; the review rejects mixed ownership, not merely an unexpected selected reading.

## Evidence and audit

Public `evidence` remains a sorted unique list of document IDs for compatibility with the outline. Audit `evidenceRecords` contains `{container, id, partitionKey}` entries sorted by that tuple; it is authoritative provenance. The trace additionally records tool names/arguments and all returned records so rejected candidates can be inspected without citing them as supporting evidence.

Golden evidence IDs are policy-SEA-01, wave-2026-10-19-1400, route-77, route-88, vehicle-van-042, vehicle-van-088, telemetry-van-042-latest, telemetry-van-088-latest, and charger-fast-03. PDX records, old telemetry, and occupied/rejected chargers do not appear.

`sourceVersions` stores container, ID, partition and `_etag` for consumed evidence. `inputHash` hashes the normalized consumed domain input values and review time/rules version; exclude `_etag` and other SDK metadata. `decisionHash` hashes the canonical response before adding `decisionHash` itself. Thus reseeding identical domain values does not change the normalized response.

Use UTF-8 SHA-256 and canonical JSON with sorted object keys, compact separators, UTC timestamps and normalized decimal values. Define the normalization helper once and cover it with unit tests. Exclude diagnostic request IDs, timings and storage metadata from the response hashes.

Upsert updates one record. A response describes that request's acknowledged write, not an immutable historical event or a guarantee another request has not already superseded it.
