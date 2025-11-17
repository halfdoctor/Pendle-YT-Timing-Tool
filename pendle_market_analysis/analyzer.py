#!/usr/bin/env python3
"""
Core analysis logic for Pendle Market Analysis
Handles all calculation and metric computation logic
"""

from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from pendle_market_analysis.models import Transaction, DeclineRateAnalysis, Market, AnalysisError


class PendleAnalyzer:
    """Handles all analysis logic for Pendle market data"""
    
    # Analysis thresholds
    ALERT_DECLINE_RATE_THRESHOLD = 1.5
    MIN_DECLINE_RATE_THRESHOLD = 5.0
    MIN_TRANSACTIONS_FOR_ANALYSIS = 5
    
    def __init__(self):
        self.MIN_TRANSACTIONS_FOR_ANALYSIS = 5
    
    def calculate_decline_rates_fast(self, transactions: List[Transaction]) -> Tuple[float, float, float]:
        """Decline rate calculation matching original script accuracy"""
        if len(transactions) < self.MIN_TRANSACTIONS_FOR_ANALYSIS:
            return 0.0, 0.0, 0.0
        
        # Use timezone-aware datetime.now()
        now_utc = datetime.now(timezone.utc)
        
        # Filter transactions with implied APY and sort by timestamp (matching original script)
        apy_transactions = [
            tx for tx in transactions
            if tx.implied_apy is not None and tx.implied_apy is not None and tx.timestamp
        ]
        apy_transactions.sort(key=lambda x: datetime.fromisoformat(x.timestamp.replace('Z', '+00:00')))
        
        if len(apy_transactions) < 2:
            return 0.0, 0.0, 0.0
        
        # Calculate average decline rate (matching original logic)
        average_decline_rate = 0.0
        first_tx = apy_transactions[0]
        last_tx = apy_transactions[-1]
        
        try:
            first_time = datetime.fromisoformat(first_tx.timestamp.replace('Z', '+00:00'))
            last_time = datetime.fromisoformat(last_tx.timestamp.replace('Z', '+00:00'))
            time_span_days = (last_time - first_time).days
            
            if time_span_days > 0:
                # Calculate rate of change in implied APY (which correlates with YT price)
                first_apy = first_tx.implied_apy or 0.0
                last_apy = last_tx.implied_apy or 0.0
                apy_change = last_apy - first_apy
                average_decline_rate = (apy_change / time_span_days) * 100  # Percentage change per day
            else:
                average_decline_rate = 0.0
        except Exception as e:
            raise AnalysisError(f"Failed to calculate average decline rate: {e}")
        
        # Fallback calculation if we have very few transactions (matching original script)
        if average_decline_rate == 0 and len(transactions) > 0:
            recent_txs = transactions[-5:]  # Last 5 transactions
            recent_apy = [tx.implied_apy for tx in recent_txs if tx.implied_apy is not None]
            if len(recent_apy) >= 2:
                apy_diff = recent_apy[-1] - recent_apy[0]
                average_decline_rate = apy_diff * 100  # Simple percentage change
        
        # Calculate latest daily decline rate (last 24 hours) - matching original script exactly
        latest_daily_decline_rate = 0.0
        one_day_ago = now_utc - timedelta(days=1)
        recent_transactions = [
            tx for tx in apy_transactions
            if datetime.fromisoformat(tx.timestamp.replace('Z', '+00:00')) >= one_day_ago
        ]
        recent_transactions.sort(key=lambda x: datetime.fromisoformat(x.timestamp.replace('Z', '+00:00')), reverse=True)
        
        if len(recent_transactions) >= 2:
            latest_apy = recent_transactions[0].implied_apy or 0.0
            previous_apy = recent_transactions[-1].implied_apy or 0.0
            
            try:
                latest_time = datetime.fromisoformat(recent_transactions[0].timestamp.replace('Z', '+00:00'))
                previous_time = datetime.fromisoformat(recent_transactions[-1].timestamp.replace('Z', '+00:00'))
                time_diff_hours = (latest_time - previous_time).total_seconds() / 3600
                
                if time_diff_hours > 0:
                    latest_daily_decline_rate = ((latest_apy - previous_apy) / time_diff_hours) * 24  # Extrapolate to daily rate
            except Exception as e:
                raise AnalysisError(f"Failed to calculate latest daily decline rate: {e}")
        
        # Calculate data freshness
        data_freshness_hours = 0.0
        if apy_transactions:
            latest_tx_time = datetime.fromisoformat(apy_transactions[-1].timestamp.replace('Z', '+00:00'))
            data_freshness_hours = (now_utc - latest_tx_time).total_seconds() / 3600
        
        return average_decline_rate, latest_daily_decline_rate, data_freshness_hours
    
    def calculate_current_yt_price_fast(self, transactions: List[Transaction]) -> float:
        """Optimized YT price calculation"""
        if not transactions:
            return 0.0
        
        # Sort by timestamp once
        transactions_sorted = sorted(
            [tx for tx in transactions if tx.value is not None and tx.value > 0],
            key=lambda x: datetime.fromisoformat(x.timestamp.replace('Z', '+00:00')),
            reverse=True
        )
        
        # Return most recent valid price
        if transactions_sorted:
            return transactions_sorted[0].value or 0.0
        
        return 0.0
    
    def calculate_volume_fast(self, transactions: List[Transaction]) -> float:
        """Optimized volume calculation"""
        return sum(
            (tx.valuation_usd or 0) for tx in transactions
        )
    
    def calculate_average_implied_apy_fast(self, transactions: List[Transaction]) -> float:
        """Optimized APY calculation"""
        apy_values = [tx.implied_apy for tx in transactions if tx.implied_apy is not None]
        return sum(apy_values) / len(apy_values) if apy_values else 0.0
    
    def analyze_market(self, market: Market, transactions: List[Transaction]) -> DeclineRateAnalysis:
        """Analyze a single market and return decline rate analysis"""
        
        if len(transactions) < self.MIN_TRANSACTIONS_FOR_ANALYSIS:
            print(f"    ⚠️ Insufficient data: {len(transactions)} transactions")
            return DeclineRateAnalysis(
                market=market, current_yt_price=0.0, average_decline_rate=0.0,
                latest_daily_decline_rate=0.0, decline_rate_exceeds_average=False,
                volume_usd=0.0, implied_apy=0.0, transaction_count=len(transactions),
                data_freshness_hours=0.0
            )
        
        try:
            # Calculate all metrics in one pass where possible
            current_yt_price = self.calculate_current_yt_price_fast(transactions)
            average_decline_rate, latest_daily_decline_rate, data_freshness_hours = self.calculate_decline_rates_fast(transactions)
            volume_usd = self.calculate_volume_fast(transactions)
            implied_apy = self.calculate_average_implied_apy_fast(transactions)
            
            # Check alert condition - focus on ACCELERATION of decay:
            # 1. Latest daily decline rate is more negative than average (acceleration)
            # 2. Acceleration magnitude exceeds minimum threshold
            # Note: We use signed values to detect acceleration (worsening) vs just magnitude
            decline_rate_exceeds_average = (latest_daily_decline_rate < average_decline_rate * self.ALERT_DECLINE_RATE_THRESHOLD) and \
                                          (abs(latest_daily_decline_rate) > self.MIN_DECLINE_RATE_THRESHOLD)
            
            print(f"    ✅ Decay: {abs(latest_daily_decline_rate):.2f}%/day (avg: {abs(average_decline_rate):.2f}%)")
            if decline_rate_exceeds_average:
                acceleration = abs(latest_daily_decline_rate) - abs(average_decline_rate)
                print(f"    🚨 ACCELERATION ALERT: {market.name} - {abs(latest_daily_decline_rate):.2f}% vs avg {abs(average_decline_rate):.2f}% (+{acceleration:.2f}%)")
            
            return DeclineRateAnalysis(
                market=market,
                current_yt_price=current_yt_price,
                average_decline_rate=average_decline_rate,
                latest_daily_decline_rate=latest_daily_decline_rate,
                decline_rate_exceeds_average=decline_rate_exceeds_average,
                volume_usd=volume_usd,
                implied_apy=implied_apy,
                transaction_count=len(transactions),
                data_freshness_hours=data_freshness_hours
            )
            
        except Exception as e:
            raise AnalysisError(f"Failed to analyze market {market.name}: {e}")