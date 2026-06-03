from __future__ import annotations

import re
from typing import Any

from config import PLAYWRIGHT_TIMEOUT_MS


def fetch_kalshi_market(city_config: dict[str, Any]) -> dict[str, Any]:
    url = city_config.get("kalshi_url")
    market = _empty_market(city_config)
    if not url:
        market["warnings"].append("No Kalshi URL configured.")
        return market

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        market["warnings"].append(
            f"Playwright unavailable: {exc}. Install requirements and run browser install."
        )
        return market

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT_MS)
            page.wait_for_timeout(2500)
            text = page.locator("body").inner_text(timeout=PLAYWRIGHT_TIMEOUT_MS)
            title = page.title()
            browser.close()
    except Exception as exc:
        market["warnings"].append(f"Kalshi scrape failed: {exc}")
        return market

    market.update(_parse_visible_market_text(text, city_config))
    if not market.get("market_title"):
        market["market_title"] = title or f"{city_config['city']} weather market"
    market["url"] = url
    return market


def _empty_market(city_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "city": city_config["city"],
        "url": city_config.get("kalshi_url"),
        "market_title": None,
        "contract_title": None,
        "kalshi_price": None,
        "implied_probability": None,
        "bid": None,
        "ask": None,
        "volume": None,
        "recent_move_cents": None,
        "contracts": [],
        "range_low_f": None,
        "range_high_f": None,
        "official_source_text": None,
        "official_source_url": city_config.get("official_source_url"),
        "raw_text_excerpt": None,
        "warnings": [],
    }


def _parse_visible_market_text(text: str, city_config: dict[str, Any]) -> dict[str, Any]:
    city = city_config["city"]
    text = _normalize_visible_text(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    heading = next((line for line in lines if line.lower().startswith("highest temperature")), None)
    matching = [line for line in lines if city.lower() in line.lower() or "temperature" in line.lower()]
    window = "\n".join(lines[:140])
    contracts = _parse_contracts(lines)
    selected = _select_contract(contracts)

    cents = selected.get("yes_price") if selected else _first_number(r"(\d{1,2})\s*[¢\u00a2]", window)
    percent = _first_number(r"(\d{1,3})\s*%", window)
    bid = _first_number(r"Bid\s*(\d{1,2})", window, flags=re.I)
    ask = _first_number(r"Ask\s*(\d{1,2})", window, flags=re.I)
    volume = _first_number(r"Volume\s*\$?([\d,]+)", window, flags=re.I)
    recent_move = _first_number(r"([+-]?\d{1,2})\s*[¢\u00a2]", window)

    implied_probability = None
    if cents is not None:
        implied_probability = cents / 100
    elif percent is not None:
        implied_probability = percent / 100

    if selected and selected.get("no_price") is not None:
        bid = 100 - selected["no_price"]
    if selected and selected.get("yes_price") is not None:
        ask = selected["yes_price"]

    title = heading or (matching[0] if matching else None)
    contract_title = selected.get("label") if selected else title
    official_text = next(
        (
            line
            for line in lines
            if "Climatological Report" in line or "Data for CLI" in line
        ),
        None,
    )
    return {
        "market_title": title,
        "contract_title": contract_title,
        "kalshi_price": cents,
        "implied_probability": implied_probability,
        "bid": bid,
        "ask": ask,
        "volume": volume,
        "recent_move_cents": recent_move,
        "contracts": contracts,
        "range_low_f": selected.get("low_f") if selected else None,
        "range_high_f": selected.get("high_f") if selected else None,
        "official_source_text": official_text,
        "raw_text_excerpt": window[:1500],
    }


def _parse_contracts(lines: list[str]) -> list[dict[str, Any]]:
    contracts = []
    seen: set[tuple[str, float | None, float | None]] = set()
    for index, line in enumerate(lines):
        temp_range = _parse_temp_range(line)
        if not temp_range:
            continue
        key = (line, temp_range[0], temp_range[1])
        if key in seen:
            continue
        seen.add(key)
        nearby = lines[index + 1 : index + 5]
        yes_price = _price_after_label("Yes", nearby)
        no_price = _price_after_label("No", nearby)
        contracts.append(
            {
                "label": line,
                "low_f": temp_range[0],
                "high_f": temp_range[1],
                "yes_price": yes_price,
                "no_price": no_price,
            }
        )
    return contracts


def _normalize_visible_text(text: str) -> str:
    return (
        text.replace("Â°", "°")
        .replace("Â¢", "¢")
        .replace("\u00a0", " ")
    )


def _parse_temp_range(text: str) -> tuple[float | None, float | None] | None:
    below = re.match(r"^(\d{1,3})°\s+or below$", text, flags=re.I)
    if below:
        return None, float(below.group(1))
    above = re.match(r"^(\d{1,3})°\s+or above$", text, flags=re.I)
    if above:
        return float(above.group(1)), None
    between = re.match(r"^(\d{1,3})°\s+to\s+(\d{1,3})°$", text, flags=re.I)
    if between:
        return float(between.group(1)), float(between.group(2))
    return None


def _price_after_label(label: str, lines: list[str]) -> float | None:
    for line in lines:
        if line.startswith(label):
            return _first_number(r"(\d{1,2})\s*[¢\u00a2]", line)
    return None


def _select_contract(contracts: list[dict[str, Any]]) -> dict[str, Any] | None:
    priced = [contract for contract in contracts if contract.get("yes_price") is not None]
    if not priced:
        return None
    return max(priced, key=lambda contract: contract["yes_price"])


def _first_number(pattern: str, text: str, flags: int = 0) -> float | None:
    match = re.search(pattern, text, flags=flags)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None
