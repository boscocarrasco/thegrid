#!/usr/bin/env bash
# Keep scripts/round2_finish.sh alive.
#
# Three things stop the driver through no fault of the plan: the desktop dying,
# a provider usage block, which takes the whole process tree with it, and the
# session itself being restarted. The driver is resumable — already_done()
# skips completed records and retries only the ones marked rate_limited — so
# the correct response to all three is to start it again. The global spend
# guard lives inside the driver, so this loop cannot spend past the cap.
#
# The first version of this counted loop iterations against its restart budget
# and so gave up after forty quiet minutes while the driver was working fine.
# Only an actual restart counts now, and the loop itself runs for as long as
# there is work.
set -u
cd "$(dirname "$0")/.."
LOG=${GRID_LOG:-/tmp/round2}
MAX_RESTARTS=${GRID_MAX_RESTARTS:-200}
mkdir -p "$LOG"
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG/supervise.log"; }

restarts=0
while true; do
  if grep -q "ALL TIERS ATTEMPTED\|STOP: estimated spend" "$LOG/finish.log" 2>/dev/null; then
    say "driver reported it is finished; supervisor exiting"
    exit 0
  fi

  if ! pgrep -f "bash scripts/round2_finish.sh" >/dev/null; then
    if [ "$restarts" -ge "$MAX_RESTARTS" ]; then
      say "gave up after $restarts restarts"
      exit 1
    fi
    # The driver revives the desktop per tier, but if the driver is not running
    # then nothing is, so check here too before handing work back to it.
    if ! /usr/bin/python3.12 -c 'import sys; sys.path.insert(0,"."); from runner.experiment import desktop_alive; sys.exit(0 if desktop_alive() else 1)' 2>/dev/null; then
      say "desktop is down; restarting it"
      bash scripts/env_up.sh >>"$LOG/envup.log" 2>&1
    fi
    source /tmp/grid-env/env.sh
    restarts=$((restarts + 1))
    say "driver not running; starting it (restart $restarts)"
    nohup bash scripts/round2_finish.sh >> /tmp/round2_finish.log 2>&1 &
    sleep 30
  fi
  sleep 60
done
