#!/usr/bin/env bash
set -euo pipefail
base="${1:-http://127.0.0.1:8001}"
question='{
  "depotId": "SEA-01",
  "question": "Where should drivers collect dispatch paperwork? Include the update reference."
}'

before=$(curl --fail-with-body --silent --show-error --max-time 200 \
  -H 'Content-Type: application/json' \
  --data "$question" "$base/agent/ask-dispatch")
printf '%s\n' "$before" | jq .
printf '%s\n' "$before" | jq -e '
  .pickupBay == "BAY-2" and .updateId == "dispatch-001"
  and (.answer | contains("BAY-2"))
  and (.answer | contains("dispatch-001"))
'

receipt=$(curl --fail-with-body --silent --show-error --max-time 60 \
  -H 'Content-Type: application/json' \
  --data '{"depotId":"SEA-01","updateId":"dispatch-007","pickupBay":"BAY-7"}' \
  "$base/feeds/dispatch-updates")
printf '%s\n' "$receipt" | jq -e '
  .depotId == "SEA-01" and .pickupBay == "BAY-7" and .updateId == "dispatch-007"
'

after=$(curl --fail-with-body --silent --show-error --max-time 200 \
  -H 'Content-Type: application/json' \
  --data "$question" "$base/agent/ask-dispatch")
printf '%s\n' "$after" | jq .
printf '%s\n' "$after" | jq -e '
  .pickupBay == "BAY-7" and .updateId == "dispatch-007"
  and (.answer | contains("BAY-7"))
  and (.answer | contains("dispatch-007"))
'
printf '%s\n' "PASS: the same question now returns BAY-7 / dispatch-007."
