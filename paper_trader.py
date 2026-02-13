import os
import asyncio
import time
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from platforms import PolymarketClient, ManifoldPlatformClient
from matcher import match_events
from arbitrage import find_arbitrage_opportunities
from stats_writer import write_scan_stats

load_dotenv()

# --- Simulation & Filter Settings ---
ORDER_SIZE_USD = 1.0
# Polymarket fee rate (0.2%)
POLYMARKET_FEE_RATE = 0.002
# Manifold fee rate (0% trading fees, but CPMM has slippage)
MANIFOLD_FEE_RATE = 0.0
SCAN_INTERVAL = 60

# Profitability: require this min profit % after fees to consider an arb
MIN_PROFIT_AFTER_FEES_PCT = 0.5
# Don't re-alert the same event within this many seconds
ALERT_COOLDOWN_SECONDS = 30 * 60  # 30 minutes
# Optional: skip events with liquidity below this (0 = disabled)
MIN_LIQUIDITY_USD = 0
# Extra console output (e.g. failed outcomes)
DEBUG = os.getenv("DEBUG", "").strip().lower() in ("1", "true", "yes")

# Event matching settings (adjusted for better matching)
TITLE_SIMILARITY_THRESHOLD = 0.5  # Lowered from 0.7 to catch more potential matches
DATE_MATCH_TOLERANCE_DAYS = 3  # Increased from 1 to 3 days for more flexibility

# Cutoff: 3 days from now
now_utc = datetime.now(timezone.utc)
cutoff_time = now_utc + timedelta(days=3)

def send_telegram_msg(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id): return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram Error: {e}")

