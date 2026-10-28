"""Local-only fresh-migration and restore drill; all targets have unique test names."""

import hashlib
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from uuid import uuid4

import psycopg

root = Path(__file__).resolve().parents[1]
cluster = ["-h", "127.0.0.1", "-p", "55432"]
names = [
    "talkocrm_migration_" + uuid4().hex[:8] + "_test",
    "talkocrm_restore_" + uuid4().hex[:8] + "_test",
]
report = []


def run(command, **kwargs):
    result = subprocess.run(
        command, check=True, text=True, capture_output=True, **kwargs
    )
    return result.stdout.strip()


try:
    for name in names:
        run(["createdb", *cluster, name])
    env = {
        **os.environ,
        "DATABASE_URL": f"postgresql+psycopg://127.0.0.1:55432/{names[0]}",
    }
    for operation in [
        ["upgrade", "head"],
        ["check"],
        ["downgrade", "base"],
        ["upgrade", "head"],
    ]:
        run(
            [str(root / ".venv/bin/alembic"), *operation], cwd=root / "backend", env=env
        )
        report.append("PASS: fresh Alembic " + " ".join(operation))
    with tempfile.TemporaryDirectory(prefix="talkocrm-recovery-") as temp:
        dump = Path(temp) / "database.dump"
        # Compare against the exact database snapshot exported to pg_dump. Browser
        # writes after that point must not create a false restore-count failure.
        with psycopg.connect(
            "host=127.0.0.1 port=55432 dbname=talkocrm", autocommit=True
        ) as source:
            source.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            snapshot = source.execute("SELECT pg_export_snapshot()").fetchone()[0]
            run(
                [
                    "pg_dump",
                    *cluster,
                    "-d",
                    "talkocrm",
                    "--snapshot",
                    snapshot,
                    "-Fc",
                    "-f",
                    str(dump),
                ]
            )
            run(
                [
                    "pg_restore",
                    *cluster,
                    "--exit-on-error",
                    "--no-owner",
                    "-d",
                    names[1],
                    str(dump),
                ]
            )
            with psycopg.connect(
                f"host=127.0.0.1 port=55432 dbname={names[1]}"
            ) as restored:
                for table in [
                    "users",
                    "organizations",
                    "leads",
                    "manual_calls",
                    "attachments",
                    "jobs",
                    "alembic_version",
                ]:
                    a = source.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    b = restored.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    assert a == b, table
                    report.append(f"PASS: restored {table} count = {b}")
            source.execute("ROLLBACK")
            report.append(
                "PASS: dump and verification use the same exported repeatable-read snapshot"
            )
        storage = root / ".local/storage"
        storage.mkdir(parents=True, exist_ok=True)
        probe = storage / ("restore-probe-" + uuid4().hex)
        probe.write_bytes(os.urandom(64))
        try:
            archive = Path(temp) / "files.tar"
            with tarfile.open(archive, "w") as target:
                target.add(storage, arcname="storage")
            restored_files = Path(temp) / "restore"
            with tarfile.open(archive) as target:
                target.extractall(restored_files, filter="data")
            for file in storage.iterdir():
                if file.is_file():
                    assert (
                        hashlib.sha256(file.read_bytes()).digest()
                        == hashlib.sha256(
                            (restored_files / "storage" / file.name).read_bytes()
                        ).digest()
                    )
            report.append(
                "PASS: private storage archive restored with matching SHA-256 bytes"
            )
        finally:
            probe.unlink(missing_ok=True)
finally:
    for name in names:
        subprocess.run(
            ["dropdb", *cluster, "--if-exists", name], check=False, capture_output=True
        )
(root / "artifacts/recovery-tests.txt").write_text("\n".join(report) + "\n")
print("\n".join(report))
