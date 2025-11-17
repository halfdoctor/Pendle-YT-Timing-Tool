#!/usr/bin/env python3
"""
Enhanced Analyzer with Advanced Optimization Strategies
Integrates intelligent fallbacks and smart data collection
"""

import asyncio
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple

from pendle_market_analysis.models import Market, Transaction, DeclineRateAnalysis, PendleApiError
from pendle_market_analysis.analyzer import PendleAnalyzer
from pendle_market_analysis.advanced_optimizations import AdvancedMarketAnalyzer, MarketTier, OptimizationStrategy


@dataclass 
class AnalysisStrategy:
    """Defines analysis approach for different scenarios"""
    min_transactions: int = 5
    max_transactions: int = 2000
    days_back: int = 120
    sampling_rate: float = 1.0
    use_fallbacks: bool = True
    aggressive_optimization: bool = False


class EnhancedPendleAnalyzer:
    """
    Enhanced analyzer that handles insufficient data with intelligent strategies
    """
    
    # Analysis strategies for different market conditions
    ANALYSIS_STRATEGIES = {
        'conservative': AnalysisStrategy(
            min_transactions=10,
            max_transactions=1500,
            days_back=60,
            sampling_rate=0.8,
            use_fallbacks=True,
            aggressive_optimization=False
        ),
        'balanced': AnalysisStrategy(
            min_transactions=5,
            max_transactions=1000,
            days_back=30,
            sampling_rate=0.6,
            use_fallbacks=True,
            aggressive_optimization=True
        ),
        'aggressive': AnalysisStrategy(
            min_transactions=3,
            max_transactions=500,
            days_back=14,
            sampling_rate=0.4,
            use_fallbacks=True,
            aggressive_optimization=True
        )
    }
    
    def __init__(self, api_client):
        # Initialize without calling super().__init__ to avoid parameter issues
        self.api_client = api_client
        self.advanced_analyzer = AdvancedMarketAnalyzer(api_client)
        self.analysis_stats = {
            'total_markets': 0,
            'successful_analyses': 0,
            'fallback_used': 0,
            'insufficient_data': 0,
            'rate_limited': 0
        }
        
    async def analyze_market_with_optimization(self, 
                                             session,
                                             market: Market, 
                                             index: int, 
                                             total: int,
                                             strategy_name: str = 'balanced') -> Optional[DeclineRateAnalysis]:
        """
        Enhanced market analysis with intelligent optimization
        """
        self.analysis_stats['total_markets'] += 1
        strategy = self.ANALYSIS_STRATEGIES[strategy_name]
        
        try:
            print(f"  📊 [{index}/{total}] Analyzing: {market.name}")
            
            # Use advanced optimization for transaction collection
            transactions = await self._get_transactions_with_strategies(
                session, market, strategy
            )
            
            if len(transactions) < strategy.min_transactions:
                # Try more aggressive strategies
                print(f"    ⚠️ Only {len(transactions)} transactions, trying aggressive strategy...")
                transactions = await self._get_transactions_with_strategies(
                    session, market, self.ANALYSIS_STRATEGIES['aggressive']
                )
                
                if len(transactions) < 3:
                    self.analysis_stats['insufficient_data'] += 1
                    print(f"    ❌ Insufficient data: {len(transactions)} transactions")
                    
                    # Try conservative fallback
                    if strategy.use_fallbacks:
                        transactions = await self._get_transactions_with_strategies(
                            session, market, self.ANALYSIS_STRATEGIES['conservative']
                        )
                        self.analysis_stats['fallback_used'] += 1
                        print(f"    🔄 Conservative fallback: {len(transactions)} transactions")
            
            if len(transactions) < strategy.min_transactions:
                # Return minimal analysis with warning
                return self._create_minimal_analysis(market, transactions)
            
            # Perform analysis with collected data
            analysis = self._perform_complete_analysis(market, transactions)
            self.analysis_stats['successful_analyses'] += 1
            
            return analysis
            
        except PendleApiError as e:
            if e.status == 429:
                self.analysis_stats['rate_limited'] += 1
                print(f"    🚫 Rate limited (429): {str(e)}")
            else:
                print(f"    ❌ API Error: {str(e)}")
            return None
        except Exception as e:
            print(f"    ❌ Analysis failed: {e}")
            return None
    
    def _perform_complete_analysis(self, market: Market, transactions: List[Transaction]) -> DeclineRateAnalysis:
        """Perform complete analysis on transaction data"""
        if not transactions:
            return self._create_minimal_analysis(market, transactions)
        
        # Calculate all metrics
        current_yt_price = self.calculate_current_yt_price_fast(transactions)
        volume_usd = self.calculate_volume_fast(transactions)
        implied_apy = self.calculate_average_implied_apy_fast(transactions)
        
        # Calculate decline rates
        avg_decline, latest_decline = self.calculate_decline_rates_fast(transactions)
        minimal_multiplier = 1.5
        minimal_notifiable_decline = 0.5
        exceeds_average = (latest_decline > avg_decline * minimal_multiplier) and (latest_decline > minimal_notifiable_decline) if avg_decline > 0 else False
        
        return DeclineRateAnalysis(
            market=market,
            current_yt_price=current_yt_price,
            average_decline_rate=avg_decline,
            latest_daily_decline_rate=latest_decline,
            decline_rate_exceeds_average=exceeds_average,
            volume_usd=volume_usd,
            implied_apy=implied_apy,
            transaction_count=len(transactions),
            data_freshness_hours=2.0
        )
    
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
    
    async def _get_transactions_with_strategies(self,
                                              session,
                                              market: Market, 
                                              strategy: AnalysisStrategy) -> List[Transaction]:
        """
        Get transactions using multiple collection strategies
        """
        try:
            # Try optimized collection through advanced analyzer
            transactions = await self.advanced_analyzer.get_transactions_with_optimization(
                market
            )
            
            # Apply intelligent sampling if needed
            if strategy.sampling_rate < 1.0 and len(transactions) > strategy.max_transactions:
                sample_size = int(len(transactions) * strategy.sampling_rate)
                transactions = random.sample(transactions, min(sample_size, len(transactions)))
                print(f"    🎯 Sampled {len(transactions)} transactions ({strategy.sampling_rate:.1%})")
            
            # Enforce transaction limits
            if len(transactions) > strategy.max_transactions:
                # Sort by timestamp and take most recent
                transactions.sort(key=lambda x: x.timestamp, reverse=True)
                transactions = transactions[:strategy.max_transactions]
                print(f"    ✂️ Limited to {len(transactions)} most recent transactions")
            
            return transactions
            
        except Exception as e:
            print(f"    ⚠️ Advanced collection failed: {e}")
            
            # Fallback to standard collection using API client directly
            try:
                transactions = await self.api_client.get_transactions(session, market.address)
                return transactions[:strategy.max_transactions]
            except Exception as fallback_error:
                print(f"    ❌ Fallback collection failed: {fallback_error}")
                return []
    
    def _create_minimal_analysis(self, market: Market, transactions: List[Transaction]) -> DeclineRateAnalysis:
        """
        Create minimal analysis when insufficient data is available
        """
        if not transactions:
            # Create analysis with zero values but mark as insufficient
            return DeclineRateAnalysis(
                market=market,
                current_yt_price=0.0,
                average_decline_rate=0.0,
                latest_daily_decline_rate=0.0,
                decline_rate_exceeds_average=False,
                volume_usd=0.0,
                implied_apy=0.0,
                transaction_count=0,
                data_freshness_hours=24.0
            )
        
        # Calculate basic metrics from limited data
        current_yt_price = self.calculate_current_yt_price_fast(transactions)
        volume_usd = self.calculate_volume_fast(transactions)
        implied_apy = self.calculate_average_implied_apy_fast(transactions)
        
        # Use simplified decline calculation with fewer data points
        decline_rates = self._calculate_simplified_decline_rates(transactions)
        
        if decline_rates:
            avg_decline = sum(decline_rates) / len(decline_rates)
            latest_decline = decline_rates[-1] if decline_rates else 0.0
            exceeds_avg = latest_decline > avg_decline * 1.1  # 10% threshold
        else:
            avg_decline = 0.0
            latest_decline = 0.0
            exceeds_avg = False
        
        return DeclineRateAnalysis(
            market=market,
            current_yt_price=current_yt_price,
            average_decline_rate=avg_decline,
            latest_daily_decline_rate=latest_decline,
            decline_rate_exceeds_average=exceeds_avg,
            volume_usd=volume_usd,
            implied_apy=implied_apy,
            transaction_count=len(transactions),
            data_freshness_hours=12.0  # Mark as potentially stale
        )
    
    def _calculate_simplified_decline_rates(self, transactions: List[Transaction]) -> List[float]:
        """
        Calculate decline rates with limited data points
        """
        if len(transactions) < 2:
            return []
        
        # Sort transactions by timestamp
        sorted_txs = sorted(transactions, key=lambda x: x.timestamp)
        
        decline_rates = []
        
        # Use sliding window approach for limited data
        window_size = max(2, len(sorted_txs) // 10)  # Use 10% of data for window
        
        for i in range(window_size, len(sorted_txs)):
            window_txs = sorted_txs[i-window_size:i+1]
            
            # Calculate simple rate of change
            if len(window_txs) >= 2:
                # Group by day and calculate daily rates
                daily_data = defaultdict(list)
                
                for tx in window_txs:
                    try:
                        tx_date = datetime.fromisoformat(tx.timestamp.replace('Z', '+00:00')).date()
                        if tx.implied_apy is not None:
                            daily_data[tx_date].append(tx.implied_apy)
                    except:
                        continue
                
                if len(daily_data) >= 2:
                    # Calculate daily change rate
                    dates = sorted(daily_data.keys())
                    daily_rates = []
                    
                    for j in range(1, len(dates)):
                        prev_rate = sum(daily_data[dates[j-1]]) / len(daily_data[dates[j-1]])
                        curr_rate = sum(daily_data[dates[j]]) / len(daily_data[dates[j]])
                        
                        if prev_rate > 0:
                            daily_change = (curr_rate - prev_rate) / prev_rate * 100
                            daily_rates.append(daily_change)
                    
                    if daily_rates:
                        decline_rates.append(sum(daily_rates) / len(daily_rates))
        
        return decline_rates[:5]  # Limit to 5 data points
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """
        Get comprehensive optimization and analysis report
        """
        stats = self.analysis_stats.copy()
        
        # Calculate success rates
        total = stats['total_markets']
        if total > 0:
            # Create separate rates dict to avoid type conflicts
            rates = {
                'success_rate': float(stats['successful_analyses'] / total),
                'fallback_rate': float(stats['fallback_used'] / total),
                'insufficient_data_rate': float(stats['insufficient_data'] / total),
                'rate_limit_rate': float(stats['rate_limited'] / total)
            }
        else:
            rates = {
                'success_rate': 0.0,
                'fallback_rate': 0.0,
                'insufficient_data_rate': 0.0,
                'rate_limit_rate': 0.0
            }
        
        # Add advanced optimization insights
        advanced_report = self.advanced_analyzer.get_optimization_report()
        
        return {
            'analysis_statistics': {**stats, **rates},  # Merge both dictionaries
            'optimization_effectiveness': {
                'markets_analyzed_with_optimization': advanced_report['total_markets_analyzed'],
                'tier_distribution': advanced_report['tier_distribution'],
                'success_rates_by_tier': advanced_report['success_rates_by_tier'],
                'problematic_markets': advanced_report['top_problematic_markets'][:5]
            },
            'recommendations': self._generate_optimization_recommendations({**stats, **rates}, advanced_report)
        }
    
    def _generate_optimization_recommendations(self, 
                                             stats: Dict[str, Any], 
                                             advanced_report: Dict[str, Any]) -> List[str]:
        """
        Generate actionable optimization recommendations
        """
        recommendations = []
        
        # Rate limiting recommendations
        if stats.get('rate_limit_rate', 0) > 0.1:
            recommendations.append(
                f"High rate limit rate ({stats['rate_limit_rate']:.1%}). Consider reducing concurrency or using more aggressive delays."
            )
        
        # Insufficient data recommendations
        if stats.get('insufficient_data_rate', 0) > 0.2:
            recommendations.append(
                f"High insufficient data rate ({stats['insufficient_data_rate']:.1%}). Consider adjusting transaction thresholds or using alternative data sources."
            )
        
        # Fallback usage recommendations
        if stats.get('fallback_rate', 0) > 0.3:
            recommendations.append(
                f"High fallback usage ({stats['fallback_rate']:.1%}). Primary strategies may need tuning for current market conditions."
            )
        
        # Tier-specific recommendations
        success_rates = advanced_report.get('success_rates_by_tier', {})
        if success_rates.get('low_volume', 0) < 0.6:
            recommendations.append(
                "Low success rate for low-volume markets. Consider using recent-only data sources or price-based estimations."
            )
        
        if not recommendations:
            recommendations.append("All optimization metrics look good! Current strategies are performing well.")
        
        return recommendations


class SmartBatchProcessor:
    """
    Intelligent batch processor that adapts based on success rates
    """
    
    def __init__(self, enhanced_analyzer: EnhancedPendleAnalyzer):
        self.analyzer = enhanced_analyzer
        self.batch_stats = {
            'batches_processed': 0,
            'markets_per_batch': 2,
            'adaptive_adjustments': 0
        }
    
    async def process_batch_with_adaptation(self, 
                                          session,
                                          markets: List[Market], 
                                          batch_index: int) -> List[DeclineRateAnalysis]:
        """
        Process batch with adaptive optimization based on previous performance
        """
        self.batch_stats['batches_processed'] += 1
        
        # Analyze previous batch performance to adapt current batch
        if batch_index > 0:
            await self._adapt_batch_parameters()
        
        results = []
        successful_count = 0
        
        for i, market in enumerate(markets):
            result = await self.analyzer.analyze_market_with_optimization(
                session, market, i + 1, len(markets)
            )
            
            if result:
                results.append(result)
                successful_count += 1
        
        # Adjust batch size based on success rate
        success_rate = successful_count / len(markets) if markets else 0
        if success_rate < 0.7 and self.batch_stats['markets_per_batch'] > 1:
            self.batch_stats['markets_per_batch'] = max(1, self.batch_stats['markets_per_batch'] - 1)
            self.batch_stats['adaptive_adjustments'] += 1
            print(f"    🔄 Reduced batch size to {self.batch_stats['markets_per_batch']} due to low success rate")
        elif success_rate > 0.9 and self.batch_stats['markets_per_batch'] < 5:
            self.batch_stats['markets_per_batch'] = min(5, self.batch_stats['markets_per_batch'] + 1)
            self.batch_stats['adaptive_adjustments'] += 1
            print(f"    🔄 Increased batch size to {self.batch_stats['markets_per_batch']} due to high success rate")
        
        return results
    
    async def _adapt_batch_parameters(self):
        """
        Adapt batch processing parameters based on overall performance
        """
        # This could implement more sophisticated adaptation logic
        # For now, just log the current state
        report = self.analyzer.get_optimization_report()
        overall_success_rate = report['analysis_statistics'].get('success_rate', 0)
        
        if overall_success_rate < 0.5:
            # Increase delays between batches
            print("    🐌 Low success rate detected, increasing inter-batch delays...")
            await asyncio.sleep(2.0)  # Increased delay
        elif overall_success_rate > 0.8:
            # Can be more aggressive
            print("    ⚡ High success rate, processing efficiently...")
            await asyncio.sleep(0.5)  # Reduced delay