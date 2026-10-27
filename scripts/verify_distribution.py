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
    parser.add_argument(
        "--with-factors",
        action="store_true",
        help="Install locked factor extra and verify Phase 3.",
    )
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
        requirements = root / "factor-requirements.txt"
        if args.with_factors:
            subprocess.run(
                [
                    args.uv,
                    "export",
                    "--locked",
                    "--offline",
                    "--extra",
                    "factors",
                    "--no-dev",
                    "--no-emit-project",
                    "--output-file",
                    str(requirements),
                ],
                check=True,
                capture_output=True,
            )
        # Check both the directly built wheel and the sdist-rebuilt wheel.
        for index, wheel in enumerate((wheels[0], rebuilt[0])):
            environment = root / f"venv-{index}"
            venv.EnvBuilder(with_pip=False).create(environment)
            bin_dir = environment / ("Scripts" if os.name == "nt" else "bin")
            python = bin_dir / ("python.exe" if os.name == "nt" else "python")
            console = bin_dir / ("prd.exe" if os.name == "nt" else "prd")
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
            research = subprocess.run(
                [
                    str(console),
                    "universe",
                    "build",
                    "--output-dir",
                    str(root / f"research-{index}"),
                ],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            phase2 = json.loads(research.stdout)
            if (
                phase2["phase"] != 2
                or phase2["data_kind"] != "synthetic"
                or phase2["status"] != "complete"
            ):
                raise RuntimeError("Installed Phase 2 offline research failed.")
            missing = subprocess.run(
                [str(console), "research", "run"], cwd=root, capture_output=True, text=True
            )
            if missing.returncode != 2 or "factors extra" not in missing.stderr:
                raise RuntimeError(
                    "Base installation should explain the missing factors extra: "
                    f"exit={missing.returncode}, stderr={missing.stderr}"
                )
            if args.with_factors:
                subprocess.run(
                    [
                        args.uv,
                        "pip",
                        "install",
                        "--offline",
                        "--no-deps",
                        "--python",
                        str(python),
                        "-r",
                        str(requirements),
                    ],
                    check=True,
                )
                factor_run = subprocess.run(
                    [
                        str(console),
                        "research",
                        "run",
                        "--output-dir",
                        str(root / f"factors-{index}"),
                        "--run-id",
                        "installed",
                    ],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                factor_payload = json.loads(factor_run.stdout)
                if factor_payload["nobs"] != 96 or factor_payload["status"] != "complete":
                    raise RuntimeError("Installed Phase 3 fixture/report failed.")
                factor_dir = Path(factor_payload["report_directory"])
                analysis = json.loads((factor_dir / "analysis.json").read_text("utf-8"))
                if abs(analysis["fits"]["FF4"]["coefficients"]["Mom"]["estimate"] - 0.5) > 1e-10:
                    raise RuntimeError("Installed FF4 did not recover the theoretical coefficient.")
                if not (factor_dir / "rolling.svg").is_file():
                    raise RuntimeError("Installed factor charts are missing.")
    print(
        "PASS: sdist rebuild, both wheels, clean install and CLI/resources "
        f"on {sys.version.split()[0]}"
    )


if __name__ == "__main__":
    main()
