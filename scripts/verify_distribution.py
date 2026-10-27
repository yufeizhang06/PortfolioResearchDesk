"""Offline sdist -> wheel -> clean venv -> installed CLI and resource smoke test."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument("--uv", default="uv", help="uv executable; default: uv on PATH")
    args = parser.parse_args()
    archives = list(args.dist.resolve().glob("*.tar.gz"))
    wheels = list(args.dist.resolve().glob("*.whl"))
    if len(archives) != 1 or len(wheels) != 1:
        parser.error("Expected exactly one sdist and one wheel in the distribution directory.")
    Path("work").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="distribution-", dir="work") as temporary:
        root = Path(temporary).resolve()
        # No isolation: reuse the project's locked build backend; --offline forbids downloads.
        subprocess.run(
            [
                args.uv,
                "build",
                "--offline",
                "--no-build-isolation",
                "--wheel",
                "--out-dir",
                str(root / "rebuilt"),
                str(archives[0]),
            ],
            check=True,
        )
        rebuilt = list((root / "rebuilt").glob("*.whl"))
        if len(rebuilt) != 1:
            raise RuntimeError("Expected one wheel rebuilt from the sdist.")
        environment = root / "venv"
        venv.EnvBuilder(with_pip=False).create(environment)
        bin_dir = environment / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        console = bin_dir / ("prd.exe" if os.name == "nt" else "prd")
        # Check both the directly built wheel and the sdist-rebuilt wheel.
        for index, wheel in enumerate((wheels[0], rebuilt[0])):
            subprocess.run(
                [
                    args.uv,
                    "pip",
                    "install",
                    "--offline",
                    "--no-deps",
                    "--reinstall",
                    "--python",
                    str(python),
                    str(wheel),
                ],
                check=True,
            )
            subprocess.run([str(console), "--help"], cwd=root, check=True, capture_output=True)
            for command in (["config", "validate"], ["demo"]):
                result = subprocess.run(
                    [str(python), "-I", "-m", "portfolio_research_desk", *command],
                    cwd=root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                payload = json.loads(result.stdout)
                if payload["phase"] != 0 or payload["config"]["currency"] != "USD":
                    raise RuntimeError("Invalid installed configuration.")
                if command == ["demo"] and payload["sample"]["rows"] != 9:
                    raise RuntimeError("Packaged sample is missing or incorrect.")
            backtest = subprocess.run(
                [
                    str(console),
                    "backtest",
                    "run",
                    "--output-dir",
                    str(root / "runs"),
                    "--run-id",
                    f"installed-{index}",
                ],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(backtest.stdout)
            if payload["phase"] != 1 or payload["metrics"]["fill_count"] <= 0:
                raise RuntimeError("Installed backtest did not execute trades.")
            marker = root / "runs" / f"installed-{index}" / "run.json"
            if not marker.is_file():
                raise RuntimeError("Installed backtest did not complete its report bundle.")
    print(
        "PASS: sdist rebuild, both wheels, clean install and CLI/resources "
        f"on {sys.version.split()[0]}"
    )


if __name__ == "__main__":
    main()
