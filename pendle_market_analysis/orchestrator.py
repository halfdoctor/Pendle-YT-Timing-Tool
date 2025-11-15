#!/usr/bin/env python3
"""
Main workflow orchestration for Pendle Market Analysis
Coordinates API client, analyzer, and notifier components
"""

import asyncio
import random
import time
from typing import List

import aiohttp

from pendle_market_analysis.models import PendleApiError, AnalysisError, NotificationError
from pendle_market_analysis.api_client import PendleAPIClient
from pendle_market_analysis.analyzer import PendleAnalyzer
from pendle_market_analysis.notifier import Notifier
from pendle_market_analysis.models import DeclineRateAnalysis, Market


class AnalysisOrchestrator:
    """Orchestrates the complete analysis workflow"""
    
    # Performance optimization settings
    MAX_CONCURRENT_MARKETS = 2  # Reduced for better rate limiting
    MARKETS_TO_ANALYZE = 10  # Process markets number
    MARKET_BATCH_DELAY = 5  # Reduced from 9 seconds
    
    def __init__(self, chain_id: int = 1, cache_duration_hours: int = 24):
        self.chain_id = chain_id
        self.api_client = PendleAPIClient(chain_id)
        self.analyzer = PendleAnalyzer()
        self.notifier = Notifier(chain_id, self.api_client.chain_name, cache_duration_hours)
        
        # Setup semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_MARKETS)
    
    async def analyze_single_market(self, session: aiohttp.ClientSession, 
                                  market: Market, index: int, total: int) -> DeclineRateAnalysis:
        """Analyze a single market with concurrency control"""
        async with self.semaphore:
            print(f"📊 [{index + 1}/{total}] Analyzing: {market.name}")
            
            try:
                # Fetch transactions for this market
                transactions = await self.api_client.get_transactions(session, market.address)
                
                # Analyze the market
                analysis = self.analyzer.analyze_market(market, transactions)
                return analysis
                
            except Exception as e:
                print(f"    ❌ Analysis failed: {e}")
                return DeclineRateAnalysis(
                    market=market, current_yt_price=0.0, average_decline_rate=0.0,
                    latest_daily_decline_rate=0.0, decline_rate_exceeds_average=False,
                    volume_usd=0.0, implied_apy=0.0, transaction_count=0,
                    data_freshness_hours=0.0
                )
    
    async def run_analysis(self):
        """Run the complete market analysis workflow"""
        print(f"🚀 Starting OPTIMIZED Pendle Market Analysis for {self.api_client.chain_name}")
        print(f"⏰ Analysis started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⚡ Optimizations: Concurrent processing, smart data limiting, early termination")
        
        start_time = time.time()
        
        connector = aiohttp.TCPConnector(limit=50)  # Increased connection pool
        timeout = aiohttp.ClientTimeout(total=300)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            try:
                # Fetch active markets
                active_markets = await self.api_client.get_active_markets(session)
                
                if not active_markets:
                    print("❌ No active markets found!")
                    return
                
                # Select markets to analyze
                # markets_to_analyze = active_markets[:self.MARKETS_TO_ANALYZE]  # Limit for testing
                markets_to_analyze = active_markets
                print(f"📊 Processing {len(markets_to_analyze)} markets with {self.MAX_CONCURRENT_MARKETS} concurrent workers")
                
                # Process markets with proper rate limiting
                analysis_results = []
                
                # Process markets in batches to respect rate limits
                for i in range(0, len(markets_to_analyze), self.MAX_CONCURRENT_MARKETS):
                    batch = markets_to_analyze[i:i + self.MAX_CONCURRENT_MARKETS]
                    batch_size = len(batch)
                    
                    print(f"📦 Processing batch {i//self.MAX_CONCURRENT_MARKETS + 1}: {batch_size} markets")
                    
                    # Process batch concurrently
                    tasks = [
                        self.analyze_single_market(session, market, i + j, len(markets_to_analyze))
                        for j, market in enumerate(batch)
                    ]
                    
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for result in batch_results:
                        if isinstance(result, Exception):
                            print(f"❌ Market analysis failed: {result}")
                        else:
                            analysis_results.append(result)
                    
                    # Rate limiting delay between batches
                    if i + self.MAX_CONCURRENT_MARKETS < len(markets_to_analyze):
                        delay = self.MARKET_BATCH_DELAY + random.uniform(0, 2)
                        print(f"    ⏱️ Rate limiting: waiting {delay:.1f}s before next batch...")
                        await asyncio.sleep(delay)
                
                # Print results and get alert markets
                alert_markets = self.notifier.print_optimized_results(analysis_results, len(active_markets))
                
                # Send Telegram alerts for markets with decline rate issues
                await self.notifier.send_telegram_alerts(alert_markets)
                
                # Performance summary
                elapsed_time = time.time() - start_time
                print(f"\n⚡ PERFORMANCE SUMMARY:")
                print(f"  ⏱️ Total Time: {elapsed_time:.1f} seconds")
                print(f"  📊 Markets/Second: {len(analysis_results)/elapsed_time:.2f}")
                print(f"  🎯 Target Achieved: Accurate decline rate analysis with rate limiting")
                
                return analysis_results, alert_markets
                
            except Exception as e:
                print(f"❌ Analysis failed: {e}")
                raise


