#!/usr/bin/env python3
"""
Basic Pendle Market Analyzer
Core analysis functionality for decline rate calculations
"""

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from pendle_market_analysis.models import Market, Transaction, DeclineRateAnalysis


class PendleAnalyzer:
    """Basic analyzer for Pendle market decline rate analysis"""
    
    def __init__(self, api_client):
        self.api_client = api_client
    
    def calculate_current_yt_price_fast(self, transactions: List[Transaction]) -> float:
        """Calculate current YT price from recent transactions"""
        if not transactions:
            return 0.0
        
        # Sort by timestamp and get most recent transactions
        sorted_txs = sorted(transactions, key=lambda x: x.timestamp, reverse=True)
        recent_txs = sorted_txs[:10]  # Last 10 transactions
        
        # Calculate average implied APY from recent transactions
        valid_apy_values = [tx.implied_apy for tx in recent_txs if tx.implied_apy is not None]
        
        if not valid_apy_values:
            return 0.0
        
        return sum(valid_apy_values) / len(valid_apy_values)
    
    def calculate_volume_fast(self, transactions: List[Transaction]) -> float:
        """Calculate total volume in USD"""
        total_volume = 0.0
        
        for tx in transactions:
            if tx.valuation_usd is not None:
                total_volume += tx.valuation_usd
        
        return total_volume
    
    def calculate_average_implied_apy_fast(self, transactions: List[Transaction]) -> float:
        """Calculate average implied APY"""
        apy_values = [tx.implied_apy for tx in transactions if tx.implied_apy is not None]
        
        if not apy_values:
            return 0.0
        
        return sum(apy_values) / len(apy_values)
    
    def calculate_decline_rates_fast(self, transactions: List[Transaction]) -> Tuple[float, float]:
        """Fast decline rate calculation"""
        if len(transactions) < 2:
            return 0.0, 0.0
        
        # Sort by timestamp
        sorted_txs = sorted(transactions, key=lambda x: x.timestamp)
        
        # Group by date and calculate daily implied APY
        daily_data = defaultdict(list)
        
        for tx in sorted_txs:
            try:
                tx_date = datetime.fromisoformat(tx.timestamp.replace('Z', '+00:00')).date()
                if tx.implied_apy is not None:
                    daily_data[tx_date].append(tx.implied_apy)
            except:
                continue
        
        if len(daily_data) < 2:
            return 0.0, 0.0
        
        # Calculate daily rates of change
        dates = sorted(daily_data.keys())
        daily_rates = []
        
        for i in range(1, len(dates)):
            prev_avg = sum(daily_data[dates[i-1]]) / len(daily_data[dates[i-1]])
            curr_avg = sum(daily_data[dates[i]]) / len(daily_data[dates[i]])
            
            if prev_avg > 0:
                rate_change = (curr_avg - prev_avg) / prev_avg * 100
                daily_rates.append(rate_change)
        
        if not daily_rates:
            return 0.0, 0.0
        
        avg_decline = sum(daily_rates) / len(daily_rates)
        latest_decline = daily_rates[-1] if daily_rates else 0.0
        
        return avg_decline, latest_decline