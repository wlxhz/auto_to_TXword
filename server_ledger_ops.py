"""Deploy and verify the live ledger task on the existing production host."""
from __future__ import annotations

import io
import os
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parent
CREDS = ROOT.parents[1] / "teyi-teshan" / ".runtime" / "private" / "server-access.env"
EXCLUDE = {".git", ".venv", ".pytest_cache", ".pytest-tmp", "__pycache__", "output", "logs"}


def credentials():
    values = {}
    for raw in CREDS.read_text(encoding="utf-8").splitlines():
        if raw.strip() and not raw.lstrip().startswith("#"):
            key, value = raw.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def connect():
    c = credentials()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(c["SERVER_HOST"], int(c["SSH_PORT"]), c["SSH_USERNAME"], c["SSH_PASSWORD"],
                   look_for_keys=False, allow_agent=False, timeout=20, auth_timeout=20)
    client.get_transport().set_keepalive(30)
    return client


def remote(client, command):
    channel = client.get_transport().open_session()
    channel.exec_command(command)
    while True:
        if channel.recv_ready():
            sys.stdout.buffer.write(channel.recv(8192))
            sys.stdout.buffer.flush()
        if channel.recv_stderr_ready():
            sys.stderr.buffer.write(channel.recv_stderr(8192))
            sys.stderr.buffer.flush()
        if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
            break
    code = channel.recv_exit_status()
    if code:
        raise RuntimeError(f"Remote command failed: {code}")


def bundle():
    file = tempfile.NamedTemporaryFile(prefix="ledger-", suffix=".tar.gz", delete=False)
    file.close()
    with tarfile.open(file.name, "w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file() or any(part in EXCLUDE for part in path.relative_to(ROOT).parts):
                continue
            if path.suffix in {".pyc", ".xlsx"} or path.name == "server_ledger_ops.py":
                continue
            tar.add(path, arcname=str(path.relative_to(ROOT)))
    return Path(file.name)


def main():
    action = sys.argv[1]
    client = connect()
    try:
        if action == "probe":
            remote(client, "set -e; date '+%F %T %Z'; timedatectl show -p Timezone --value; python3 --version; "
                   "test -f /opt/teyi/production.env && echo production_env=present; "
                   "test -f /root/.config/tencent-docs/env && echo tencent_token=present; "
                   "docker ps --format '{{.Names}}'; "
                   "systemctl list-timers --all --no-pager | grep -Ei 'ledger|tencent|NEXT' || true; "
                   "test -e /opt/tencent-doc-automation/current && echo previous_deployment=present || true")
            remote(client, "grep -E '^[A-Za-z_][A-Za-z0-9_]*=' /opt/teyi/production.env | cut -d= -f1 | grep -E 'POSTGRES|DATABASE' || true; "
                   "grep -E '^[A-Za-z_][A-Za-z0-9_]*=' /root/.config/tencent-docs/env | cut -d= -f1; "
                   "docker port deploy-postgres-1 5432 || true; command -v flock; command -v systemctl")
            remote(client, "sed -n 's/^\\(export[[:space:]]*\\)\\?\\([A-Za-z_][A-Za-z0-9_]*\\)=.*/\\2/p' /root/.config/tencent-docs/env")
        elif action == "deploy":
            archive = bundle()
            release = datetime.now().strftime("%Y%m%d%H%M%S")
            remote_archive = f"/tmp/ledger-{release}.tar.gz"
            try:
                sftp = client.open_sftp()
                sftp.put(str(archive), remote_archive)
                sftp.put(str(ROOT / "server_install.sh"), "/tmp/ledger-install.sh")
                sftp.close()
                print(f"Uploaded source bundle ({archive.stat().st_size} bytes).")
                remote(client, f"bash /tmp/ledger-install.sh {remote_archive} {release}")
            finally:
                archive.unlink(missing_ok=True)
        elif action == "test":
            remote(client, "systemctl start tencent-ledger.service && "
                   "systemctl show tencent-ledger.service -p Result -p ExecMainStatus --no-pager && "
                   "journalctl -u tencent-ledger.service -n 35 --no-pager")
        elif action == "schedule":
            remote(client, "systemctl enable --now tencent-ledger.timer && "
                   "systemctl list-timers tencent-ledger.timer --all --no-pager && "
                   "systemctl show tencent-ledger.timer -p ActiveState -p NextElapseUSecRealtime --no-pager")
        elif action == "verify-write":
            sftp = client.open_sftp()
            sftp.put(str(ROOT / "verify_live_write.py"),
                     "/opt/tencent-doc-automation/current/verify_live_write.py")
            sftp.close()
            remote(client, "cd /opt/tencent-doc-automation/current && "
                   "/opt/tencent-doc-automation/venv/bin/python verify_live_write.py")
        else:
            raise ValueError(action)
    finally:
        client.close()


if __name__ == "__main__":
    main()
