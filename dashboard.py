"""
Real-time dashboard for arbitrage scanner.
Run with: streamlit run dashboard.py
"""
import streamlit as st
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from stats_writer import STATS_FILE, get_stats

st.set_page_config(
    page_title="Arbitrage Scanner Dashboard",
    page_icon="📊",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .opportunity-card {
        background-color: #fff;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
        border: 1px solid #ddd;
    }
    .profit-positive {
        color: #00cc00;
        font-weight: bold;
    }
    .profit-negative {
        color: #cc0000;
    }
</style>
""", unsafe_allow_html=True)

def format_timestamp(iso_str: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except:
        return iso_str

def main():
    st.title("📊 Cross-Platform Arbitrage Scanner Dashboard")
    st.markdown("---")
    
    # Initialize session state for refresh control
    if 'refresh_timer' not in st.session_state:
        st.session_state.refresh_timer = time.time()
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 10  # Default 10 seconds
    
    # Auto-refresh control in sidebar
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=False)
    
    if auto_refresh:
        refresh_interval = st.sidebar.slider("Refresh interval (seconds)", min_value=10, max_value=120, value=10, step=5)
        st.session_state.refresh_interval = refresh_interval
        
        # Calculate time until next refresh
        elapsed = time.time() - st.session_state.refresh_timer
        remaining = max(0, refresh_interval - elapsed)
        st.sidebar.caption(f"⏱️ Next refresh in {remaining:.0f}s")
        
        # Only refresh if interval has passed (at the very end, after all content renders)
        # This way it doesn't interrupt user interaction
    else:
        st.sidebar.caption("Auto-refresh disabled")
        st.session_state.refresh_timer = time.time()  # Reset timer when disabled
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now"):
        st.session_state.refresh_timer = time.time()
        st.rerun()
    
    # Load stats
    stats = get_stats()
    
    if not stats:
        st.warning("⚠️ No scan data available yet. Start the scanner to see statistics.")
        st.info("Run: `python paper_trader.py` in another terminal")
        return
    
    last_scan = stats.get('last_scan')
    if not last_scan:
        st.warning("⚠️ No scan data available.")
        return
    
    # Header metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Scans", stats.get('total_scans', 0))
    
    with col2:
        st.metric("PM Events", last_scan.get('pm_events', 0))
    
    with col3:
        st.metric("Manifold Events", last_scan.get('manifold_events', 0))
    
    with col4:
        st.metric("Matched Pairs", last_scan.get('matched', 0))
    
    with col5:
        # Use opportunities_count if available, otherwise count the list
        opp_count = last_scan.get('opportunities_count')
        if opp_count is None:
            opp_list = last_scan.get('opportunities', [])
            opp_count = len(opp_list) if isinstance(opp_list, list) else 0
        st.metric("Opportunities", opp_count)
    
    st.markdown("---")
    
    # Last scan time
    last_scan_time = format_timestamp(last_scan.get('timestamp', ''))
    st.caption(f"Last scan: {last_scan_time}")
    
    # Main content in tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Current Opportunities", 
        "📊 Statistics", 
        "🔍 Recent Scans",
        "📋 Sample Events",
        "⚙️ Settings"
    ])
    
    with tab1:
        st.subheader("Current Arbitrage Opportunities")
        
        opportunities = last_scan.get('opportunities', [])
        if not isinstance(opportunities, list):
            opportunities = []
        if not opportunities:
            st.info("No opportunities found in the last scan.")
        else:
            for i, opp in enumerate(opportunities, 1):
                with st.expander(f"💰 {opp.get('title', 'Unknown')[:50]}", expanded=(i == 1)):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Polymarket Prices**")
                        st.write(f"YES: ${opp.get('pm_yes', 0):.4f}")
                        st.write(f"NO: ${opp.get('pm_no', 0):.4f}")
                    
                    with col2:
                        st.markdown("**Manifold Prices**")
                        st.write(f"YES: ${opp.get('manifold_yes', 0):.4f}")
                        st.write(f"NO: ${opp.get('manifold_no', 0):.4f}")
                    
                    direction = opp.get('direction', '')
                    if 'pm_yes' in direction:
                        direction_str = "Buy YES on Polymarket + NO on Manifold"
                    else:
                        direction_str = "Buy NO on Polymarket + YES on Manifold"
                    
                    st.markdown(f"**Direction:** {direction_str}")
                    
                    profit_pct = opp.get('profit_pct', 0)
                    profit = opp.get('profit', 0)
                    profit_class = "profit-positive" if profit > 0 else "profit-negative"
                    st.markdown(f"**Profit:** <span class='{profit_class}'>${profit:.4f} ({profit_pct:.2f}%)</span>", unsafe_allow_html=True)
    
    with tab2:
        st.subheader("Overall Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Opportunities", stats.get('total_opportunities', 0))
            st.metric("Total Alerts Sent", stats.get('total_alerts', 0))
        
        with col2:
            best = stats.get('best_opportunity')
            if best:
                st.metric("Best Opportunity", f"{best.get('profit_pct', 0):.2f}%")
                st.caption(f"Found: {format_timestamp(best.get('timestamp', ''))}")
                st.text(f"Title: {best.get('title', '')[:50]}")
            else:
                st.info("No opportunities found yet")
        
        with col3:
            # Calculate averages
            scan_history = stats.get('scan_history', [])
            if scan_history:
                avg_pm = sum(s.get('pm_events', 0) for s in scan_history) / len(scan_history)
                avg_mf = sum(s.get('manifold_events', 0) for s in scan_history) / len(scan_history)
                avg_matched = sum(s.get('matched', 0) for s in scan_history) / len(scan_history)
                
                st.metric("Avg PM Events", f"{avg_pm:.1f}")
                st.metric("Avg Manifold Events", f"{avg_mf:.1f}")
                st.metric("Avg Matched", f"{avg_matched:.1f}")
        
        # Chart of scan history
        if len(scan_history) > 1:
            st.subheader("Scan History Trends")
            
            import pandas as pd
            
            df = pd.DataFrame(scan_history)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Handle both 'opportunities' (list) and 'opportunities_count' (number) in history
            if 'opportunities_count' in df.columns:
                opp_col = 'opportunities_count'
            else:
                # Convert opportunities list to count if needed
                df['opportunities_count'] = df['opportunities'].apply(lambda x: len(x) if isinstance(x, list) else (x if isinstance(x, (int, float)) else 0))
                opp_col = 'opportunities_count'
            
            chart_data = df[['timestamp', 'pm_events', 'manifold_events', 'matched', opp_col]].set_index('timestamp')
            chart_data = chart_data.rename(columns={opp_col: 'opportunities'})
            st.line_chart(chart_data)
    
    with tab3:
        st.subheader("Recent Scan Results")
        
        scan_history = stats.get('scan_history', [])
        if not scan_history:
            st.info("No scan history available.")
        else:
            # Show last 10 scans
            for scan in reversed(scan_history[-10:]):
                with st.expander(f"Scan at {format_timestamp(scan.get('timestamp', ''))}"):
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("PM Events", scan.get('pm_events', 0))
                    col2.metric("Manifold Events", scan.get('manifold_events', 0))
                    col3.metric("Matched", scan.get('matched', 0))
                    opp_val = scan.get('opportunities_count') or scan.get('opportunities', 0)
                    if isinstance(opp_val, list):
                        opp_val = len(opp_val)
                    col4.metric("Opportunities", opp_val)
    
    with tab4:
        st.subheader("Sample Events from Last Scan")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Polymarket Events")
            pm_sample = last_scan.get('pm_sample', [])
            if pm_sample:
                for event in pm_sample:
                    st.write(f"**{event.get('title', 'Unknown')[:50]}**")
                    st.caption(f"Resolves: {format_timestamp(event.get('end_date', ''))}")
                    st.caption(f"Markets: {event.get('markets_count', 0)}")
            else:
                st.info("No sample events available")
        
        with col2:
            st.markdown("### Manifold Events")
            mf_sample = last_scan.get('manifold_sample', [])
            if mf_sample:
                for event in mf_sample:
                    st.write(f"**{event.get('title', 'Unknown')[:50]}**")
                    st.caption(f"Resolves: {format_timestamp(event.get('end_date', ''))}")
                    st.caption(f"Markets: {event.get('markets_count', 0)}")
            else:
                st.info("No sample events available")
        
        # Matched pairs
        matched_details = last_scan.get('matched_details', [])
        if matched_details:
            st.markdown("### Matched Event Pairs")
            for pair in matched_details[:5]:
                st.write(f"**PM:** {pair.get('pm_title', '')[:40]}")
                st.write(f"**MF:** {pair.get('manifold_title', '')[:40]}")
                st.markdown("---")
    
    with tab5:
        st.subheader("Scanner Configuration")
        st.info("Configuration is read from paper_trader.py")
        st.code("""
MIN_PROFIT_AFTER_FEES_PCT = 0.5%
TITLE_SIMILARITY_THRESHOLD = 0.5
DATE_MATCH_TOLERANCE_DAYS = 3
SCAN_INTERVAL = 60 seconds
        """)
        
        st.markdown("### Dashboard Settings")
        st.caption(f"Stats file: {STATS_FILE}")
        st.caption(f"Auto-refresh: {'Enabled' if auto_refresh else 'Disabled'}")
        if auto_refresh:
            st.caption(f"Refresh interval: {st.session_state.refresh_interval} seconds")
    
    # Auto-refresh logic at the END (after all content is rendered)
    # This prevents interrupting user interaction
    if auto_refresh:
        elapsed = time.time() - st.session_state.refresh_timer
        if elapsed >= st.session_state.refresh_interval:
            st.session_state.refresh_timer = time.time()
            # Use a placeholder to show refresh is happening without blocking
            refresh_placeholder = st.empty()
            refresh_placeholder.info("🔄 Refreshing...")
            time.sleep(0.1)  # Brief pause to show refresh message
            st.rerun()

if __name__ == "__main__":
    main()
