import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from .base import PlatformClient


class ManifoldPlatformClient(PlatformClient):
    """Client for Manifold Markets prediction markets."""
    
    BASE_URL = "https://api.manifold.markets/v0"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Manifold client.
        
        Args:
            api_key: Optional Manifold API key for authenticated requests
                     (not required for reading market data)
        """
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({
                'Authorization': f'Key {api_key}'
            })
    
    async def get_events(self, limit: int = 50, max_resolution_days: int = 3) -> List[Dict]:
        """Fetch active events from Manifold."""
        cutoff_time = datetime.now(timezone.utc) + timedelta(days=max_resolution_days)
        cutoff_ts_ms = int(cutoff_time.timestamp() * 1000)
        
        try:
            # Get open binary markets using search-markets endpoint
            # /v0/markets doesn't support filter/contractType, but /v0/search-markets does
            response = self.session.get(
                f"{self.BASE_URL}/search-markets",
                params={
                    'limit': min(limit, 1000),  # API max is 1000
                    'sort': 'close-date',
                    'filter': 'open',
                    'contractType': 'BINARY',
                    'term': ''  # Empty term to get all markets
                },
                timeout=30
            )
            response.raise_for_status()
            markets = response.json()
        except Exception as e:
            print(f"Manifold API error: {e}")
            return []
        
        # Group markets by close date (events)
        # For Manifold, each market is essentially its own event
        normalized_events = []
        
        for market in markets:
            # Skip markets closing too far in the future
            close_time = market.get('closeTime')
            if not close_time:
                continue
            
            try:
                close_dt = datetime.fromtimestamp(close_time / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                continue
            
            if close_dt > cutoff_time:
                continue
            
            # Skip resolved markets
            if market.get('isResolved', False):
                continue
            
            # Get probability (price)
            probability = market.get('probability', 0.5)
            yes_price = probability
            no_price = 1.0 - probability
            
            # Manifold uses CPMM (Constant Product Market Maker) or DPM
            # The probability represents the current market price
            # For buying YES, you'd pay around the probability
            # For buying NO, you'd pay around (1 - probability)
            # But actual execution prices depend on liquidity and slippage
            
            normalized_events.append({
                'id': market['id'],
                'title': market.get('question', ''),
                'end_date': close_dt,
                'markets': [{
                    'id': market['id'],
                    'question': market.get('question', ''),
                    'yes_price': yes_price,
                    'no_price': no_price
                }],
                'platform': 'manifold',
                'raw_data': market
            })
        
        return normalized_events
    
    async def get_market_prices(self, event_id: str, market_id: str) -> Optional[Tuple[float, float]]:
        """
        Get YES and NO prices for a specific market.
        
        Note: For Manifold, event_id and market_id are the same.
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/market/{market_id}",
                timeout=30
            )
            response.raise_for_status()
            market = response.json()
            
            if market.get('isResolved', False):
                return None
            
            probability = market.get('probability', 0.5)
            yes_price = probability
            no_price = 1.0 - probability
            
            return (yes_price, no_price)
        except Exception as e:
            print(f"Manifold API error getting market {market_id}: {e}")
            return None
    
    def get_fee_rate(self) -> float:
        """
        Manifold fee rate.
        
        Note: Manifold doesn't charge trading fees, but there may be creator fees
        and platform fees on resolution. For arbitrage purposes, we'll use 0% trading fee.
        However, there's slippage in CPMM markets, so actual execution may differ.
        """
        return 0.0
    
    def get_platform_name(self) -> str:
        return "manifold"
