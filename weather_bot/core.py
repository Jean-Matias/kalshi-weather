from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from backtest import low_data, low_strategies, low_weather
from backtest.engine import split_chronological
from backtest.low_engine import run_low_backtest
from backtest.market_specs import low_market_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_STATE_PATH = REPO_ROOT / "data" / "weather_bot_controls.json"


@dataclass(frozen=True)
class BotDefinition:
    bot_id: str
    name: str
    market_type: str
    city: str
    strategy_name: str
    decision_hour: int
    contracts: int = 3
    max_contracts: int = 10
    daily_loss_limit_cents: int = 300
    mode: str = "paper"
    trading_enabled: bool = False


@dataclass(frozen=True)
class BotControlState:
    armed: bool = False
    contracts: int = 3


DEFAULT_BOTS = [
    BotDefinition(
        bot_id="vegas-low-confirmation",
        name="Vegas Low Confirmation",
        market_type="low",
        city="Las Vegas",
        strategy_name="low_weather_confirmed",
        decision_hour=3,
        contracts=3,
    )
]


def bot_summaries(*, state_path: Path = CONTROL_STATE_PATH) -> list[dict[str, Any]]:
    summaries = []
    for bot in DEFAULT_BOTS:
        control = get_bot_control(bot.bot_id, state_path=state_path)
        summaries.append(
            {
                "bot_id": bot.bot_id,
                "name": bot.name,
                "market_type": bot.market_type,
                "city": bot.city,
                "strategy_name": bot.strategy_name,
                "decision_hour": bot.decision_hour,
                "contracts": control.contracts,
                "max_contracts": bot.max_contracts,
                "armed": control.armed,
                "mode": bot.mode,
                "trading_enabled": bot.trading_enabled,
            }
        )
    return summaries


def get_bot(bot_id: str) -> BotDefinition:
    for bot in DEFAULT_BOTS:
        if bot.bot_id == bot_id:
            return bot
    raise KeyError(bot_id)


def get_bot_control(bot_id: str, *, state_path: Path = CONTROL_STATE_PATH) -> BotControlState:
    bot = get_bot(bot_id)
    raw_state = _load_control_state(state_path)
    bot_state = raw_state.get(bot_id, {})
    contracts = int(bot_state.get("contracts", bot.contracts))
    if contracts < 1 or contracts > bot.max_contracts:
        contracts = bot.contracts
    return BotControlState(
        armed=bool(bot_state.get("armed", False)),
        contracts=contracts,
    )


def update_bot_control(
    bot_id: str,
    *,
    armed: bool | None = None,
    contracts: int | None = None,
    state_path: Path = CONTROL_STATE_PATH,
) -> BotControlState:
    bot = get_bot(bot_id)
    current = get_bot_control(bot_id, state_path=state_path)
    next_armed = current.armed if armed is None else bool(armed)
    next_contracts = current.contracts if contracts is None else int(contracts)
    if next_contracts < 1 or next_contracts > bot.max_contracts:
        raise ValueError(f"contracts must be between 1 and {bot.max_contracts}")

    next_control = BotControlState(armed=next_armed, contracts=next_contracts)
    raw_state = _load_control_state(state_path)
    raw_state[bot_id] = {"armed": next_control.armed, "contracts": next_control.contracts}
    _save_control_state(raw_state, state_path)
    return next_control


