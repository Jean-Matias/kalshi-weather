from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from rh_client import RobinhoodCredentials, RobinhoodCryptoClient
from strategy import PriceWindow, dry_run_signal
import rh_database as database


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    args = parse_args()
    
    db_path = Path(__file__).parent / "data" / "quotes.sqlite3"
    database.init_db(db_path)

    if args.recent is not None:
        quotes = database.get_recent_quotes(db_path, limit=args.recent)
        for q in quotes:
            print(f"{q['timestamp']} {q['symbol']} bid={q['bid']} ask={q['ask']} mark={q['mark']} spread={q['spread']}")
        return 0

    credentials = RobinhoodCredentials(
        api_key=os.environ.get("ROBINHOOD_API_KEY", ""),
        private_key_base64=os.environ.get("ROBINHOOD_PRIVATE_KEY_BASE64", ""),
    )
    client = RobinhoodCryptoClient(credentials)
    dry_run = env_bool("BOT_DRY_RUN", default=True)
    allow_live_orders = env_bool("BOT_ALLOW_LIVE_ORDERS", default=False)
    poll_seconds = int(os.environ.get("BOT_POLL_SECONDS", "30"))
    max_notional = Decimal(os.environ.get("BOT_MAX_NOTIONAL_USD", "5"))

    if not dry_run and not allow_live_orders:
        raise SystemExit("Live orders are blocked. Set BOT_ALLOW_LIVE_ORDERS=true intentionally.")

    print(f"Robinhood crypto bot | symbol={args.symbol} | dry_run={dry_run} | max_notional=${max_notional}")
    window = PriceWindow(maxlen=args.window)
    while True:
        quote = client.get_best_bid_ask(args.symbol)
        bid, ask, mark, spread = extract_quote_details(quote)
        
        now = datetime.now(timezone.utc)
        if mark is not None:
            database.insert_quote(
                db_path, timestamp=now, symbol=args.symbol,
                bid=bid, ask=ask, mark=mark, spread=spread
            )
            
        if mark is None:
            print(f"{timestamp()} {args.symbol} quote unavailable: {quote}")
        else:
            window.add(float(mark))
            momentum = window.momentum_pct()
            signal = dry_run_signal(momentum)
            print(
                f"{timestamp()} {args.symbol} mark={mark} "
                f"momentum={format_pct(momentum)} signal={signal} action=DRY_RUN_ONLY"
            )
        if args.once:
            break
        time.sleep(poll_seconds)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Robinhood Crypto dry-run bot")
    parser.add_argument("--symbol", default="BTC-USD", help="Crypto pair, for example BTC-USD")
    parser.add_argument("--window", type=int, default=20, help="Price samples used for momentum")
    parser.add_argument("--once", action="store_true", help="Run one poll and exit")
    parser.add_argument("--recent", type=int, nargs='?', const=10, help="Print recent DB entries without network request")
    args = parser.parse_args()
    if args.recent is not None and args.recent < 1:
        parser.error("--recent must be >= 1")
    return args


def extract_quote_details(quote: dict) -> tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
    results = quote.get("results") if isinstance(quote, dict) else None
    item = results[0] if isinstance(results, list) and results else quote
    if not isinstance(item, dict):
        return None, None, None, None
        
    def get_dec(key: str) -> Decimal | None:
        val = item.get(key)
        if val is not None:
            try:
                return Decimal(str(val))
            except InvalidOperation:
                pass
        return None

    bid = get_dec("bid_price")
    if bid is None:
        bid = get_dec("bid_inclusive_of_sell_spread")
        
    ask = get_dec("ask_price")
    if ask is None:
        ask = get_dec("ask_inclusive_of_buy_spread")
    
    mark = None
    for key in ("mark_price", "price", "ask_inclusive_of_buy_spread", "bid_inclusive_of_sell_spread"):
        val = get_dec(key)
        if val is not None:
            mark = val
            break
            
    if mark is None and bid is not None and ask is not None:
        mark = (bid + ask) / Decimal("2")
        
    spread = None
    if bid is not None and ask is not None:
        spread = ask - bid
        
    return bid, ask, mark, spread


def quote_mark_price(quote: dict) -> Decimal | None:
    _, _, mark, _ = extract_quote_details(quote)
    return mark


def env_bool(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def format_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}%"


def timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    raise SystemExit(main())
