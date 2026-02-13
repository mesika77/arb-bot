from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class PlatformClient(ABC):
    """Abstract base class for prediction market platform clients."""
    
    @abstractmethod
    async def get_events(self, limit: int = 50, max_resolution_days: int = 3) -> List[Dict]:
        """
        Fetch active events from the platform.
        
        Returns:
            List of normalized event dictionaries with structure:
            {
                'id': str,
                'title': str,
                'end_date': datetime,
                'markets': [
                    {
                        'id': str,
                        'question': str,
                        'yes_price': float | None,
                        'no_price': float | None
                    }
                ],
                'platform': str,
                'raw_data': dict  # Original platform data
            }
        """
        pass
    
    @abstractmethod
    async def get_market_prices(self, event_id: str, market_id: str) -> Optional[Tuple[float, float]]:
        """
        Get YES and NO prices for a specific market.
        
        Args:
            event_id: Platform-specific event identifier
            market_id: Platform-specific market identifier
            
        Returns:
            Tuple of (yes_price, no_price) or None if unavailable
        """
        pass
    
    @abstractmethod
    def get_fee_rate(self) -> float:
        """
        Get the platform's fee rate (as decimal, e.g., 0.002 for 0.2%).
        
        Returns:
            Fee rate as a decimal
        """
        pass
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """Return the platform name."""
        pass
