"""Read production aggregates over the existing verified SSH connection."""
import json
import re
from pathlib import Path

from database_source import SUMMARY_SQL


def get_server_data(config, logger):
    import paramiko

    values = {}
    for line in Path(config["credential_file"]).read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    client = paramiko.SSHClient()
    client.load_system_host_keys(str(Path.home() / ".ssh" / "known_hosts"))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(values["SERVER_HOST"], port=int(values["SSH_PORT"]),
                       username=values["SSH_USERNAME"], password=values["SSH_PASSWORD"],
                       look_for_keys=False, allow_agent=False, timeout=20)
        _, stdout, _ = client.exec_command(
            "docker ps --filter label=com.docker.compose.service=backend --format '{{.ID}}'")
        containers = stdout.read().decode().splitlines()
        if len(containers) != 1 or not re.fullmatch(r"[a-f0-9]+", containers[0]):
            raise RuntimeError("Expected exactly one production backend container")
        script = '''import asyncio, json
from sqlalchemy import text
from app.db.session import AsyncSessionLocal, engine
async def run():
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        rows = (await db.execute(text(SQL))).mappings().all()
        print(json.dumps([dict(r) for r in rows], default=str, ensure_ascii=False))
    await engine.dispose()
asyncio.run(run())
'''
        stdin, stdout, stderr = client.exec_command("docker exec -i " + containers[0] + " python -", timeout=120)
        stdin.write("SQL = " + repr(SUMMARY_SQL) + "\n" + script)
        stdin.channel.shutdown_write()
        payload = stdout.read().decode()
        error = stderr.read().decode()
        if stdout.channel.recv_exit_status():
            # SQL error text can contain parameters; do not include it in logs.
            raise RuntimeError("Production read-only query failed: " +
                               next((x for x in ("UndefinedColumnError", "UndefinedTableError") if x in error), "remote query error"))
        rows = json.loads(payload)
    finally:
        client.close()
    for index, row in enumerate(rows, 1):
        row["sequence"] = index
        for field in ("glucose_mean", "glucose_max", "glucose_min"):
            row[field] = float(row[field])
    logger.info("服务器只读查询完成：records=%d", len(rows))
    return rows
