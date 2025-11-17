#!/usr/bin/env python3
"""
Advanced Optimization Strategies for Pendle Market Analysis
Provides intelligent fallbacks, data diversification, and smart sampling
"""

import asyncio
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple, Union
from enum import Enum
import json

from pendle_market_analysis.models import Market, Transaction, PendleApiError


class MarketTier(Enum):
    """Market classification for optimization strategies"""
    HIGH_VOLUME = "high_volume"      # >1000 transactions typically
    MEDIUM_VOLUME = "medium_volume"  # 100-1000 transactions  
    LOW_VOLUME = "low_volume"        # <100 transactions
    UNKNOWN = "unknown"


class DataSource(Enum):
    """Alternative data sources when primary fails"""
    MAIN_TRANSACTIONS = "main_transactions"
    RECENT_ONLY = "recent_only"      # Last 7 days only
    SAMPLE_DATA = "sample_data"      # Random sampling
    PRICE_DATA = "price_data"        # Use price endpoints
    HISTORICAL_SNAPSHOT = "historical_snapshot"  # Use cached data


@dataclass
class OptimizationStrategy:
    """Configuration for different optimization approaches"""
    name: str
    max_transactions: int
    days_back: int
    sampling_rate: float
    fallback_enabled: bool
    retry_count: int
    priority: int


