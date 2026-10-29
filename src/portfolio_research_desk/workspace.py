"""Exclusive local workspace templates. Generated samples are always synthetic."""

import csv
from importlib.resources import files
from pathlib import Path

from portfolio_research_desk.delivery_reports import write_json
from portfolio_research_desk.errors import ReportError
from portfolio_research_desk.workflow_fixtures import delivery_inputs, paper_documents


def create_workspace(directory: Path):
    resource = files("portfolio_research_desk").joinpath("resources")
    try:
        configs = {
            name: resource.joinpath(name + ".toml").read_text("utf-8")
            for name in ("workflow", "paper", "backtest", "factors", "ml", "research")
        }
        configs["workflow"] = configs["workflow"].replace(
            'output_dir = "outputs/workflows"', 'output_dir = "runs"'
        )
        documents = paper_documents()
        directory = directory.resolve()
        directory.mkdir(parents=True, exist_ok=False)
        for name, content in configs.items():
            with (directory / (name + ".toml")).open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
        for name, content in documents.items():
            write_json(directory / (name + ".json"), content)
        assets = delivery_inputs()["bundle"].universe.assets
        with (directory / "watchlist.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("market", "exchange", "symbol", "currency"))
            writer.writerows((a.market, a.exchange, a.symbol, a.currency) for a in assets)
        (directory / ".gitignore").write_text(
            "/runs/\n/accounts/\n/cache/\n/data/\n/outputs/\n/private/\n"
            "*.sqlite*\n*.db\n*.key\ncredentials*\n.env\n.env.*\n",
            encoding="utf-8",
        )
        (directory / "README.md").write_text(
            "# Local PortfolioResearchDesk workspace\n\n"
            "All provided inputs are synthetic fixtures, with fixed 2024 UTC times. "
            "They are not live market inputs.\n\n"
            "From this directory after installing the package:\n\n"
            "```text\nprd doctor\nprd workflow run --config workflow.toml\n"
            "prd workflow run --config workflow.toml --with-factors --with-ml\n```\n\n"
            "The workflow creates a new immutable run and an index.html linking all reports.\n"
            "It uses a fixed synthetic universe; changing watchlist.csv "
            "does not retarget the demo.\n"
            "For daily Paper work, import your available data into the readable "
            "decision/opening/closing schemas,\n"
            "use a separate accounts/ database, then paper plan, paper review, "
            "paper simulate, paper value, summary and export.\n"
            "The research.toml normalized-data fixture and factors/ml examples "
            "keep their own explicit identities/date ranges;\n"
            "they are independent diagnostics, not interchangeable historical PIT inputs.\n"
            "Do not relabel these files real. Consult the installed CLI help "
            "and project USER_GUIDE for actual sources.\n",
            encoding="utf-8",
        )
        return {
            "phase": 6,
            "status": "created",
            "data_kind": "synthetic",
            "directory": str(directory),
            "workflow_config": str(directory / "workflow.toml"),
            "next_command": f'prd workflow run --config "{directory / "workflow.toml"}"',
            "paper_inputs": [str(directory / (name + ".json")) for name in documents],
        }
    except OSError as exc:
        raise ReportError(
            "Cannot create workspace; existing directories are never overwritten. "
            "Inspect incomplete output if present."
        ) from exc
