#!/usr/bin/env python3
"""
Data models and exceptions for Pendle Market Analysis
"""

from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class Market:
    """Market data structure matching the TypeScript interface"""
    name: str
    address: str
    expiry: str
    pt: str
    yt: str
    sy: str
    underlying_asset: str


@dataclass
class Transaction:
    """Transaction data structure for decline rate analysis"""
    id: str
    timestamp: str
    implied_apy: Optional[float] = None
    valuation_usd: Optional[float] = None
    market: str = ""
    action: str = ""
    value: Optional[float] = None


@dataclass
class DeclineRateAnalysis:
    """Focused analysis results for decline rate monitoring"""
    market: Market
    current_yt_price: float
    average_decline_rate: float
    latest_daily_decline_rate: float
    decline_rate_exceeds_average: bool
    volume_usd: float
    implied_apy: float
    transaction_count: int
    data_freshness_hours: float


class PendleApiError(Exception):
    """Pendle-specific API error"""
    
    def __init__(self, message: str, status: Optional[int] = None,
                 code: Optional[str] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details
        self.name = 'PendleApiError'


class AnalysisError(Exception):
    """Analysis-specific error"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.details = details
        self.name = 'AnalysisError'


class NotificationError(Exception):
    """Notification-specific error"""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.details = details
        self.name = 'NotificationError'