#!/usr/bin/env bash
# Bring up the virtual desktop: Xvfb + D-Bus session + AT-SPI registry.
# Writes /tmp/grid-env/env.sh which every other process sources.
set -euo pipefail

DISPLAY_NUM="${GRID_DISPLAY:-:99}"
W="${GRID_W:-1920}"; H="${GRID_H:-1080}"
RUNDIR=/tmp/grid-env
mkdir -p "$RUNDIR"

pkill -f "Xvfb ${DISPLAY_NUM}" 2>/dev/null || true
pkill -f at-spi2-registryd 2>/dev/null || true
pkill -f at-spi-bus-launcher 2>/dev/null || true
pkill -f "dbus-daemon --session" 2>/dev/null || true
sleep 0.5
rm -f "/tmp/.X${DISPLAY_NUM#:}-lock" 2>/dev/null || true

# ---- X server: fixed resolution, fixed DPI, no scaling ----
Xvfb "$DISPLAY_NUM" -screen 0 "${W}x${H}x24" -dpi 96 -nolisten tcp -noreset \
     >"$RUNDIR/xvfb.log" 2>&1 &
echo $! > "$RUNDIR/xvfb.pid"
export DISPLAY="$DISPLAY_NUM"
for _ in $(seq 1 50); do xdpyinfo >/dev/null 2>&1 && break; sleep 0.2; done
xdpyinfo >/dev/null 2>&1 || { echo "FATAL: Xvfb did not come up"; exit 1; }

# ---- session bus (shared by apps and by the observer) ----
eval "$(dbus-launch --sh-syntax)"
echo "$DBUS_SESSION_BUS_PID" > "$RUNDIR/dbus.pid"

# ---- accessibility stack ----
export GTK_MODULES=gail:atk-bridge
export QT_ACCESSIBILITY=1
export QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1
export OOO_FORCE_DESKTOP=gnome          # LibreOffice: use the gtk3 VCL plugin
export SAL_USE_VCLPLUGIN=gtk3
export NO_AT_BRIDGE=0
export GDK_BACKEND=x11

/usr/libexec/at-spi-bus-launcher --launch-immediately >"$RUNDIR/atspi-bus.log" 2>&1 &
echo $! > "$RUNDIR/atspi-bus.pid"
sleep 1
/usr/libexec/at-spi2-registryd --use-gnome-session >"$RUNDIR/atspi-reg.log" 2>&1 &
echo $! > "$RUNDIR/atspi-reg.pid"
sleep 1

# gsettings needs a writable dconf dir; toolkit-accessibility is what GTK reads
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$RUNDIR/xdg}"
mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
gsettings set org.gnome.desktop.interface toolkit-accessibility true 2>/dev/null || true

cat > "$RUNDIR/env.sh" <<EOF
export DISPLAY=$DISPLAY_NUM
export DBUS_SESSION_BUS_ADDRESS='$DBUS_SESSION_BUS_ADDRESS'
export GTK_MODULES=gail:atk-bridge
export QT_ACCESSIBILITY=1
export QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1
export OOO_FORCE_DESKTOP=gnome
export SAL_USE_VCLPLUGIN=gtk3
export NO_AT_BRIDGE=0
export GDK_BACKEND=x11
export XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR
export GRID_W=$W
export GRID_H=$H
EOF

echo "env up: DISPLAY=$DISPLAY_NUM ${W}x${H}  bus=$DBUS_SESSION_BUS_ADDRESS"
echo "source $RUNDIR/env.sh"
