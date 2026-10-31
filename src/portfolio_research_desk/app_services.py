"""Confined local use cases. No Streamlit, CLI subprocesses or financial calculations."""

import csv
import io
import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

from portfolio_research_desk.app_contracts import FactorRequest, HistoryRequest, TaskRef
from portfolio_research_desk.data_adapters import LocalHistoryAdapter, YFinanceAdapter
from portfolio_research_desk.delivery_reports import bundle_hashes, file_hash, write_json
from portfolio_research_desk.diagnostics import inspect_environment
from portfolio_research_desk.domain import AssetId, fingerprint, jsonable
from portfolio_research_desk.errors import DataError, ReportError
from portfolio_research_desk.factor_config import FactorConfig
from portfolio_research_desk.factor_reporting import save_factor_report
from portfolio_research_desk.factor_workflow import run_factor_research
from portfolio_research_desk.research_config import load_research_config
from portfolio_research_desk.research_workflow import run_research, save_research_run
from portfolio_research_desk.universe import custom_universe, load_watchlist, save_watchlist
from portfolio_research_desk.workspace import create_workspace


def preview_watchlist(text, synthetic):
    """Explicit CSV identities, with visible duplicates; never infer exchanges."""
    try:
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
        if reader.fieldnames != ["market", "exchange", "symbol", "currency"]:
            raise DataError("列名必须为 market,exchange,symbol,currency。")
        assets, duplicates, errors = [], [], []
        for line, row in enumerate(reader, 2):
            try:
                asset = AssetId(**{k: v.strip().upper() for k, v in row.items()})
                custom_universe((asset,), datetime(2024, 1, 1, tzinfo=UTC), synthetic)
                if asset.exchange not in {"XNAS", "XNYS", "XASE", "ARCX", "BATS"}:
                    raise DataError("请确认支持的美国交易所 MIC，不能猜测证券身份。")
                if asset in assets:
                    duplicates.append(line)
                else:
                    assets.append(asset)
            except (TypeError, AttributeError, DataError) as exc:
                errors.append(f"第 {line} 行：{exc}")
        if not assets:
            errors.append("至少需要一只具有完整身份的证券。")
        return tuple(assets), duplicates, errors
    except (csv.Error, TypeError, AttributeError) as exc:
        raise DataError("无法读取自选股表格。") from exc


