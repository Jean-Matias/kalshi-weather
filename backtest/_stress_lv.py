import statistics as st
from collections import Counter
import data, engine, strategies

ds = data.load_dataset("Las Vegas")
strat = strategies.quick_scalp(profit_target_cents=8, stop_loss_cents=8)

# Reproduce run_flip but capture entry diagnostics
records = []
for entry in ds:
    event = entry["event"]
    buckets = engine._build_buckets(event, entry["bucket_candles"])
    if not buckets:
        continue
    max_idx = min(len(b["prices"]) for b in buckets) - 1
    if max_idx < 1:
        continue
    decision = None
    entry_idx = None
    for idx in range(1, min(30, max_idx) + 1):
        if any(b["prices"][idx] is None for b in buckets):
            continue
        cand = strat(event, buckets, idx)
        if cand is not None:
            decision = cand
            entry_idx = idx
            break
    if decision is None:
        continue
    bucket = next(b for b in buckets if b["ticker"] == decision["bucket"])
    entry_price = max(1, min(99, int(decision["entry_price"])))
    tp = int(decision["take_profit"]); sl = int(decision["stop_loss"])

    # spread at entry
    yes_ask = bucket["prices"][entry_idx]
    yes_bid = bucket["bids"][entry_idx]
    spread = (yes_ask - yes_bid) if (yes_ask is not None and yes_bid is not None) else None

    # find raw candle for volume/OI
    cands = entry["bucket_candles"].get(bucket["ticker"]) or []
    rows = sorted(cands, key=lambda c: c.get("end_period_ts") or 0)
    vol = oi = None
    if entry_idx < len(rows):
        vol = rows[entry_idx].get("volume_fp")
        oi = rows[entry_idx].get("open_interest_fp")
        vol = float(vol) if vol is not None else None
        oi = float(oi) if oi is not None else None

    # tie check: how many buckets within 2c of the favorite at entry_idx
    scored = [(b["ticker"], b["prices"][entry_idx]) for b in buckets if b["prices"][entry_idx] is not None]
    fav_price = max(p for _, p in scored)
    near_ties = sum(1 for _, p in scored if fav_price - p <= 2 and p != fav_price)

    exit_price = None
    for h in range(entry_idx + 1, min(entry_idx + 12, max_idx) + 1):
        bid = bucket["bids"][h]
        if bid is None:
            continue
        if bid >= tp or bid <= sl:
            exit_price = bid
            break

    if exit_price is not None:
        gross = (exit_price - entry_price) * 3
        net = gross - int(2*1.5*3)
        won = gross > 0
        exited_early = True
    else:
        won = bucket["result"] == "yes"
        gross = (100 - entry_price)*3 if won else -entry_price*3
        net = gross - int(1.5*3)
        exited_early = False

    # missing candle check hours 0-2
    missing_0_2 = sum(1 for h in (0,1,2) if h <= max_idx and any(b["prices"][h] is None for b in buckets))

    records.append(dict(
        event=event["event_ticker"], entry_idx=entry_idx, entry_price=entry_price,
        spread=spread, vol=vol, oi=oi, near_ties=near_ties,
        exited_early=exited_early, won=won, net=net, missing_0_2=missing_0_2,
        open_ts=event["open_ts"],
    ))

print(f"n trades = {len(records)}")

# 1. spread at entry
spreads = [r["spread"] for r in records if r["spread"] is not None]
print(f"\n1. SPREAD at entry: n={len(spreads)} avg={st.mean(spreads):.2f}c median={st.median(spreads)}c "
      f"min={min(spreads)} max={max(spreads)}")
print("   spread distribution:", Counter(spreads).most_common())
print("   entry hour distribution:", Counter(r["entry_idx"] for r in records).most_common())

# 2. volume/OI
vols = [r["vol"] for r in records if r["vol"] is not None]
ois = [r["oi"] for r in records if r["oi"] is not None]
print(f"\n2. VOLUME at entry hour: n={len(vols)} avg={st.mean(vols):.1f} median={st.median(vols)} "
      f"zero_count={sum(1 for v in vols if v==0)}")
print(f"   OPEN INTEREST at entry hour: n={len(ois)} avg={st.mean(ois):.1f} median={st.median(ois)} "
      f"zero_count={sum(1 for v in ois if v==0)}")

# 3. ties
tie_ct = Counter(r["near_ties"] for r in records)
print(f"\n3. Near-ties (other buckets within 2c of favorite) at entry: {dict(tie_ct)}")

# 4. early exit vs settlement fallback
early = [r for r in records if r["exited_early"]]
fallback = [r for r in records if not r["exited_early"]]
def stats(rs, label):
    if not rs:
        print(f"   {label}: none")
        return
    wr = 100*sum(1 for r in rs if r["won"])/len(rs)
    ev = sum(r["net"] for r in rs)/len(rs)
    print(f"   {label}: n={len(rs)} win_rate={wr:.1f}% EV/trade={ev:+.2f}c total={sum(r['net'] for r in rs):+d}c")
print(f"\n4. Early-exit vs settlement-fallback split:")
stats(early, "exited early (TP/SL)")
stats(fallback, "settlement fallback")

# 5. tail risk
losses = sorted([r["net"] for r in records if not r["won"]])
print(f"\n5. Worst single-trade loss: {losses[0]:+d}c (${losses[0]/100:.2f})  -- top 5 worst: {losses[:5]}")
# longest losing streak chronological
recs_sorted = sorted(records, key=lambda r: r["open_ts"])
streak = best = 0
for r in recs_sorted:
    if not r["won"]:
        streak += 1
        best = max(best, streak)
    else:
        streak = 0
print(f"   Longest consecutive losing streak: {best}")

# 6. missing candle data near entry
miss = sum(1 for r in records if r["missing_0_2"] > 0)
print(f"\n6. Trades where hours 0-2 had missing candle data on at least one bucket: {miss}/{len(records)}")
print(f"   distribution of missing-hour counts: {Counter(r['missing_0_2'] for r in records)}")
