"""Package only deployment source plus immutable image references (no secrets)."""

import argparse
import re
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def package(output: Path, sha: str, images: dict[str, str]):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected a full Git commit SHA")
    for key, image in images.items():
        if not re.fullmatch(r"[a-zA-Z0-9./:_-]+@sha256:[0-9a-f]{64}", image):
            raise ValueError(f"{key} must use an immutable sha256 digest")
    sources = {
        "compose.yaml": ROOT / "infra/compose.production.yaml",
        "Caddyfile": ROOT / "infra/Caddyfile.production",
        **{
            name: ROOT / f"scripts/deploy/{name}"
            for name in ["deploy.sh", "host_config.py", "cleanup_images.py"]
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        env = Path(temporary) / "images.env"
        env.write_text(
            f"RELEASE_SHA={sha}\n"
            + "".join(f"{key}={value}\n" for key, value in images.items())
        )
        with tarfile.open(output, "w:gz") as archive:
            for name, path in sources.items():
                archive.add(path, arcname=name, recursive=False)
            archive.add(env, arcname="images.env", recursive=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    for name in ["api", "web", "postgres", "caddy"]:
        parser.add_argument(f"--{name}-image", required=True)
    args = parser.parse_args()
    package(
        args.output,
        args.sha,
        {
            f"{name.upper()}_IMAGE": getattr(args, f"{name}_image")
            for name in ["api", "web", "postgres", "caddy"]
        },
    )