class DeskService:
    def __init__(self, root: Path, clock=lambda: datetime.now(UTC)):
        self.root = Path(root).expanduser().resolve()
        self.clock = clock

    def path(self, relative):
        value = Path(relative)
        if value.is_absolute() or ".." in value.parts or not value.parts:
            raise DataError("只能选择当前工作区内的相对路径。")
        candidate = (self.root / value).resolve()
        if not candidate.is_relative_to(self.root):
            raise DataError("路径不能离开当前工作区。")
        return candidate

    def relative(self, path):
        return Path(path).resolve().relative_to(self.root).as_posix()

    def create(self):
        create_workspace(self.root)

    def inspect(self):
        if not self.root.is_dir() or not (self.root / "workflow.toml").is_file():
            raise DataError("请选择已有 PRD 工作区，或使用“创建工作区”。")
        return inspect_environment()

    def capabilities(self):
        environment = inspect_environment()
        return {
            "factors": environment["extras"]["factors"]["available"],
            "live_data": environment["extras"]["data"]["available"],
            "real_backtest": False,
            "paper_writes": False,
            "broker": False,
        }

    def require(self, capability):
        if not self.capabilities().get(capability, False):
            raise DataError(f"当前版本不支持或尚未安装此能力：{capability}。")

    def save_list(self, name, assets, synthetic):
        self.inspect()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", name):
            raise DataError("列表名称请用 1–48 位字母、数字、短横线或下划线。")
        snapshot = custom_universe(tuple(assets), self.clock(), synthetic)
        for asset in assets:
            if asset.exchange not in {"XNAS", "XNYS", "XASE", "ARCX", "BATS"}:
                raise DataError("交易所身份不受支持。")
        # Versioned immutable files; saving an identical list reuses its version.
        key = fingerprint({"assets": assets, "synthetic": synthetic})[:16]
        path = self.path(f"gui/watchlists/{name}-{key}.json")
        if path.exists():
            existing = load_watchlist(path)
            if existing.assets != snapshot.assets or existing.synthetic != synthetic:
                raise DataError("已保存列表与输入不一致。")
        else:
            save_watchlist(snapshot, path)
        return self.relative(path)

    def lists(self):
        return sorted(self.relative(p) for p in self.path("gui/watchlists").glob("*.json"))

    def load_list(self, relative):
        return load_watchlist(self.path(relative))

    def _execute(self, command_id, kind, inputs, operation):
        self.inspect()
        if not re.fullmatch(r"[a-f0-9]{32}", command_id):
            raise DataError("任务编号无效，请创建新任务。")
        directory = self.path(f"gui/tasks/{command_id}")
        request_hash = fingerprint({"kind": kind, "inputs": inputs})
        if directory.exists():
            request = self._json(directory / "request.json")
            if request["request_hash"] != request_hash:
                raise DataError("任务输入已变化，请点击“新实验 / 重试”后提交。")
            return self.task(command_id)
        # mkdir is the exclusive writer guard, including other tabs/processes.
        try:
            directory.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise DataError("该任务正在运行，请刷新结果，或创建新任务。") from exc
        write_json(directory / "request.json", {"request_hash": request_hash, "inputs": inputs})
        try:
            output, status, data_kind = operation(directory)
            ref = TaskRef(
                command_id,
                kind,
                status,
                self.clock().isoformat(),
                self.relative(output),
                data_kind,
            )
            hashes = bundle_hashes(directory)
            write_json(directory / "result.json", {"task": jsonable(ref), "files": hashes})
            return ref
        except Exception as exc:
            write_json(directory / "failure.json", {"reason": str(exc), "kind": kind})
            raise

    @staticmethod
    def _json(path):
        try:
            return json.loads(path.read_text("utf-8"))
        except (OSError, ValueError) as exc:
            raise DataError("结果不存在、尚未完成或无法读取，请新建任务后重试。") from exc

    def task(self, command_id):
        if not re.fullmatch(r"[a-f0-9]{32}", command_id):
            raise DataError("任务编号无效。")
        directory = self.path(f"gui/tasks/{command_id}")
        if not (directory / "result.json").exists() and (directory / "failure.json").exists():
            failure = self._json(directory / "failure.json")
            raise DataError(f"任务失败：{failure['reason']}；请创建新任务后重试。")
        result = self._json(directory / "result.json")
        actual = bundle_hashes(directory)
        actual.pop("result.json", None)
        if actual != result["files"]:
            raise DataError("结果完整性校验失败：文件缺失或已变化。")
        ref = TaskRef(**result["task"])
        if not self.path(ref.directory).is_relative_to(directory):
            raise DataError("结果引用离开了对应任务目录。")
        return ref

    def tasks(self):
        results = []
        for path in self.path("gui/tasks").glob("*/request.json"):
            try:
                results.append((self.task(path.parent.name), None))
            except (DataError, ReportError, OSError, TypeError, KeyError) as exc:
                results.append((None, f"{path.parent.name}: {exc}"))
        return sorted(
            results, key=lambda item: item[0].generated_at if item[0] else "", reverse=True
        )

    def fetch(self, request: HistoryRequest, command_id):
        if request.start >= request.end:
            raise DataError("开始日期必须早于结束日期（不含）。")
        if request.source not in {"synthetic", "local", "yfinance"}:
            raise DataError("数据来源不受支持。")
        custom_universe(request.assets, datetime.now(UTC), request.expected_kind == "synthetic")
        if request.source == "synthetic":
            if request.expected_kind != "synthetic" or request.assets != (
                AssetId("US", "XNAS", "SYN_FACTOR", "USD"),
            ):
                raise DataError("内置研究样例仅支持 SYN_FACTOR；不能替代真实证券。")
            local = Path(
                str(files("portfolio_research_desk").joinpath("resources/factor_prices.csv"))
            )
        elif request.source == "local":
            local = self.path(request.local_file) if request.local_file else None
            if not local or local.suffix.lower() not in {".csv", ".parquet"}:
                raise DataError("请选择工作区内原生 CSV（含元数据）或 Parquet 文件。")
        else:
            self.require("live_data")
            if request.expected_kind != "real":
                raise DataError("在线来源必须显式声明为真实数据。")
            if request.refresh and not request.network_allowed:
                raise DataError("离线模式不能刷新网络数据。")
            local = None
        base = load_research_config()

        def operation(directory):
            config = replace(
                base,
                universe_mode="custom",
                assets=request.assets,
                watchlist=None,
                directory_fixture=False,
                include=(),
                exclude=(),
                rules=None,
                adapter="yfinance" if local is None else local.suffix.lstrip("."),
                local_file=local,
                expected_kind=request.expected_kind,
                start=request.start,
                end=request.end,
                as_of=None,
                expected_sessions=None,
                cache_dir=self.path("gui/cache/history"),
                output_dir=directory / "outputs",
                offline=not request.network_allowed,
                allow_stale=request.allow_stale,
                require_point_in_time=False,
                max_assets=max(20, len(request.assets)),
            )
            adapter = None
            if request.source == "yfinance" and not request.network_allowed:
                # Preserve the existing adapter/cache identity without importing a live provider.
                # The backend rejects cache misses before fetch; this guard is defense in depth.
                def no_network(*_):
                    raise DataError("离线模式不允许网络请求。")

                adapter = YFinanceAdapter(config.cache_dir, factory=no_network)
                adapter.version = version("yfinance")
            result = run_research(
                config, "data", adapter=adapter, refresh=request.refresh, clock=self.clock
            )
            output = save_research_run(result, config)
            return output, result.status, request.expected_kind

        inputs = jsonable(
            replace(request, local_file=str(request.local_file) if request.local_file else None)
        )
        if local:
            inputs["source_hash"] = LocalHistoryAdapter(local).cache_identity()
        return self._execute(command_id, "history", inputs, operation)

    def histories(self, ref):
        ref = self.task(ref.command_id)
        if ref.kind != "history":
            raise DataError("请选择行情任务。")
        document = self._json(self.path(ref.directory) / "run.json")
        return [
            (AssetId(**item["asset"]), self.relative(self.path(ref.directory) / item["csv"]))
            for item in document["history_files"]
        ]

    def history_result(self, ref):
        ref = self.task(ref.command_id)
        if ref.kind != "history":
            raise DataError("请选择行情任务。")
        return self._json(self.path(ref.directory) / "run.json")["result"]

    def history(self, relative):
        # Only an exact exported reference of a verified acquisition may enter research.
        path = self.path(relative)
        parts = path.relative_to(self.root).parts
        if len(parts) < 4 or parts[:2] != ("gui", "tasks"):
            raise DataError("研究必须使用已保存并校验的行情快照。")
        ref = self.task(parts[2])
        if relative not in [p for _, p in self.histories(ref)]:
            raise DataError("不是已保存的行情引用。")
        return LocalHistoryAdapter(path).read()

    def factor_config(self, request: FactorRequest):
        self.require("factors")
        history = self.history(request.history_file)
        assets = set(r.asset for r in history.rows)
        if len(assets) != 1:
            raise DataError("因子研究需要准确的一只证券。")
        if request.source not in {"synthetic", "local"}:
            raise DataError("首版使用内置合成因子或本地 French 格式文件。")
        return FactorConfig(
            frequency=request.frequency,
            factor_source=request.source,
            expected_kind=history.data_kind,
            start=request.start,
            end=request.end,
            price_file=self.path(request.history_file),
            asset_symbol=next(iter(assets)).symbol,
            ff3_file=self.path(request.ff3_file) if request.ff3_file else None,
            momentum_file=self.path(request.momentum_file) if request.momentum_file else None,
            sessions_file=self.path(request.sessions_file) if request.sessions_file else None,
            covariance=request.covariance,
            confidence=request.confidence,
            min_obs=request.min_obs,
            rolling_window=request.rolling_window,
            return_basis=request.return_basis,
            offline=True,
            cache_dir=self.path("gui/cache/factors"),
            output_dir=self.path("gui/tasks"),
        )

    def check_factor(self, request):
        # Real backend preparation/fit, no persisted run or side effect. It is ex-post only.
        return run_factor_research(self.factor_config(request), clock=self.clock)

    def study(self, request, command_id):
        config = self.factor_config(request)
        inputs = config.snapshot()
        for name in ("price_file", "ff3_file", "momentum_file", "sessions_file"):
            path = getattr(config, name)
            if path:
                inputs[name + "_hash"] = file_hash(path)

        def operation(directory):
            result = run_factor_research(config, clock=self.clock)
            output = save_factor_report(result, directory / "outputs", "factor")
            return output, result.status, config.expected_kind

        return self._execute(command_id, "factor", inputs, operation)

    def factor_data(self, ref):
        ref = self.task(ref.command_id)
        if ref.kind != "factor":
            raise DataError("请选择因子研究结果。")
        directory = self.path(ref.directory)
        return {
            name: self._json(directory / f"{name}.json")
            for name in (
                "run",
                "analysis",
                "alignment",
                "rolling",
                "price_snapshot",
                "factor_snapshot",
            )
        }

    def demo(self, command_id):
        from portfolio_research_desk.product_workflow import run_workflow
        from portfolio_research_desk.workflow_config import WorkflowConfig

        def operation(directory):
            result = run_workflow(WorkflowConfig(output_dir=directory / "outputs"), "demo")
            return Path(result["report_directory"]), "complete", "synthetic"

        return self._execute(command_id, "demo", {"initial_cash_cad": "3000.00"}, operation)

    def read_account(self, relative):
        from portfolio_research_desk.paper_services import account_summary
        from portfolio_research_desk.paper_store import PaperAccount

        path = self.path(relative)
        if not path.is_file():
            raise DataError("账户文件不存在。")
        return account_summary(PaperAccount(path))
