"""Offline installation diagnostics; inspection never installs packages or fetches data."""

import importlib.metadata as metadata
import importlib.util
import platform
import sqlite3
import sys

from portfolio_research_desk import __version__
from portfolio_research_desk.errors import DataError

EXTRAS = {
    "data": {"yfinance": "yfinance", "pyarrow": "pyarrow"},
    "factors": {
        "numpy": "numpy",
        "scipy": "scipy",
        "statsmodels": "statsmodels",
        "matplotlib": "matplotlib",
    },
    "ml": {"scikit-learn": "sklearn", "xgboost": "xgboost"},
}


def inspect_environment(required=()):
    if any(name not in EXTRAS for name in required):
        raise DataError("Unknown optional extra; choose data, factors or ml.")
    extras = {}
    for name, packages in EXTRAS.items():
        details = {}
        for distribution, module in packages.items():
            try:
                version = metadata.version(distribution)
                available = importlib.util.find_spec(module) is not None
            except (metadata.PackageNotFoundError, ValueError, ImportError):
                version, available = None, False
            details[distribution] = {"version": version, "available": available}
        extras[name] = {
            "available": all(p["available"] for p in details.values()),
            "packages": details,
            "install_command": f"uv sync --locked --extra {name}",
        }
    python_ok = sys.version_info[:2] == (3, 12)
    missing = [name for name in required if not extras[name]["available"]]
    return {
        "phase": 6,
        "status": "ready" if python_ok and not missing else "attention_required",
        "package_version": __version__,
        "python_version": platform.python_version(),
        "python_supported": python_ok,
        "sqlite_version": sqlite3.sqlite_version,
        "base_currency": "CAD",
        "network_accessed": False,
        "extras": extras,
        "missing_required_extras": missing,
        "checks": (
            "Metadata/module discovery only; workflow execution separately validates "
            "actual imports and numerical behavior."
        ),
    }


def require_workflow_extras(config):
    required = tuple(
        name
        for name, enabled in (("factors", config.include_factors), ("ml", config.include_ml))
        if enabled
    )
    report = inspect_environment(required)
    if report["status"] != "ready":
        missing = ", ".join(report["missing_required_extras"])
        raise DataError(
            f"Workflow requirements missing: {missing or 'Python 3.12'}. "
            "Run prd doctor; install the locked extras before retrying."
        )
    # Metadata does not guarantee an importable binary wheel. Existing preflight
    # functions provide the actual engine import checks, before reserving output.
    if config.include_factors:
        from portfolio_research_desk.factor_analysis import require_factor_dependencies

        require_factor_dependencies()
    if config.include_ml:
        from portfolio_research_desk.ml_config import MODELS
        from portfolio_research_desk.ml_models import require_ml_dependencies

        require_ml_dependencies(MODELS)
