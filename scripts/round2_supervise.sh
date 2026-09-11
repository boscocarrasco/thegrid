#!/usr/bin/env bash
# Keep scripts/round2_finish.sh alive.
#
# Two things kill the driver through no fault of the plan: the desktop dying
# (handled inside the driver) and the session losing its model channel to a
# provider usage block, which takes the whole process tree with it. The driver
# is resumable — already_done() skips completed records and retries the ones
# marked rate_limited — so the correct response to either is to start it again.
# The global spend guard inside the driver still decides when to stop, so this
# loop cannot spend past the cap.
set -u
cd "$(dirname "$0")/.."
LOG=${GRID_LOG:-/tmp/round2}
mkdir -p "$LOG"

for attempt in $(seq 1 40); do
  if grep -q "ALL TIERS ATTEMPTED\|STOP: estimated spend" "$LOG/finish.log" 2>/dev/null; then
    echo "[$(date -u +%H:%M:%S)] driver reported it is finished; supervisor exiting" \
      | tee -a "$LOG/supervise.log"
    exit 0
  fi
  if ! pgrep -f round2_finish.sh >/dev/null; then
    echo "[$(date -u +%H:%M:%S)] driver not running; starting it (attempt $attempt)" \
      | tee -a "$LOG/supervise.log"
    nohup bash scripts/round2_finish.sh >> /tmp/round2_finish.log 2>&1 &
    sleep 20
  fi
  sleep 60
done
echo "[$(date -u +%H:%M:%S)] supervisor gave up after 40 restarts" \
  | tee -a "$LOG/supervise.log"