class MultiChainAnalysisOrchestrator:
    """Handles analysis across multiple chains"""
    
    def __init__(self, chain_orchestrators: List[AnalysisOrchestrator]):
        self.chain_orchestrators = chain_orchestrators
    
    async def analyze_all_chains(self):
        """Analyze all supported chains sequentially"""
        print("🚀 Starting MULTI-CHAIN Pendle Market Analysis")
        print(f"⏰ Analysis started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔗 Processing {len(self.chain_orchestrators)} chains sequentially")
        print("="*90)
        
        start_time = time.time()
        chain_results = {}
        
        for i, orchestrator in enumerate(self.chain_orchestrators, 1):
            chain_name = orchestrator.api_client.chain_name
            print(f"\n{'='*20} CHAIN {i}/{len(self.chain_orchestrators)}: {chain_name} {'='*20}")
            
            try:
                chain_start_time = time.time()
                await orchestrator.run_analysis()
                
                chain_end_time = time.time()
                chain_duration = chain_end_time - chain_start_time
                chain_results[orchestrator.chain_id] = {
                    'name': chain_name,
                    'status': 'success',
                    'duration': chain_duration
                }
                
                print(f"✅ Completed {chain_name} in {chain_duration:.1f} seconds")
                
                # Add delay between chains to avoid rate limiting
                if i < len(self.chain_orchestrators):
                    delay = 10 + random.uniform(0, 5)  # 10-15 second delay
                    print(f"⏱️ Waiting {delay:.1f}s before next chain...")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                print(f"❌ Failed to analyze {chain_name} (ID: {orchestrator.chain_id}): {e}")
                chain_end_time = time.time()
                chain_duration = chain_end_time - chain_start_time
                chain_results[orchestrator.chain_id] = {
                    'name': chain_name,
                    'status': 'failed',
                    'duration': chain_duration,
                    'error': str(e)
                }
        
        # Print final summary
        total_time = time.time() - start_time
        print(f"\n{'='*90}")
        print(f"🏁 MULTI-CHAIN ANALYSIS COMPLETE")
        print(f"⏰ Total Time: {total_time:.1f} seconds")
        print(f"📊 Chains Processed: {len([r for r in chain_results.values() if r['status'] == 'success'])}/{len(self.chain_orchestrators)}")
        
        print(f"\n📋 CHAIN SUMMARY:")
        for chain_id, result in chain_results.items():
            status_icon = "✅" if result['status'] == 'success' else "❌"
            print(f"  {status_icon} {result['name']} (ID: {chain_id}): {result['duration']:.1f}s")
            if result['status'] == 'failed':
                print(f"      Error: {result['error']}")
        
        print(f"{'='*90}")
        return chain_results