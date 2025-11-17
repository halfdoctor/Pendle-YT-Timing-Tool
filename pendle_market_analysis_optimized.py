#!/usr/bin/env python3
"""
Enhanced Pendle Market Analysis with Advanced Optimizations
Features caching, rate limiting, batch processing, and comprehensive monitoring
Maintains backward compatibility while providing enhanced performance
"""

import asyncio
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
import aiohttp
import urllib.parse

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ python-dotenv not installed. Please install it: pip install python-dotenv")
    pass

# Import from the optimized modular structure
from pendle_market_analysis.models import Market, Transaction, DeclineRateAnalysis, PendleApiError
from pendle_market_analysis.api_client import PendleAPIClientOptimized  # Now uses enhanced version
from pendle_market_analysis.enhanced_analyzer import EnhancedPendleAnalyzer  # Use enhanced analyzer
from pendle_market_analysis.enhanced_analyzer import SmartBatchProcessor  # Use smart batch processor
from pendle_market_analysis.notifier import Notifier
from pendle_market_analysis.orchestrator import AnalysisOrchestrator


class OptimizedPendleAnalyzer:
    """Backward compatibility wrapper that uses the new modular structure"""
    
    # Legacy configuration that maps to the new structure
    MAX_CONCURRENT_MARKETS = 2
    MARKET_BATCH_DELAY = 5
    MARKETS_TO_ANALYZE = 10
    
    def __init__(self, chain_id: int = 1, cache_duration_hours: int = 24):
        self.chain_id = chain_id
        # Create the new orchestrator which handles everything
        self.orchestrator = AnalysisOrchestrator(chain_id, cache_duration_hours)
        
        # Legacy compatibility - expose some attributes
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.TELEGRAM_BOT_TOKEN or not self.TELEGRAM_CHAT_ID:
            print("⚠️ Telegram configuration incomplete. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file")
        else:
            print(f"📱 Telegram notifications enabled for chat {self.TELEGRAM_CHAT_ID}")
    
    # Legacy methods that delegate to the new structure
    async def fetch_json_optimized(self, session: aiohttp.ClientSession, url: str, 
                                 params: Dict[str, str], retry_count: int = 0) -> Dict[str, Any]:
        """Legacy method - delegates to API client"""
        return await self.orchestrator.api_client.fetch_json_optimized(session, url, params, retry_count)
    
    async def get_active_markets_optimized(self, session: aiohttp.ClientSession) -> List[Market]:
        """Legacy method - delegates to API client"""
        return await self.orchestrator.api_client.get_active_markets(session)
    
    async def get_transactions_optimized(self, session: aiohttp.ClientSession, 
                                       market_addr: str) -> List[Transaction]:
        """Legacy method - delegates to API client"""
        return await self.orchestrator.api_client.get_transactions(session, market_addr)
    
    def calculate_decline_rates_fast(self, transactions: List[Transaction]) -> Tuple[float, float, float]:
        """Legacy method - delegates to analyzer"""
        avg_decline, latest_decline = self.orchestrator.analyzer.calculate_decline_rates_fast(transactions)
        # Return 3 values as expected by legacy code
        return avg_decline, latest_decline, avg_decline  # Use avg_decline as third value
    
    def calculate_current_yt_price_fast(self, transactions: List[Transaction]) -> float:
        """Legacy method - delegates to analyzer"""
        return self.orchestrator.analyzer.calculate_current_yt_price_fast(transactions)
    
    def calculate_volume_fast(self, transactions: List[Transaction]) -> float:
        """Legacy method - delegates to analyzer"""
        return self.orchestrator.analyzer.calculate_volume_fast(transactions)
    
    def calculate_average_implied_apy_fast(self, transactions: List[Transaction]) -> float:
        """Legacy method - delegates to analyzer"""
        return self.orchestrator.analyzer.calculate_average_implied_apy_fast(transactions)
    
    async def analyze_market_optimized(self, session: aiohttp.ClientSession, 
                                     market: Market, index: int, total: int) -> DeclineRateAnalysis:
        """Legacy method - delegates to orchestrator"""
        return await self.orchestrator.analyze_single_market(session, market, index, total)
    
    def print_optimized_results(self, analysis_results: List[DeclineRateAnalysis], active_markets_count: int):
        """Legacy method - delegates to notifier"""
        return self.orchestrator.notifier.print_optimized_results(analysis_results, active_markets_count)
    
    async def send_telegram_message(self, message: str) -> bool:
        """Legacy method - delegates to notifier"""
        return await self.orchestrator.notifier.send_telegram_message(message)
    
    async def send_telegram_alerts(self, alert_markets: List[DeclineRateAnalysis]) -> None:
        """Legacy method - delegates to notifier"""
        return await self.orchestrator.notifier.send_telegram_alerts(alert_markets)
    
    # Legacy convenience properties for compatibility
    @property
    def chain_name(self):
        return self.orchestrator.api_client.chain_name
    
    @property
    def CHAINS(self):
        return self.orchestrator.api_client.CHAINS
    
    # Main legacy method that delegates to the new structure
    async def run_optimized_analysis(self):
        """Legacy method - delegates to orchestrator"""
        await self.orchestrator.run_analysis()


# Legacy convenience functions for direct compatibility
async def analyze_single_chain(chain_id: int, cache_duration_hours: int = 24) -> None:
    """Legacy convenience function"""
    orchestrator = AnalysisOrchestrator(chain_id, cache_duration_hours)
    await orchestrator.run_analysis()


async def analyze_all_chains(cache_duration_hours: int = 24) -> None:
    """Legacy convenience function"""
    from pendle_market_analysis.orchestrator import MultiChainAnalysisOrchestrator
    
    # Create orchestrators for all supported chains
    chain_orchestrators = []
    for chain_id in PendleAPIClientOptimized.CHAINS.keys():
        chain_orchestrators.append(AnalysisOrchestrator(chain_id, cache_duration_hours))
    
    # Create multi-chain orchestrator and run analysis
    multi_orchestrator = MultiChainAnalysisOrchestrator(chain_orchestrators)
    await multi_orchestrator.analyze_all_chains()


async def main():
    """Legacy main function - maintains original interface"""
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ['all', 'multi', 'chains']:
            # Analyze all chains
            await analyze_all_chains()
        else:
            # Analyze single chain
            try:
                chain_id = int(sys.argv[1])
                await analyze_single_chain(chain_id)
            except ValueError:
                print("❌ Invalid chain ID. Use a number for single chain or 'all' for multi-chain analysis")
                print("Usage:")
                print("  python pendle_market_analysis_optimized.py 1          # Analyze Ethereum only")
                print("  python pendle_market_analysis_optimized.py all        # Analyze all chains")
                return
    else:
        # Default: analyze all chains
        print("🔗 No chain specified - analyzing all chains by default")
        print("💡 To analyze a specific chain, use: python pendle_market_analysis_optimized.py <chain_id>")
        await analyze_all_chains()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        sys.exit(1)