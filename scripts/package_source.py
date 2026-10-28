"""Package reviewable source/evidence with a hash manifest, excluding local data and signing keys."""

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/aven-crm-source.zip"
REPORT = ROOT / "artifacts/android/package-check.txt"
EXCLUDED = {
    ".git",
    ".venv",
    ".local",
    "node_modules",
    "dist",
    "build",
    ".gradle",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "test-results",
}
SUFFIXES = {
    ".apk",
    ".aab",
    ".p12",
    ".jks",
    ".keystore",
    ".zip",
    ".pyc",
    ".log",
    ".dump",
    ".tar",
    ".db",
}


def configured_secrets():
    values = []
    for path in [
        ROOT / ".env",
        ROOT / "backend/.env",
        ROOT / ".local/qa-container.env",
    ]:
        if path.exists():
            for line in path.read_text().splitlines():
                key, separator, value = line.partition("=")
                if (
                    separator
                    and key in {"SECRET_KEY", "ENCRYPTION_KEY", "DB_PASSWORD"}
                    and value.strip()
                ):
                    values.append(value.strip().strip("\"'"))
    for fixture in (ROOT / ".local").rglob("android-fixture*.json"):
        if fixture.exists():
            data = json.loads(fixture.read_text())
            values.extend(
                data[key]
                for key in ["password", "otp_secret", "admin_token"]
                if data.get(key)
            )
    signing = ROOT / ".local/android-signing/password"
    if signing.exists():
        values.append(signing.read_text().strip())
    return {value.encode() for value in values if value}


def main():
    files = []
    for folder, directories, names in os.walk(ROOT):
        directories[:] = sorted(name for name in directories if name not in EXCLUDED)
        for name in sorted(names):
            path = Path(folder) / name
            if (
                path.is_symlink()
                or path == REPORT
                or name in {".env", ".DS_Store", "local.properties"}
            ):
                continue
            if (
                name.startswith(".coverage")
                or (name.startswith(".env.") and name != ".env.example")
                or path.suffix in SUFFIXES
            ):
                continue
            files.append((path, path.relative_to(ROOT).as_posix()))
    manifest = {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for path, name in files
    }
    secrets = configured_secrets()
    with zipfile.ZipFile(
        OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path, name in files:
            archive.write(path, "aven-crm/" + name)
        archive.writestr(
            "aven-crm/SOURCE_MANIFEST.json", json.dumps(manifest, indent=2) + "\n"
        )
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
        for item in archive.infolist():
            assert not any(
                part in EXCLUDED or part == ".env" for part in Path(item.filename).parts
            )
            assert Path(item.filename).suffix not in SUFFIXES
            content = archive.read(item)
            assert not any(secret in content for secret in secrets), (
                "Configured secret found in source archive"
            )
            name = item.filename.removeprefix("aven-crm/")
            if name in manifest:
                assert hashlib.sha256(content).hexdigest() == manifest[name]
        for name in [
            "backend/app/main.py",
            "backend/tests/test_android_sync.py",
            "web/src/main.tsx",
            "web/tests/fixtures.ts",
            "android/gradlew",
            "android/gradle/wrapper/gradle-wrapper.jar",
            "android/app/gradle.lockfile",
            "android/app/src/main/java/com/aven/calls/SyncEngine.java",
            "android/README.md",
            "android/QA_MATRIX.md",
            "docs/ACCEPTANCE.md",
        ]:
            assert "aven-crm/" + name in archive.namelist(), name
    shutil.copy2(OUTPUT, ROOT / "artifacts/talkocrm-source.zip")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    report = f"PASS: {len(files)} source/evidence files plus SHA-256 manifest\nPASS: archive CRC and every manifest hash verified\nPASS: local data, dependencies, build outputs, APKs, environment files and signing keys excluded\nPASS: configured CRM, QA, authenticator and signing secrets absent\nSize: {OUTPUT.stat().st_size / 1024 / 1024:.2f} MiB\nSHA-256: {digest}\n"
    REPORT.write_text(report)
    print(report)


if __name__ == "__main__":
    main()
