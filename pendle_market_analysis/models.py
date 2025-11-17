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
    """Enhanced Pendle-specific API error with detailed error reporting"""
    
    def __init__(self, message: str, status: Optional[int] = None,
                 code: Optional[str] = None, details: Optional[Any] = None,
                 endpoint: Optional[str] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details
        self.endpoint = endpoint
        self.response_body = response_body
        self.name = 'PendleApiError'
        
    def to_dict(self) -> dict:
        """Convert error to dictionary for logging and monitoring"""
        return {
            'error_type': self.name,
            'message': str(self),
            'status': self.status,
            'code': self.code,
            'endpoint': self.endpoint,
            'details': self.details,
            'response_body': self.response_body
        }
    
    @classmethod
    def from_response(cls, response, endpoint: Optional[str] = None) -> 'PendleApiError':
        """Create error from aiohttp response"""
        try:
            response_data = response.json() if response.content_type == 'application/json' else None
            if response_data and isinstance(response_data, dict):
                error_message = response_data.get('message') or response_data.get('error') or str(response.reason)
                error_code = response_data.get('code') or response_data.get('errorCode')
                details = response_data.get('details') or response_data
            else:
                error_message = f"HTTP {response.status}: {response.reason}"
                error_code = None
                details = None
        except Exception:
            error_message = f"HTTP {response.status}: {response.reason}"
            error_code = None
            details = None
            
        return cls(
            message=error_message,
            status=response.status,
            code=error_code,
            details=details,
            endpoint=endpoint
        )


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