class AdvancedMarketAnalyzer:
    """
    Advanced analyzer with intelligent optimization strategies
    Handles insufficient data scenarios with multiple fallback mechanisms
    """
    
    # Market tier thresholds (transactions per analysis)
    VOLUME_THRESHOLDS = {
        MarketTier.HIGH_VOLUME: 1000,
        MarketTier.MEDIUM_VOLUME: 100,
        MarketTier.LOW_VOLUME: 10
    }
    
    # Optimization strategies for different market types
    OPTIMIZATION_STRATEGIES = {
        MarketTier.HIGH_VOLUME: OptimizationStrategy(
            name="high_volume_optimized",
            max_transactions=500,  # Reduced from 2000
            days_back=30,         # Reduced from 120
            sampling_rate=0.25,   # Sample 25% of transactions
            fallback_enabled=True,
            retry_count=3,        # Reduced from 6
            priority=1
        ),
        MarketTier.MEDIUM_VOLUME: OptimizationStrategy(
            name="medium_volume_balanced",
            max_transactions=800,
            days_back=60,
            sampling_rate=0.5,
            fallback_enabled=True,
            retry_count=4,
            priority=2
        ),
        MarketTier.LOW_VOLUME: OptimizationStrategy(
            name="low_volume_complete",
            max_transactions=2000,  # Allow full collection
            days_back=120,
            sampling_rate=1.0,     # No sampling
            fallback_enabled=True,
            retry_count=6,
            priority=3
        )
    }
    
    def __init__(self, api_client):
        self.api_client = api_client
        self.market_tier_cache: Dict[str, MarketTier] = {}
        self.failure_tracker: Dict[str, int] = defaultdict(int)
        self.success_tracker: Dict[str, int] = defaultdict(int)
        self.optimization_history: Dict[str, List[Dict]] = defaultdict(list)
        
    def classify_market_tier(self, market_address: str) -> MarketTier:
        """Classify market based on historical performance"""
        if market_address in self.market_tier_cache:
            return self.market_tier_cache[market_address]
            
        # Check historical success/failure patterns
        success_rate = self.success_tracker.get(market_address, 0)
        failure_rate = self.failure_tracker.get(market_address, 0)
        total_attempts = success_rate + failure_rate
        
        if total_attempts > 0:
            success_ratio = success_rate / total_attempts
            if success_ratio > 0.8:
                tier = MarketTier.HIGH_VOLUME  # Successful = likely high volume
            elif success_ratio > 0.5:
                tier = MarketTier.MEDIUM_VOLUME
            else:
                tier = MarketTier.LOW_VOLUME  # Failing = likely low volume/slow
        else:
            # Unknown market - start with medium volume strategy
            tier = MarketTier.MEDIUM_VOLUME
            
        self.market_tier_cache[market_address] = tier
        return tier
    
    async def get_transactions_with_optimization(self, 
                                               market: Market,
                                               base_strategy: Optional[OptimizationStrategy] = None) -> List[Transaction]:
        """
        Get transactions using intelligent optimization and fallbacks
        """
        market_address = market.address
        tier = self.classify_market_tier(market_address)
        
        # Use provided strategy or get tier-based strategy
        strategy = base_strategy or self.OPTIMIZATION_STRATEGIES[tier]
        
        print(f"    🎯 Using {tier.value} strategy: {strategy.name}")
        
        # Try main strategy first
        transactions = await self._try_transaction_collection(
            market, strategy, DataSource.MAIN_TRANSACTIONS
        )
        
        if len(transactions) >= self.VOLUME_THRESHOLDS[MarketTier.LOW_VOLUME]:
            self._record_success(market_address)
            return transactions
        
        # If insufficient data, try fallback strategies
        fallback_sources = self._get_fallback_sources(tier)
        
        for fallback_source in fallback_sources:
            print(f"    🔄 Trying fallback: {fallback_source.value}")
            
            fallback_strategy = self._adapt_strategy_for_source(strategy, fallback_source)
            transactions = await self._try_transaction_collection(
                market, fallback_strategy, fallback_source
            )
            
            if len(transactions) >= self.VOLUME_THRESHOLDS[MarketTier.LOW_VOLUME]:
                self._record_success(market_address)
                return transactions
        
        # If all strategies fail, record failure and return best effort
        self._record_failure(market_address)
        return transactions
    
    def _get_fallback_sources(self, tier: MarketTier) -> List[DataSource]:
        """Get appropriate fallback data sources for market tier"""
        if tier == MarketTier.HIGH_VOLUME:
            return [
                DataSource.RECENT_ONLY,
                DataSource.SAMPLE_DATA,
                DataSource.PRICE_DATA
            ]
        elif tier == MarketTier.MEDIUM_VOLUME:
            return [
                DataSource.RECENT_ONLY,
                DataSource.SAMPLE_DATA
            ]
        else:  # LOW_VOLUME
            return [
                DataSource.RECENT_ONLY
            ]
    
    def _adapt_strategy_for_source(self, 
                                  base_strategy: OptimizationStrategy, 
                                  source: DataSource) -> OptimizationStrategy:
        """Adapt strategy parameters based on data source"""
        adapted = OptimizationStrategy(
            name=f"{base_strategy.name}_{source.value}",
            max_transactions=base_strategy.max_transactions,
            days_back=base_strategy.days_back,
            sampling_rate=base_strategy.sampling_rate,
            fallback_enabled=False,  # Don't recurse on fallbacks
            retry_count=base_strategy.retry_count,
            priority=base_strategy.priority
        )
        
        # Adjust parameters based on data source
        if source == DataSource.RECENT_ONLY:
            adapted.days_back = min(7, base_strategy.days_back)
            adapted.max_transactions = int(base_strategy.max_transactions * 1.5)
        elif source == DataSource.SAMPLE_DATA:
            adapted.sampling_rate = max(0.1, base_strategy.sampling_rate * 0.5)
        elif source == DataSource.PRICE_DATA:
            # Price data is different - we'll handle this separately
            adapted.max_transactions = 100
            
        return adapted
    
    async def _try_transaction_collection(self, 
                                        market: Market,
                                        strategy: OptimizationStrategy,
                                        data_source: DataSource) -> List[Transaction]:
        """Attempt transaction collection with specific strategy"""
        try:
            if data_source == DataSource.PRICE_DATA:
                return await self._get_price_based_transactions(market, strategy)
            else:
                return await self._get_optimized_transactions(market, strategy, data_source)
        except Exception as e:
            print(f"    ⚠️ Strategy {strategy.name} failed: {e}")
            return []
    
    async def _get_optimized_transactions(self,
                                        market: Market,
                                        strategy: OptimizationStrategy,
                                        data_source: DataSource) -> List[Transaction]:
        """Get transactions using optimized parameters"""
        session = await self.api_client.get_session()
        
        # Set up optimized parameters
        params = {
            "market": market.address,
            "limit": str(strategy.max_transactions),
            "minValue": "0",
            "action": "SWAP_PT,SWAP_PY,SWAP_YT"  # Focus on relevant actions
        }
        
        # Adjust time range based on strategy
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=strategy.days_back)
        params["timestamp_start"] = cutoff_date.isoformat()
        
        # Use the API client's optimized method with modified parameters
        transactions = []
        skip = 0
        resume_token = None
        pages = 0
        seen_ids = set()
        
        max_pages = min(4, max(1, strategy.max_transactions // 250))  # Adaptive page count
        
        while pages < max_pages:
            page_params = params.copy()
            
            if resume_token:
                page_params["resumeToken"] = resume_token
            else:
                page_params["skip"] = str(skip)
            
            try:
                # Use the client's optimized request method
                data = await self.api_client._make_request_with_retry(
                    session, 
                    f"{self.api_client.BASE_URL}/v4/{self.api_client.chain_id}/transactions",
                    page_params,
                    endpoint="v4/transactions"
                )
            except Exception as e:
                print(f"    ⚠️ Page {pages + 1} failed: {e}")
                break
            
            page = data.get('results', [])
            if not page:
                break
            
            # Apply intelligent sampling if needed
            if data_source == DataSource.SAMPLE_DATA and strategy.sampling_rate < 1.0:
                sample_size = max(1, int(len(page) * strategy.sampling_rate))
                page = random.sample(page, min(sample_size, len(page)))
            
            # Process transactions
            page_transactions = []
            for tx_data in page:
                tx_id = tx_data.get('id', '')
                
                if tx_id in seen_ids:
                    continue
                seen_ids.add(tx_id)
                
                # Enhanced date filtering
                tx_timestamp = tx_data.get('timestamp', '')
                if tx_timestamp:
                    try:
                        tx_datetime = datetime.fromisoformat(tx_timestamp.replace('Z', '+00:00'))
                        if tx_datetime < cutoff_date:
                            continue
                    except:
                        pass  # If we can't parse timestamp, include it
                
                # Essential field validation
                if tx_data.get('impliedApy') is None:
                    continue
                
                # Create transaction object
                transaction = Transaction(
                    id=tx_id,
                    timestamp=tx_timestamp,
                    implied_apy=tx_data.get('impliedApy'),
                    valuation_usd=tx_data.get('valuation', {}).get('usd'),
                    market=market.address,
                    action=tx_data.get('action', ''),
                    value=tx_data.get('value')
                )
                page_transactions.append(transaction)
            
            transactions.extend(page_transactions)
            pages += 1
            
            # Stop if we've reached the target
            if len(transactions) >= strategy.max_transactions:
                break
            
            # Update pagination
            resume_token = data.get('resumeToken')
            if not resume_token:
                skip += len(page)
        
        print(f"    📊 Collected {len(transactions)} transactions using {data_source.value}")
        return transactions
    
    async def _get_price_based_transactions(self, 
                                          market: Market, 
                                          strategy: OptimizationStrategy) -> List[Transaction]:
        """Create synthetic transactions from price data as last resort"""
        print(f"    💰 Using price-based estimation for {market.name}")
        
        # This would typically involve getting price data and creating
        # synthetic transaction points based on price movements
        # For now, return empty list as this requires additional API endpoints
        
        return []
    
    def _record_success(self, market_address: str):
        """Record successful analysis"""
        self.success_tracker[market_address] += 1
        
        # Update market tier if we consistently succeed
        if self.success_tracker[market_address] >= 5:
            if market_address in self.market_tier_cache:
                current_tier = self.market_tier_cache[market_address]
                if current_tier == MarketTier.MEDIUM_VOLUME:
                    self.market_tier_cache[market_address] = MarketTier.HIGH_VOLUME
                elif current_tier == MarketTier.LOW_VOLUME:
                    self.market_tier_cache[market_address] = MarketTier.MEDIUM_VOLUME
    
    def _record_failure(self, market_address: str):
        """Record failed analysis"""
        self.failure_tracker[market_address] += 1
        
        # Update market tier if we consistently fail
        if self.failure_tracker[market_address] >= 3:
            if market_address in self.market_tier_cache:
                current_tier = self.market_tier_cache[market_address]
                if current_tier == MarketTier.HIGH_VOLUME:
                    self.market_tier_cache[market_address] = MarketTier.MEDIUM_VOLUME
                elif current_tier == MarketTier.MEDIUM_VOLUME:
                    self.market_tier_cache[market_address] = MarketTier.LOW_VOLUME
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """Get comprehensive optimization report"""
        total_markets = len(self.market_tier_cache)
        tier_distribution = defaultdict(int)
        success_rate_by_tier = defaultdict(list)
        
        for market_address, tier in self.market_tier_cache.items():
            tier_distribution[tier.value] += 1
            
            total_attempts = self.success_tracker[market_address] + self.failure_tracker[market_address]
            if total_attempts > 0:
                success_rate = self.success_tracker[market_address] / total_attempts
                success_rate_by_tier[tier.value].append(success_rate)
        
        return {
            'total_markets_analyzed': total_markets,
            'tier_distribution': dict(tier_distribution),
            'success_rates_by_tier': {
                tier: sum(rates) / len(rates) if rates else 0.0
                for tier, rates in success_rate_by_tier.items()
            },
            'top_problematic_markets': sorted(
                [(addr, self.failure_tracker[addr]) for addr in self.failure_tracker if self.failure_tracker[addr] > 0],
                key=lambda x: x[1], reverse=True
            )[:10],
            'optimization_effectiveness': {
                'markets_recovered_from_failure': len([
                    addr for addr in self.failure_tracker 
                    if self.failure_tracker[addr] > 0 and self.success_tracker[addr] > 0
                ])
            }
        }