async def main():
    # Initialize platform clients
    pm_client = PolymarketClient(
        private_key=os.getenv("POLYMARKET_PRIVATE_KEY"),
        api_key=os.getenv("CLOB_API_KEY"),
        api_secret=os.getenv("CLOB_SECRET"),
        api_passphrase=os.getenv("CLOB_PASSPHRASE")
    )
    
    # Manifold API key is optional (not needed for reading market data)
    manifold_api_key = os.getenv("MANIFOLD_API_KEY")
    manifold_client = ManifoldPlatformClient(api_key=manifold_api_key)

    # Cooldown: event_id -> last alert time
    last_alerted = {}

    print("Cross-Platform Arbitrage Scanner Active")
    print(f"Max resolution: {cutoff_time.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"Min profit after fees: {MIN_PROFIT_AFTER_FEES_PCT}% | Alert cooldown: {ALERT_COOLDOWN_SECONDS // 60} min")
    print(f"Title similarity threshold: {TITLE_SIMILARITY_THRESHOLD} | Date tolerance: {DATE_MATCH_TOLERANCE_DAYS} days")
    
    startup_msg = (
        "Cross-Platform Arb Scanner Online\n"
        f"Min profit: {MIN_PROFIT_AFTER_FEES_PCT}% (after fees) | Cooldown: {ALERT_COOLDOWN_SECONDS // 60} min"
    )
    send_telegram_msg(startup_msg)

    while True:
        try:
            # Fetch events from both platforms in parallel
            pm_events_task = pm_client.get_events(limit=50, max_resolution_days=3)
            manifold_events_task = manifold_client.get_events(limit=50, max_resolution_days=3)
            
            pm_events = await pm_events_task
            manifold_events = await manifold_events_task
            
            if DEBUG:
                print(f"  [DEBUG] Fetched {len(pm_events)} Polymarket events, {len(manifold_events)} Manifold events")
                if pm_events:
                    print(f"  [DEBUG] Sample PM events:")
                    for i, e in enumerate(pm_events[:3]):
                        print(f"    {i+1}. '{e['title'][:60]}' | Resolves: {e['end_date'].strftime('%Y-%m-%d %H:%M')}")
                if manifold_events:
                    print(f"  [DEBUG] Sample Manifold events:")
                    for i, e in enumerate(manifold_events[:3]):
                        print(f"    {i+1}. '{e['title'][:60]}' | Resolves: {e['end_date'].strftime('%Y-%m-%d %H:%M')}")
            
            # Match events between platforms
            matched_events = match_events(
                polymarket_events=pm_events,
                kalshi_events=manifold_events,  # matcher uses generic name but works for any platform
                title_similarity_threshold=TITLE_SIMILARITY_THRESHOLD,
                date_tolerance_days=DATE_MATCH_TOLERANCE_DAYS,
                debug=DEBUG
            )
            
            if DEBUG:
                print(f"  [DEBUG] Matched {len(matched_events)} event pairs")
                if matched_events:
                    for pm_e, m_e in matched_events[:3]:
                        from matcher import calculate_title_similarity
                        sim = calculate_title_similarity(pm_e['title'], m_e['title'])
                        date_diff = abs((pm_e['end_date'] - m_e['end_date']).total_seconds() / 86400)
                        print(f"    Match: '{pm_e['title'][:40]}' <-> '{m_e['title'][:40]}'")
                        print(f"      Similarity: {sim:.3f}, Date diff: {date_diff:.1f} days")
            
            # Find arbitrage opportunities
            opportunities = find_arbitrage_opportunities(
                matched_events=matched_events,
                polymarket_client=pm_client,
                kalshi_client=manifold_client,  # arbitrage uses generic name but works for any platform
                min_profit_pct=MIN_PROFIT_AFTER_FEES_PCT,
                order_size_usd=ORDER_SIZE_USD
            )
            
            ts = datetime.now().strftime("%H:%M:%S")
            alerts_sent = 0

            for opp in opportunities:
                pm_event = opp['pm_event']
                manifold_event = opp['kalshi_event']  # variable name from arbitrage.py
                title = pm_event['title'][:50]
                
                # Format direction for display
                if opp['direction'] == 'pm_yes_kalshi_no':
                    direction_str = "Buy YES on Polymarket + NO on Manifold"
                else:
                    direction_str = "Buy NO on Polymarket + YES on Manifold"
                
                print(
                    f"  | {title} | {direction_str}\n"
                    f"    PM: YES=${opp['pm_price']:.4f} NO=${pm_event['markets'][0]['no_price']:.4f} | "
                    f"Manifold: YES=${manifold_event['markets'][0]['yes_price']:.4f} NO=${opp['kalshi_price']:.4f}\n"
                    f"    Cost=${opp['total_cost']:.4f} Cost+ fees=${opp['total_cost_with_fees']:.4f} "
                    f"Profit=${opp['profit']:.4f} ({opp['profit_pct']:.2f}%)"
                )

                # Create unique event ID for cooldown tracking
                event_id = f"{pm_event['id']}_{manifold_event['id']}_{opp['direction']}"
                
                now = time.time()
                if now - last_alerted.get(event_id, 0) < ALERT_COOLDOWN_SECONDS:
                    continue

                last_alerted[event_id] = now
                alerts_sent += 1
                
                # Get links
                pm_slug = pm_event.get('raw_data', {}).get('slug', '')
                pm_link = f"https://polymarket.com/event/{pm_slug}" if pm_slug else ""
                manifold_id = manifold_event.get('id', '')
                manifold_raw = manifold_event.get('raw_data', {})
                creator_username = manifold_raw.get('creatorUsername', '')
                manifold_slug = manifold_raw.get('slug', '')
                if creator_username and manifold_slug:
                    manifold_link = f"https://manifold.markets/{creator_username}/{manifold_slug}"
                elif manifold_id:
                    manifold_link = f"https://manifold.markets/{manifold_id}"
                else:
                    manifold_link = ""
                
                # Format alert message
                alert = (
                    "*CROSS-PLATFORM ARB*\n"
                    f"{pm_event['title']}\n\n"
                    f"Direction: `{direction_str}`\n"
                    f"Polymarket YES/NO: `${opp['pm_price']:.4f}`/`${pm_event['markets'][0]['no_price']:.4f}`\n"
                    f"Manifold YES/NO: `${manifold_event['markets'][0]['yes_price']:.4f}`/`${opp['kalshi_price']:.4f}`\n"
                    f"Cost (after fees)=`${opp['total_cost_with_fees']:.4f}` Payout=`${opp['payout']:.1f}`\n"
                    f"Profit=`${opp['profit']:.4f}` (`${opp['profit_pct']:.2f}%`)\n"
                )
                if pm_link:
                    alert += f"\nPolymarket: {pm_link}"
                if manifold_link:
                    alert += f"\nManifold: {manifold_link}"
                
                send_telegram_msg(alert)

            print(f"[{ts}] Scanned {len(pm_events)} PM events, {len(manifold_events)} Manifold events, "
                  f"{len(matched_events)} matched, {len(opportunities)} opportunity(ies), {alerts_sent} alerted")

            # Write stats for dashboard
            write_scan_stats(
                pm_events_count=len(pm_events),
                manifold_events_count=len(manifold_events),
                matched_count=len(matched_events),
                opportunities_count=len(opportunities),
                alerts_sent=alerts_sent,
                opportunities=opportunities,
                pm_sample_events=pm_events[:5] if pm_events else None,
                manifold_sample_events=manifold_events[:5] if manifold_events else None,
                matched_pairs=matched_events[:10] if matched_events else None
            )

            await asyncio.sleep(SCAN_INTERVAL)

        except Exception as e:
            print(f"Loop error: {e}")
            import traceback
            if DEBUG:
                traceback.print_exc()
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
