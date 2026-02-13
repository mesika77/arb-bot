from typing import List, Dict, Tuple
from platforms.base import PlatformClient


def find_arbitrage_opportunities(
    matched_events: List[Tuple[Dict, Dict]],
    polymarket_client: PlatformClient,
    kalshi_client: PlatformClient,
    min_profit_pct: float = 0.5,
    order_size_usd: float = 1.0
) -> List[Dict]:
    """
    Find arbitrage opportunities from matched events between Polymarket and another platform.
    
    Args:
        matched_events: List of matched event pairs [(pm_event, other_platform_event), ...]
        polymarket_client: Polymarket platform client
        kalshi_client: Other platform client (e.g., Manifold) - generic parameter name
        min_profit_pct: Minimum profit percentage after fees to consider
        order_size_usd: Order size in USD for calculations
        
    Returns:
        List of arbitrage opportunities with structure:
        {
            'pm_event': dict,
            'kalshi_event': dict,  # Actually contains other platform event
            'pm_market': dict,
            'kalshi_market': dict,  # Actually contains other platform market
            'direction': str,  # 'pm_yes_kalshi_no' or 'pm_no_kalshi_yes'
            'pm_price': float,
            'kalshi_price': float,  # Actually other platform price
            'total_cost': float,
            'total_cost_with_fees': float,
            'payout': float,
            'profit': float,
            'profit_pct': float
        }
    """
    opportunities = []
    
    pm_fee_rate = polymarket_client.get_fee_rate()
    kalshi_fee_rate = kalshi_client.get_fee_rate()
    
    for pm_event, kalshi_event in matched_events:
        # Compare markets between platforms
        # For simplicity, compare first market from each event
        # In production, you might want to match markets more intelligently
        if not pm_event['markets'] or not kalshi_event['markets']:
            continue
        
        pm_market = pm_event['markets'][0]
        kalshi_market = kalshi_event['markets'][0]
        
        pm_yes = pm_market['yes_price']
        pm_no = pm_market['no_price']
        kalshi_yes = kalshi_market['yes_price']
        kalshi_no = kalshi_market['no_price']
        
        if None in [pm_yes, pm_no, kalshi_yes, kalshi_no]:
            continue
        
        # Scenario 1: Buy YES on Polymarket + NO on other platform
        # Cost = pm_yes + other_no, Payout = 1.0
        cost_scenario1 = pm_yes + kalshi_no
        cost_with_fees_scenario1 = (
            pm_yes * (1 + pm_fee_rate) + 
            kalshi_no * (1 + kalshi_fee_rate)
        )
        profit_scenario1 = 1.0 - cost_with_fees_scenario1
        profit_pct_scenario1 = (profit_scenario1 / cost_with_fees_scenario1 * 100) if cost_with_fees_scenario1 > 0 else 0
        
        if profit_pct_scenario1 >= min_profit_pct:
            opportunities.append({
                'pm_event': pm_event,
                'kalshi_event': kalshi_event,
                'pm_market': pm_market,
                'kalshi_market': kalshi_market,
                'direction': 'pm_yes_kalshi_no',
                'pm_price': pm_yes,
                'kalshi_price': kalshi_no,
                'total_cost': cost_scenario1,
                'total_cost_with_fees': cost_with_fees_scenario1,
                'payout': 1.0,
                'profit': profit_scenario1,
                'profit_pct': profit_pct_scenario1
            })
        
        # Scenario 2: Buy NO on Polymarket + YES on other platform
        # Cost = pm_no + other_yes, Payout = 1.0
        cost_scenario2 = pm_no + kalshi_yes
        cost_with_fees_scenario2 = (
            pm_no * (1 + pm_fee_rate) + 
            kalshi_yes * (1 + kalshi_fee_rate)
        )
        profit_scenario2 = 1.0 - cost_with_fees_scenario2
        profit_pct_scenario2 = (profit_scenario2 / cost_with_fees_scenario2 * 100) if cost_with_fees_scenario2 > 0 else 0
        
        if profit_pct_scenario2 >= min_profit_pct:
            opportunities.append({
                'pm_event': pm_event,
                'kalshi_event': kalshi_event,
                'pm_market': pm_market,
                'kalshi_market': kalshi_market,
                'direction': 'pm_no_kalshi_yes',
                'pm_price': pm_no,
                'kalshi_price': kalshi_yes,
                'total_cost': cost_scenario2,
                'total_cost_with_fees': cost_with_fees_scenario2,
                'payout': 1.0,
                'profit': profit_scenario2,
                'profit_pct': profit_pct_scenario2
            })
    
    return opportunities
