"""Patch the existing deployed launcher under its scheduler lock."""
from datetime import datetime
from pathlib import Path
import runpy
import paramiko


def main():
    root = Path(__file__).resolve().parent
    credentials = runpy.run_path(str(root.parents[1] / "teyi-teshan/scripts/audit-domain-production.py"))["read_credentials"]()
    client = paramiko.SSHClient()
    client.load_system_host_keys(str(Path.home() / ".ssh/known_hosts"))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(credentials["SERVER_HOST"], port=int(credentials["SSH_PORT"]),
                   username=credentials["SSH_USERNAME"], password=credentials["SSH_PASSWORD"],
                   look_for_keys=False, allow_agent=False, timeout=20)
    files = ("smart_sync.py", "tencent_doc.py", "run_live.py")
    current = "/opt/tencent-doc-automation/current"
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = "/opt/tencent-doc-automation/shared/target-switch-" + stamp
    try:
        with client.open_sftp() as sftp:
            for name in files:
                sftp.put(str(root / name), current + "/" + name + ".next")
        commands = ["set -e", "mkdir -p " + backup]
        for name in files:
            path = current + "/" + name
            commands.append("if test -f " + path + "; then cp -p " + path + " " + backup + "/" + name + "; fi")
        for name in files:
            commands.append("mv " + current + "/" + name + ".next " + current + "/" + name)
        commands.append("/opt/tencent-doc-automation/venv/bin/python -m py_compile " + " ".join(current + "/" + n for n in files))
        command = "flock -x -w 60 /run/lock/tencent-ledger.lock sh -c '" + "; ".join(commands) + "'"
        _, stdout, stderr = client.exec_command(command, timeout=90)
        stdout.read()
        if stdout.channel.recv_exit_status():
            raise RuntimeError("服务器代码更新失败，请检查备份：" + backup)
        _, stdout, stderr = client.exec_command(
            "systemctl start tencent-ledger.service && systemctl show tencent-ledger.service -p Result -p ExecMainStatus --no-pager && journalctl -u tencent-ledger.service -n 8 --no-pager", timeout=120)
        print(stdout.read().decode())
        if stdout.channel.recv_exit_status():
            raise RuntimeError("服务器智能表同步验证失败")
        print("backup=" + backup)
    finally:
        client.close()


if __name__ == "__main__":
    main()
