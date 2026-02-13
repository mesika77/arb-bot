import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from kalshi_python import Configuration
from .base import PlatformClient


class KalshiPlatformClient(PlatformClient):
    """Client for Kalshi prediction markets."""
    
    def __init__(self, api_key_id: str, private_key_pem: str):
        """
        Initialize Kalshi client.
        
        Args:
            api_key_id: Kalshi API key ID
            private_key_pem: Kalshi private key (PEM format string or path to PEM file)
        """
        config = Configuration(host="https://api.elections.kalshi.com/trade-api/v2")
        config.api_key_id = api_key_id
        
        # Handle both file path and inline PEM
        if os.path.isfile(private_key_pem):
            with open(private_key_pem, "r") as f:
                config.private_key_pem = f.read()
        else:
            config.private_key_pem = private_key_pem
        
        from kalshi_python import KalshiClient as KalshiSDKClient
        self.client = KalshiSDKClient(config)
    
    def _cents_to_decimal(self, cents: int) -> float:
        """Convert Kalshi price from cents to decimal (e.g., 50 cents -> 0.50)."""
        return cents / 100.0
    
    async def get_events(self, limit: int = 50, max_resolution_days: int = 3) -> List[Dict]:
        """Fetch active events from Kalshi."""
        cutoff_time = datetime.now(timezone.utc) + timedelta(days=max_resolution_days)
        
        try:
            # Get events with nested markets
            response = self.client.get_events(
                limit=limit,
                with_nested_markets=True,
                status="open"
            )
        except Exception as e:
            print(f"Kalshi API error: {e}")
            return []
        
        normalized_events = []
        
        for event in response.events:
            # Parse end date
            end_ts = event.close_ts
            if not end_ts:
                continue
            
            try:
                end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)
            except (ValueError, TypeError):
                continue
            
            if end_dt > cutoff_time:
                continue
            
            # Get markets for this event
            markets = event.markets if hasattr(event, 'markets') and event.markets else []
            
            if not markets:
                # Try fetching markets separately if not nested
                try:
                    markets_response = self.client.get_markets(
                        event_ticker=event.event_ticker,
                        status="open",
                        limit=100
                    )
                    markets = markets_response.markets if hasattr(markets_response, 'markets') else []
                except Exception:
                    continue
            
            if not markets:
                continue
            
            # Normalize markets
            normalized_markets = []
            for market in markets:
                # Kalshi prices are in cents, convert to decimal
                yes_bid = market.yes_bid if hasattr(market, 'yes_bid') else None
                yes_ask = market.yes_ask if hasattr(market, 'yes_ask') else None
                no_bid = market.no_bid if hasattr(market, 'no_bid') else None
                no_ask = market.no_ask if hasattr(market, 'no_ask') else None
                
                # Use ask price (price to buy)
                yes_price = self._cents_to_decimal(yes_ask) if yes_ask is not None else None
                no_price = self._cents_to_decimal(no_ask) if no_ask is not None else None
                
                # If ask not available, infer from bid or use midpoint
                if yes_price is None and yes_bid is not None:
                    yes_price = self._cents_to_decimal(yes_bid)
                if no_price is None and no_bid is not None:
                    no_price = self._cents_to_decimal(no_bid)
                
                # If still missing, infer from other side
                if yes_price is None and no_price is not None:
                    yes_price = 1.0 - no_price
                if no_price is None and yes_price is not None:
                    no_price = 1.0 - yes_price
                
                if yes_price is None or no_price is None:
                    continue
                
                normalized_markets.append({
                    'id': market.ticker if hasattr(market, 'ticker') else '',
                    'question': market.title if hasattr(market, 'title') else '',
                    'yes_price': yes_price,
                    'no_price': no_price
                })
            
            if not normalized_markets:
                continue
            
            normalized_events.append({
                'id': event.event_ticker if hasattr(event, 'event_ticker') else '',
                'title': event.title if hasattr(event, 'title') else '',
                'end_date': end_dt,
                'markets': normalized_markets,
                'platform': 'kalshi',
                'raw_data': event.__dict__ if hasattr(event, '__dict__') else {}
            })
        
        return normalized_events
    
    async def get_market_prices(self, event_id: str, market_id: str) -> Optional[Tuple[float, float]]:
        """
        Get YES and NO prices for a specific market.
        
        Note: This requires fetching the event first to find the market.
        For efficiency, prefer using get_events() which includes prices.
        """
        events = await self.get_events(limit=200)
        for event in events:
            if event['id'] == event_id:
                for market in event['markets']:
                    if market['id'] == market_id:
                        if market['yes_price'] is not None and market['no_price'] is not None:
                            return (market['yes_price'], market['no_price'])
        return None
    
    def get_fee_rate(self) -> float:
        """Kalshi fee rate is 10% (0.10)."""
        return 0.10
    
    def get_platform_name(self) -> str:
        return "kalshi"
