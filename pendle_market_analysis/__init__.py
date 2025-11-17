"""
Pendle Market Analysis Package

A modular tool for analyzing Pendle markets with focus on decline rate analysis.
Features advanced optimization including caching, rate limiting, and batch processing.
"""

from .models import Market, Transaction, DeclineRateAnalysis, PendleApiError
from .analyzer import PendleAnalyzer
from .api_client import PendleAPIClient
from .notifier import Notifier
from .orchestrator import AnalysisOrchestrator

__version__ = "3.0.0"
__all__ = [
    "Market",
    "Transaction",
    "DeclineRateAnalysis",
    "PendleApiError",
    "PendleAnalyzer",
    "PendleAPIClient",
    "Notifier",
    "AnalysisOrchestrator",
]