"""Export installed license metadata for locked packages; no network or legal inference."""

import json
import tomllib
from importlib import metadata
from pathlib import Path


def inventory():
    project = Path(__file__).resolve().parents[1]
    lock = tomllib.loads((project / "uv.lock").read_text("utf-8"))
    result = []
    for package in lock["package"]:
        name = package["name"]
        if name == "portfolio-research-desk":
            continue
        row = {"name": name, "locked_version": package["version"]}
        try:
            dist = metadata.distribution(name)
            expression = dist.metadata.get("License-Expression")
            license_text = dist.metadata.get("License", "")
            row.update(
                installed_version=dist.version,
                matches_lock=dist.version == package["version"],
                license_expression=expression,
                license_summary=license_text.splitlines()[0] if license_text else None,
                license_files=dist.metadata.get_all("License-File") or [],
                classifiers=[
                    c for c in dist.metadata.get_all("Classifier", []) if c.startswith("License")
                ],
            )
        except metadata.PackageNotFoundError:
            row["installed_version"] = None
            row["note"] = "Not installed on this platform / selected extras."
        result.append(row)
    return {
        "scope": (
            "Installed metadata versus uv.lock; not a license clearance or bundled-code audit."
        ),
        "network_accessed": False,
        "packages": result,
    }


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2, ensure_ascii=True))
