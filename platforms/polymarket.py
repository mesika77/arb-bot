import os
import json
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from .base import PlatformClient


class PolymarketClient(PlatformClient):
    """Client for Polymarket prediction markets."""
    
    def __init__(self, private_key: str, api_key: str, api_secret: str, api_passphrase: str):
        """
        Initialize Polymarket client.
        
        Args:
            private_key: Polymarket private key
            api_key: CLOB API key
            api_secret: CLOB API secret
            api_passphrase: CLOB API passphrase
        """
        creds = ApiCreds(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase
        )
        self.client = ClobClient(
            host="https://clob.polymarket.com",
            key=private_key,
            chain_id=137,
            creds=creds
        )
        self.order_size_usd = 1.0
    
    def _parse_clob_token_ids(self, raw):
        """Parse clobTokenIds from Gamma API (can be JSON string or list)."""
        if raw is None:
            return None
        if isinstance(raw, list):
            return raw if len(raw) >= 2 else None
        if isinstance(raw, str):
            try:
                out = json.loads(raw)
                return out if isinstance(out, list) and len(out) >= 2 else None
            except (json.JSONDecodeError, TypeError):
                return None
        return None
    
    def _get_best_ask(self, token_id: str) -> Optional[float]:
        """Best ask price only; returns None if no book or no asks."""
        try:
            book = self.client.get_order_book(token_id)
            if not (hasattr(book, "asks") and book.asks):
                return None
            return float(book.asks[0].price)
        except Exception:
            return None
    
    async def _get_impact_price(self, token_id: str, amount_usd: float) -> Optional[float]:
        """Weighted average price for amount_usd; falls back to best ask if book too thin."""
        try:
            book = self.client.get_order_book(token_id)
            if not (hasattr(book, "asks") and book.asks):
                return None

            filled_usd, shares = 0, 0
            for ask in book.asks:
                p, s = float(ask.price), float(ask.size)
                avail = p * s
                if filled_usd + avail >= amount_usd:
                    rem = amount_usd - filled_usd
                    shares += rem / p
                    filled_usd = amount_usd
                    break
                shares += s
                filled_usd += avail

            if filled_usd >= amount_usd:
                return amount_usd / shares
            # Book too thin: return best ask as fallback
            return float(book.asks[0].price)
        except Exception:
            return None
    
    async def get_events(self, limit: int = 50, max_resolution_days: int = 3) -> List[Dict]:
        """Fetch active events from Polymarket."""
        cutoff_time = datetime.now(timezone.utc) + timedelta(days=max_resolution_days)
        
        response = requests.get(f"https://gamma-api.polymarket.com/events?closed=false&limit={limit}")
        events = response.json()
        
        normalized_events = []
        
        for event in events:
            end_str = event.get("endDate")
            if not end_str:
                continue
            
            try:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            
            if end_dt > cutoff_time:
                continue
            
            markets = event.get("markets", [])
            if not markets:
                continue
            
            # Filter tradeable markets
            tradeable = [
                m for m in markets
                if m.get("enableOrderBook") is True
                and m.get("closed") is not True
                and m.get("acceptingOrders") is not False
            ]
            
            if not tradeable:
                continue
            
            # Get prices for each market
            normalized_markets = []
            for m in tradeable:
                t_ids = self._parse_clob_token_ids(m.get("clobTokenIds"))
                if not t_ids:
                    continue
                
                yes_token, no_token = t_ids[0], t_ids[1]
                
                # Get prices
                yes_price = await self._get_impact_price(yes_token, self.order_size_usd)
                if yes_price is None:
                    yes_price = self._get_best_ask(yes_token)
                
                no_price = await self._get_impact_price(no_token, self.order_size_usd)
                if no_price is None:
                    no_price = self._get_best_ask(no_token)
                    if no_price is None and yes_price is not None:
                        # Infer NO price from YES price
                        no_price = 1.0 - yes_price
                
                if yes_price is None:
                    continue
                
                normalized_markets.append({
                    'id': m.get('id') or m.get('slug', ''),
                    'question': m.get('question', ''),
                    'yes_price': yes_price,
                    'no_price': no_price
                })
            
            if not normalized_markets:
                continue
            
            normalized_events.append({
                'id': event.get('id') or event.get('slug', ''),
                'title': event.get('title', ''),
                'end_date': end_dt,
                'markets': normalized_markets,
                'platform': 'polymarket',
                'raw_data': event
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
        """Polymarket fee rate is 0.2%."""
        return 0.002
    
    def get_platform_name(self) -> str:
        return "polymarket"
