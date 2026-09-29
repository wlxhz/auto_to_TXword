#!/usr/bin/env bash
set -euo pipefail

archive="$1"
release="$2"
base=/opt/tencent-doc-automation
target="$base/releases/$release"
mkdir -p "$target" "$base/shared/output/live" "$base/shared/logs"
tar -xzf "$archive" -C "$target"
chmod -R go-rwx "$base/shared"
ln -s "$base/shared/output" "$target/output"
ln -s "$base/shared/logs" "$target/logs"

if [[ ! -x "$base/venv/bin/python" ]]; then
  python3 -m venv "$base/venv"
fi
"$base/venv/bin/python" -m pip install --disable-pip-version-check -q -r "$target/requirements.txt"
ln -sfn "$target" "$base/current.new"
mv -Tf "$base/current.new" "$base/current"

cat > /etc/systemd/system/tencent-ledger.service <<'UNIT'
[Unit]
Description=Sync glucose monitoring ledger to Tencent Docs
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/tencent-doc-automation/current
ExecStart=/usr/bin/flock -n /run/lock/tencent-ledger.lock /opt/tencent-doc-automation/venv/bin/python /opt/tencent-doc-automation/current/server_run.py
TimeoutStartSec=900
UNIT

cat > /etc/systemd/system/tencent-ledger.timer <<'UNIT'
[Unit]
Description=Run Tencent ledger sync at 08:00 and 17:00 Beijing time

[Timer]
OnCalendar=*-*-* 08:00:00
OnCalendar=*-*-* 17:00:00
AccuracySec=1min
Persistent=false
Unit=tencent-ledger.service

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemd-analyze calendar '*-*-* 08:00:00' '*-*-* 17:00:00' --no-pager | grep -E 'Normalized form|Next elapse' || true
echo "installed_release=$release"
rm -f "$archive"
