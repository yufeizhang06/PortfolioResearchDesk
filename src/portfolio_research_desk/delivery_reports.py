"""Small immutable workflow bundles and offline, confined integrity verification."""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from uuid import uuid4

from portfolio_research_desk.domain import jsonable
from portfolio_research_desk.errors import ReportError


def write_json(path, value):
    try:
        with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(jsonable(value), stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    except (OSError, ValueError, TypeError) as exc:
        raise ReportError(f"Cannot create JSON output: {Path(path).name}.") from exc


def reserve_run(parent, run_id=None):
    run_id = run_id or "workflow-" + uuid4().hex[:12]
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)
    }
    if (
        not isinstance(run_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id)
        or run_id.upper() in reserved
    ):
        raise ReportError(
            "run_id requires 1–80 non-reserved letters, digits, hyphens or underscores."
        )
    directory = Path(parent) / run_id
    try:
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.mkdir(exist_ok=False)
    except OSError as exc:
        raise ReportError(
            "Cannot reserve workflow directory; existing runs are never overwritten."
        ) from exc
    return directory.resolve()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bundle_hashes(directory):
    hashes = {}
    try:
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ReportError("Workflow bundles cannot contain symbolic links.")
            if path.is_file() and path != directory / "workflow.json":
                hashes[path.relative_to(directory).as_posix()] = file_hash(path)
        return hashes
    except OSError as exc:
        raise ReportError("Cannot hash workflow artifacts.") from exc


def verify_workflow_report(directory):
    directory = Path(directory).resolve()
    try:
        marker = directory / "workflow.json"
        if marker.is_symlink():
            raise ReportError("Workflow completion marker cannot be a symbolic link.")
        document = json.loads(marker.read_text("utf-8"))
        expected = {
            "schema_version",
            "phase",
            "status",
            "data_kind",
            "credible_real_market_oos",
            "components",
            "files",
        }
        if (
            not isinstance(document, dict)
            or set(document) != expected
            or type(document["schema_version"]) is not int
            or document["schema_version"] != 6
        ):
            raise ReportError("Unknown or incomplete workflow manifest.")
        if (
            document["phase"] != 6
            or document["status"] != "complete"
            or document["data_kind"] != "synthetic"
            or document["credible_real_market_oos"] is not False
        ):
            raise ReportError("Workflow scope/status cannot be verified.")
        files = document["files"]
        if not isinstance(files, dict) or not files:
            raise ReportError("Workflow artifact hashes are missing.")
        for name, digest in files.items():
            if (
                not isinstance(name, str)
                or "\\" in name
                or ":" in name
                or PurePosixPath(name).is_absolute()
                or any(part in {".", ".."} for part in name.split("/"))
                or not name
                or not isinstance(digest, str)
                or not re.fullmatch("[0-9a-f]{64}", digest)
            ):
                raise ReportError("Unsafe artifact path or hash in workflow manifest.")
            path = directory / name
            if not path.resolve().is_relative_to(directory):
                raise ReportError("Artifact path escapes the workflow directory.")
        actual = bundle_hashes(directory)
        if actual != files:
            raise ReportError(
                "Workflow artifacts changed, are missing or contain unexpected files."
            )
        return {
            "phase": 6,
            "status": "verified",
            "data_kind": "synthetic",
            "credible_real_market_oos": False,
            "report_directory": str(directory),
            "index": str(directory / "index.html"),
            "file_count": len(files),
            "components": document["components"],
        }
    except (OSError, ValueError, TypeError) as exc:
        raise ReportError(
            "Cannot read a completed workflow bundle; no network requests were made."
        ) from exc