def build_bot_snapshot(
    bot: BotDefinition,
    *,
    days: int = 60,
    state_path: Path = CONTROL_STATE_PATH,
) -> dict[str, Any]:
    if bot.market_type != "low":
        raise ValueError("Only low-temperature paper bots are currently supported.")

    control = get_bot_control(bot.bot_id, state_path=state_path)
    active_bot = replace(bot, contracts=control.contracts)
    spec = low_market_spec(bot.city)
    dataset = low_data.load_dataset(bot.city, days=days)
    strategy = low_strategies.REGISTRY[bot.strategy_name]()
    result = run_low_backtest(
        dataset,
        strategy,
        weather_loader=lambda event: low_weather.load_history_for_event(spec, event),
        contracts=active_bot.contracts,
        label=f"{bot.name} h{bot.decision_hour}",
        decision_hour=bot.decision_hour,
    )
    older, newer = split_chronological(result.report)
    paper_trades = [_trade_payload(trade) for trade in sorted(result.report.trades, key=lambda item: item.open_ts)[-12:]]
    return {
        "bot_id": bot.bot_id,
        "name": bot.name,
        "mode": bot.mode,
        "trading_enabled": bot.trading_enabled,
        "armed": control.armed,
        "city": bot.city,
        "market_type": bot.market_type,
        "strategy_name": bot.strategy_name,
        "decision_hour": bot.decision_hour,
        "contracts": active_bot.contracts,
        "max_contracts": active_bot.max_contracts,
        "backtest": {
            "event_days": result.total_event_days,
            "trades": result.report.n,
            "skips": len(result.skipped),
            "win_rate": round(result.report.win_rate, 1),
            "ev_per_trade_cents": round(result.report.ev_per_trade, 2),
            "total_net_cents": result.report.total_net_cents,
            "worst_drawdown_cents": result.worst_drawdown_cents,
            "older_ev_per_trade_cents": round(older.ev_per_trade, 2),
            "newer_ev_per_trade_cents": round(newer.ev_per_trade, 2),
        },
        "risk_gates": _risk_gates(active_bot, result, control),
        "paper_trades": paper_trades,
        "signal": _signal_payload(active_bot, result, control),
    }


def _risk_gates(bot: BotDefinition, result, control: BotControlState) -> list[dict[str, Any]]:
    return [
        {
            "name": "Real order placement",
            "status": "blocked",
            "detail": "Disabled in this research workspace. Paper mode only.",
            "ok": True,
        },
        {
            "name": "Paper bot armed",
            "status": "pass" if control.armed else "off",
            "detail": "Paper signal tracking is on." if control.armed else "Paper signal tracking is off.",
            "ok": True,
        },
        {
            "name": "Contract cap",
            "status": "pass" if bot.contracts <= bot.max_contracts else "fail",
            "detail": f"{bot.contracts} / {bot.max_contracts} contracts",
            "ok": bot.contracts <= bot.max_contracts,
        },
        {
            "name": "Sample size",
            "status": "watch" if result.report.n < 30 else "pass",
            "detail": f"{result.report.n} historical trades",
            "ok": result.report.n >= 10,
        },
        {
            "name": "Expected value",
            "status": "pass" if result.report.ev_per_trade > 0 else "fail",
            "detail": f"{result.report.ev_per_trade:+.2f}c per trade",
            "ok": result.report.ev_per_trade > 0,
        },
        {
            "name": "Loss guard",
            "status": "pass" if abs(result.worst_drawdown_cents) <= bot.daily_loss_limit_cents else "watch",
            "detail": f"worst drawdown {result.worst_drawdown_cents:+d}c",
            "ok": abs(result.worst_drawdown_cents) <= bot.daily_loss_limit_cents,
        },
    ]


def _trade_payload(trade) -> dict[str, Any]:
    return {
        "event_ticker": trade.event_ticker,
        "bucket": trade.bucket,
        "side": trade.side.upper(),
        "price_cents": trade.limit_price,
        "net_cents": trade.net_cents,
        "status": "won" if trade.won else "lost",
    }


def _signal_payload(bot: BotDefinition, result, control: BotControlState) -> dict[str, Any]:
    last_trade = sorted(result.report.trades, key=lambda item: item.open_ts)[-1:] or [None]
    trade = last_trade[0]
    if not control.armed:
        return {
            "label": "Paper bot off",
            "action": "paper-disabled",
            "confidence": "disabled",
            "why": "The Vegas confirmation bot is built but paper signal tracking is turned off.",
            "last_bucket": trade.bucket if trade else None,
        }
    return {
        "label": "Weather-confirmed favorite",
        "action": "paper-buy-yes" if trade else "skip",
        "confidence": "candidate" if result.report.ev_per_trade > 0 else "avoid",
        "why": (
            "Weather target and Kalshi favorite agree inside the entry band."
            if trade
            else "No qualifying historical signal in the current window."
        ),
        "last_bucket": trade.bucket if trade else None,
    }


def _load_control_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _save_control_state(state: dict[str, Any], state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
