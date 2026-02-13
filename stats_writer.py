"""
Shared state writer for dashboard communication.
Writes scan statistics to a JSON file that the dashboard can read.
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path

STATS_FILE = Path(__file__).parent / "dashboard_stats.json"


def write_scan_stats(
    pm_events_count: int,
    manifold_events_count: int,
    matched_count: int,
    opportunities_count: int,
    alerts_sent: int,
    opportunities: List[Dict],
    pm_sample_events: Optional[List[Dict]] = None,
    manifold_sample_events: Optional[List[Dict]] = None,
    matched_pairs: Optional[List[tuple]] = None
):
    """
    Write scan statistics to shared JSON file for dashboard.
    
    Args:
        pm_events_count: Number of Polymarket events fetched
        manifold_events_count: Number of Manifold events fetched
        matched_count: Number of matched event pairs
        opportunities_count: Number of arbitrage opportunities found
        alerts_sent: Number of alerts sent this scan
        opportunities: List of opportunity dictionaries
        pm_sample_events: Sample Polymarket events (for display)
        manifold_sample_events: Sample Manifold events (for display)
        matched_pairs: List of matched event pairs
    """
    try:
        # Read existing stats if file exists
        if STATS_FILE.exists():
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
        else:
            stats = {
                'scan_history': [],
                'total_scans': 0,
                'total_opportunities': 0,
                'total_alerts': 0,
                'best_opportunity': None,
                'last_scan': None
            }
        
        # Prepare current scan data
        current_scan = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'pm_events': pm_events_count,
            'manifold_events': manifold_events_count,
            'matched': matched_count,
            'opportunities_count': opportunities_count,
            'alerts_sent': alerts_sent,
            'opportunities': [
                {
                    'title': opp.get('pm_event', {}).get('title', '')[:60],
                    'direction': opp.get('direction', ''),
                    'profit_pct': opp.get('profit_pct', 0),
                    'profit': opp.get('profit', 0),
                    'pm_yes': opp.get('pm_price', 0),
                    'pm_no': opp.get('pm_event', {}).get('markets', [{}])[0].get('no_price', 0),
                    'manifold_yes': opp.get('kalshi_event', {}).get('markets', [{}])[0].get('yes_price', 0),
                    'manifold_no': opp.get('kalshi_price', 0),
                }
                for opp in opportunities
            ]
        }
        
        # Add sample events if provided
        if pm_sample_events:
            current_scan['pm_sample'] = [
                {
                    'title': e.get('title', '')[:60],
                    'end_date': e.get('end_date').isoformat() if e.get('end_date') else None,
                    'markets_count': len(e.get('markets', []))
                }
                for e in pm_sample_events[:5]
            ]
        
        if manifold_sample_events:
            current_scan['manifold_sample'] = [
                {
                    'title': e.get('title', '')[:60],
                    'end_date': e.get('end_date').isoformat() if e.get('end_date') else None,
                    'markets_count': len(e.get('markets', []))
                }
                for e in manifold_sample_events[:5]
            ]
        
        # Add matched pairs info if provided
        if matched_pairs:
            current_scan['matched_details'] = [
                {
                    'pm_title': pm.get('title', '')[:50],
                    'manifold_title': mf.get('title', '')[:50],
                    'pm_end_date': pm.get('end_date').isoformat() if pm.get('end_date') else None,
                    'manifold_end_date': mf.get('end_date').isoformat() if mf.get('end_date') else None,
                }
                for pm, mf in matched_pairs[:10]
            ]
        
        # Update stats
        stats['scan_history'].append(current_scan)
        stats['total_scans'] = len(stats['scan_history'])
        stats['total_opportunities'] += opportunities_count
        stats['total_alerts'] += alerts_sent
        stats['last_scan'] = current_scan
        
        # Keep only last 100 scans in history
        if len(stats['scan_history']) > 100:
            stats['scan_history'] = stats['scan_history'][-100:]
        
        # Track best opportunity
        if opportunities:
            best = max(opportunities, key=lambda x: x.get('profit_pct', 0))
            if not stats['best_opportunity'] or best.get('profit_pct', 0) > stats['best_opportunity'].get('profit_pct', 0):
                stats['best_opportunity'] = {
                    'title': best.get('pm_event', {}).get('title', '')[:60],
                    'profit_pct': best.get('profit_pct', 0),
                    'profit': best.get('profit', 0),
                    'timestamp': current_scan['timestamp']
                }
        
        # Write to file
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
            
    except Exception as e:
        print(f"Error writing stats: {e}")


def get_stats() -> Optional[Dict]:
    """Read current stats from file."""
    try:
        if STATS_FILE.exists():
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error reading stats: {e}")
    return None
