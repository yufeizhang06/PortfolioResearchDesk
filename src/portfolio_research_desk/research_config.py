"""Strict Phase 2 configuration; paths resolve relative to the selected TOML file."""

import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import Any

from portfolio_research_desk.data_adapters import RetryPolicy
from portfolio_research_desk.domain import AssetId, jsonable, require_utc
from portfolio_research_desk.errors import ConfigError, DataError
from portfolio_research_desk.screening import ScreenRules


@dataclass(frozen=True)
class ResearchConfig:
    universe_mode: str
    assets: tuple[AssetId, ...]
    watchlist: Path | None
    directory_fixture: bool
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    adapter: str
    local_file: Path | None
    expected_kind: str
    start: date
    end: date
    as_of: datetime | None
    rules: ScreenRules | None
    expected_sessions: tuple[date, ...] | None
    cache_dir: Path
    ttl_hours: int
    offline: bool
    allow_stale: bool
    max_assets: int
    output_dir: Path
    require_point_in_time: bool
    policy: RetryPolicy

    def snapshot(self) -> dict[str, Any]:
        values = {
            name: (str(value) if isinstance(value, Path) else value)
            for name, value in self.__dict__.items()
        }
        return jsonable({"schema_version": 2, **values})


def _table(value: Any, allowed: set[str], required: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        raise ConfigError(f"{name}: unknown/missing fields or invalid table.")
    return value


def _bool(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise ConfigError(f"{name} must be a boolean.")
    return value


def _int(value: Any, name: str, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise ConfigError(f"{name} must be an integer >= {minimum}.")
    return value


def _symbols(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or any(type(item) is not str for item in value):
        raise ConfigError("Symbol filters must be string arrays.")
    return tuple(dict.fromkeys(item.strip().upper() for item in value))


def _assets(value: Any) -> tuple[AssetId, ...]:
    if not isinstance(value, list):
        raise ConfigError("assets must be an array of explicit identity tables.")
    assets = []
    for item in value:
        _table(
            item,
            {"market", "exchange", "symbol", "currency"},
            {"market", "exchange", "symbol", "currency"},
            "asset",
        )
        if any(type(v) is not str for v in item.values()):
            raise ConfigError("Asset identity fields must be strings.")
        assets.append(AssetId(**{key: val.strip().upper() for key, val in item.items()}))
    return tuple(dict.fromkeys(assets))


def load_research_config(path: Path | None = None) -> ResearchConfig:
    try:
        raw = (
            path.read_bytes()
            if path
            else files("portfolio_research_desk").joinpath("resources/research.toml").read_bytes()
        )
        document = tomllib.loads(raw.decode("utf-8"), parse_float=Decimal)
        root = _table(
            document,
            {"schema_version", "universe", "data", "research", "screening", "storage", "network"},
            {"schema_version", "universe", "data"},
            "config",
        )
        if type(root["schema_version"]) is not int or root["schema_version"] != 2:
            raise ConfigError("Phase 2 requires schema_version=2.")
        universe = _table(
            root["universe"],
            {"mode", "source", "assets", "watchlist", "directory_fixture", "include", "exclude"},
            {"mode"},
            "universe",
        )
        mode = universe["mode"]
        if mode not in {"custom", "market", "screening"}:
            raise ConfigError("universe.mode must be custom, market or screening.")
        if universe.get("source", "nasdaq_listed") != "nasdaq_listed":
            raise ConfigError("The market source is nasdaq_listed, not a historical index adapter.")
        base = path.resolve().parent if path else Path.cwd()

        def local(value: Any) -> Path:
            if type(value) is not str or not value.strip():
                raise ConfigError("File paths must be nonempty strings.")
            return (base / value).resolve()

        assets = _assets(universe.get("assets", []))
        watchlist = local(universe["watchlist"]) if "watchlist" in universe else None
        if mode in {"custom", "screening"} and (bool(assets) == bool(watchlist)):
            raise ConfigError("Custom/screening mode requires exactly one of assets or watchlist.")
        if mode == "market" and watchlist:
            raise ConfigError("Use explicit assets for additions to the current market snapshot.")
        data = _table(
            root["data"],
            {
                "adapter",
                "local_file",
                "expected_kind",
                "start",
                "end",
                "offline",
                "allow_stale",
                "max_assets",
                "expected_sessions",
            },
            {"adapter", "expected_kind", "start", "end"},
            "data",
        )
        adapter, kind = data["adapter"], data["expected_kind"]
        if adapter not in {"yfinance", "csv", "parquet"} or kind not in {"real", "synthetic"}:
            raise ConfigError(
                "Explicit yfinance/csv/parquet adapter and real/synthetic kind required."
            )
        if adapter == "yfinance" and kind != "real":
            raise ConfigError("yfinance cannot be declared synthetic.")
        file = None
        if adapter in {"csv", "parquet"}:
            if data.get("local_file") == "packaged":
                if adapter != "csv" or kind != "synthetic":
                    raise ConfigError("Packaged fixture is explicitly synthetic CSV.")
                file = Path(
                    str(files("portfolio_research_desk").joinpath("resources/research_prices.csv"))
                )
            else:
                file = local(data.get("local_file"))
            if file.suffix.lower() != f".{adapter}":
                raise ConfigError("Local file extension must match the selected adapter.")
        elif "local_file" in data:
            raise ConfigError("yfinance does not use a local_file.")
        start, end = date.fromisoformat(str(data["start"])), date.fromisoformat(str(data["end"]))
        if start >= end:
            raise ConfigError("start must be before exclusive end.")
        research = _table(
            root.get("research", {}), {"as_of", "require_point_in_time"}, set(), "research"
        )
        as_of = (
            None
            if research.get("as_of", "now") == "now"
            else datetime.fromisoformat(str(research["as_of"]))
        )
        if as_of is not None:
            require_utc(as_of)
        screen = _table(
            root.get("screening", {}),
            {
                "enabled",
                "min_history",
                "momentum_sessions",
                "min_momentum",
                "volatility_sessions",
                "max_volatility",
                "liquidity_sessions",
                "min_dollar_volume",
            },
            set(),
            "screening",
        )
        enabled = _bool(screen.get("enabled", mode == "screening"), "screening.enabled")
        if mode == "screening" and not enabled:
            raise ConfigError("Screening mode requires enabled screening.")
        rules = None
        if enabled:
            arguments = {key: value for key, value in screen.items() if key != "enabled"}
            for key in ("min_momentum", "max_volatility", "min_dollar_volume"):
                if key in arguments:
                    if type(arguments[key]) not in (str, int, Decimal):
                        raise ConfigError("Screen thresholds require decimal strings/numbers.")
                    arguments[key] = Decimal(arguments[key])
            rules = ScreenRules(**arguments)
        elif set(screen) - {"enabled"}:
            raise ConfigError("Disabled screening cannot silently ignore rule settings.")
        storage = _table(
            root.get("storage", {}), {"cache_dir", "ttl_hours", "output_dir"}, set(), "storage"
        )
        network = _table(root.get("network", {}), {"attempts", "timeout"}, set(), "network")
        sessions = (
            tuple(date.fromisoformat(str(d)) for d in data["expected_sessions"])
            if "expected_sessions" in data
            else None
        )
        if sessions is not None and (
            list(sessions) != sorted(set(sessions)) or any(not start <= d < end for d in sessions)
        ):
            raise ConfigError("expected_sessions must be unique ordered dates within the request.")
        return ResearchConfig(
            mode,
            assets,
            watchlist,
            _bool(universe.get("directory_fixture", False), "directory_fixture"),
            _symbols(universe.get("include", [])),
            _symbols(universe.get("exclude", [])),
            adapter,
            file,
            kind,
            start,
            end,
            as_of,
            rules,
            sessions,
            local(storage.get("cache_dir", "data/cache")),
            _int(storage.get("ttl_hours", 24), "ttl_hours"),
            _bool(data.get("offline", False), "offline"),
            _bool(data.get("allow_stale", False), "allow_stale"),
            _int(data.get("max_assets", 20), "max_assets"),
            local(storage.get("output_dir", "outputs/research")),
            _bool(research.get("require_point_in_time", False), "require_point_in_time"),
            RetryPolicy(
                _int(network.get("attempts", 3), "attempts"),
                _int(network.get("timeout", 15), "timeout"),
            ),
        )
    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        KeyError,
        ArithmeticError,
        DataError,
    ) as exc:
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError("Invalid Phase 2 TOML configuration: " + str(exc)) from exc
