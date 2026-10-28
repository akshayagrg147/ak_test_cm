"""Delete only unused ViaCRM images; retain current and previous release images."""

import subprocess
import sys
from pathlib import Path


def cleanup(root: Path):
    retained = set()
    for link in ("current", "previous"):
        path = root / link / "images.env"
        if path.exists():
            for line in path.read_text().splitlines():
                key, _, value = line.partition("=")
                if key in {"API_IMAGE", "WEB_IMAGE"}:
                    image_id = subprocess.check_output(
                        ["docker", "image", "inspect", "--format", "{{.Id}}", value],
                        text=True,
                    ).strip()
                    retained.add(image_id)
    candidates = subprocess.check_output(
        [
            "docker",
            "image",
            "ls",
            "--no-trunc",
            "--quiet",
            "--filter",
            "label=io.viacrm.project=viacrm",
        ],
        text=True,
    ).splitlines()
    for image_id in sorted(set(candidates) - retained):
        # No --force: Docker refuses to remove an image used by any container.
        subprocess.run(["docker", "image", "rm", image_id], check=False)


if __name__ == "__main__":
    cleanup(Path(sys.argv[1]))
