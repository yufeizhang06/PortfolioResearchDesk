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
    parser.add_argument(
        "--with-ml", action="store_true", help="Install locked ML extra and verify Phase 4."
    )
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
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
            paper_db = root / f"paper-{index}.sqlite3"
            paper = subprocess.run(
                [
                    str(python),
                    "-I",
                    "-m",
                    "portfolio_research_desk",
                    "paper",
                    "demo",
                    "--db",
                    str(paper_db),
                    "--output-dir",
                    str(root / f"paper-reports-{index}"),
                    "--run-id",
                    "installed",
                ],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            paper_payload = json.loads(paper.stdout)
            record = paper_payload["plans"]["synthetic-demo"]
            if (
                paper_payload["phase"] != 5
                or paper_payload["base_currency"] != "CAD"
                or paper_payload["event_count"] != 4
                or record["status"] != "SIMULATED"
                or len(record["fills"]) != 3
            ):
                raise RuntimeError("Installed Phase 5 CAD paper fixture failed.")
            recovered = subprocess.run(
                [str(console), "paper", "status", "--db", str(paper_db)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            recovered_payload = json.loads(recovered.stdout)
            if recovered_payload["state"] != paper_payload["state"]:
                raise RuntimeError("Installed paper account failed restart recovery.")
            if not (Path(paper_payload["report_directory"]) / "run.json").is_file():
                raise RuntimeError("Installed paper report completion marker missing.")
            subprocess.run(
                [str(console), "config", "validate", "--kind", "paper"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
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
            missing_ml = subprocess.run(
                [str(console), "ml", "run"], cwd=root, capture_output=True, text=True
            )
            if missing_ml.returncode != 2 or "ml extra" not in missing_ml.stderr:
                raise RuntimeError("Base installation should explain the missing ml extra.")
            if args.with_factors:
                # Reuse the exact locked wheel URLs populated by the initial sync.
                # A requirements export would need separate registry-index metadata
                # that a cold CI cache need not contain. Keep the installed wheel;
                # never replace it with an editable source-tree installation.
                subprocess.run(
                    [
                        args.uv,
                        "sync",
                        "--project",
                        str(project),
                        "--locked",
                        "--offline",
                        "--extra",
                        "factors",
                        "--no-dev",
                        "--no-install-project",
                        "--inexact",
                        "--python",
                        str(python),
                    ],
                    check=True,
                    env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(environment)},
                )
                subprocess.run(
                    [
                        str(python),
                        "-I",
                        "-c",
                        "import importlib.metadata as m, json, pathlib, sys; "
                        "import portfolio_research_desk as package; "
                        "direct=json.loads(m.distribution('portfolio-research-desk')"
                        ".read_text('direct_url.json')); "
                        "assert 'archive_info' in direct and direct['url'].endswith('.whl'); "
                        "assert pathlib.Path(package.__file__).resolve().is_relative_to("
                        "pathlib.Path(sys.prefix).resolve())",
                    ],
                    cwd=root,
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
            if args.with_ml:
                subprocess.run(
                    [
                        args.uv,
                        "sync",
                        "--project",
                        str(project),
                        "--locked",
                        "--offline",
                        "--extra",
                        "ml",
                        "--no-dev",
                        "--no-install-project",
                        "--inexact",
                        "--python",
                        str(python),
                    ],
                    check=True,
                    env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(environment)},
                )
                ml_run = subprocess.run(
                    [
                        str(python),
                        "-I",
                        "-m",
                        "portfolio_research_desk",
                        "ml",
                        "run",
                        "--output-dir",
                        str(root / f"ml-{index}"),
                        "--run-id",
                        "installed",
                    ],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                ml_payload = json.loads(ml_run.stdout)
                ml_dir = Path(ml_payload["report_directory"])
                if ml_payload["phase"] != 4 or ml_payload["credible_real_market_oos"] is not False:
                    raise RuntimeError("Installed Phase 4 scope metadata failed.")
                if not (ml_dir / "run.json").is_file() or not (ml_dir / "folds.json").is_file():
                    raise RuntimeError("Installed Phase 4 audit bundle is incomplete.")
                if set(ml_payload["metrics"]["holdout"]) != {
                    "dummy",
                    "logistic",
                    "lasso",
                    "random_forest",
                    "xgboost",
                }:
                    raise RuntimeError("Installed Phase 4 model coverage failed.")
                subprocess.run(
                    [
                        str(python),
                        "-I",
                        "-c",
                        "import importlib.metadata as m, json, pathlib, sys; "
                        "import portfolio_research_desk as p; "
                        "d=json.loads(m.distribution('portfolio-research-desk')"
                        ".read_text('direct_url.json')); "
                        "assert 'archive_info' in d and d['url'].endswith('.whl'); "
                        "assert pathlib.Path(p.__file__).resolve().is_relative_to("
                        "pathlib.Path(sys.prefix).resolve())",
                    ],
                    cwd=root,
                    check=True,
                )
    print(
        "PASS: sdist rebuild, both wheels, clean install and CLI/resources "
        f"on {sys.version.split()[0]}"
    )


if __name__ == "__main__":
    main()
