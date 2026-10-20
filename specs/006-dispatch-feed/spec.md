# Dispatch feed and grounded briefing

Depot operators publish the current pickup bay through a dispatch feed. Drivers
ask the agent where to collect their dispatch paperwork. Returning an old bay
after an update is a functional failure that CI must detect before deployment.

## Requirements

- FR-001: `POST /feeds/dispatch-updates` accepts only depotId, updateId and
  pickupBay. Persist a validated current snapshot in `dispatchUpdates`,
  partitioned by depotId. Return the acknowledged document. This local sample
  accepts the last successfully written snapshot, not an ordered event stream.
- FR-002: `POST /agent/ask-dispatch` accepts depotId and question. Point-read
  `current-dispatch` from that depot's partition and pass the actual stored
  values to real Ollama through Agent Framework. Return a generated sentence,
  pickupBay and updateId. Both structured fields must match the source, and
  the sentence must contain the exact bay and update reference.
- FR-003: Reject missing/malformed source, invalid feed input, inference errors
  and mismatched model output explicitly. Never synthesize or repair an answer.
  Keep the existing vehicle and charging review endpoints unchanged.
- FR-004: Seed SEA-01 with BAY-2 and PDX-02 with BAY-99. Test scoped ingestion,
  replacement, validation and missing source against the real emulator. In the
  actual-model suite ask before and after publishing update dispatch-007/BAY-7;
  verify independent SDK storage and raw provider context, then exact source
  fields and literal values in the generated answer.
- FR-005: Document installation, configuration, startup, all endpoints, examples,
  tests, reports and limitations in the public README. Verify packaging and
  actual HTTP startup, commit without the article/.env, pass branch CI, merge,
  and verify main. CD/deployment remains future work.

## Acceptance

The same question returns BAY-2/dispatch-001 before ingestion and
BAY-7/dispatch-007 afterward. A wrong bay/reference fails instead of being
rewritten. All 20 real inference calls, component checks, build and runtime
smoke checks pass. The article remains local.
