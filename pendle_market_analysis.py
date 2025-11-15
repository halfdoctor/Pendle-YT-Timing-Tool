#!/usr/bin/env python3
"""
Pendle Market Analysis Tool

This script replicates the functionality of the MarketAnalysis.tsx React component
and automatically fetches market data and outputs analysis results.

Usage:
    python pendle_market_analysis.py [chain_id]

Default chain_id: 1 (Ethereum)
"""

import asyncio
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import aiohttp
import urllib.parse

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ python-dotenv not installed. Please install it: pip install python-dotenv")
    # Continue without dotenv - fallback to os.environ
    pass


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
    """Transaction data structure matching the TypeScript interface"""
    id: str
    timestamp: str
    implied_apy: Optional[float] = None
    valuation_usd: Optional[float] = None
    valuation: Optional[Dict] = None  # Add valuation field for proper API data mapping
    market: str = ""
    action: str = ""
    origin: str = ""
    value: Optional[float] = None


@dataclass
class MarketAnalysisData:
    """Market analysis results"""
    market: Market
    current_yt_price: float
    average_decline_rate: float
    latest_daily_decline_rate: float
    decline_rate_exceeds_average: bool
    volume_usd: float
    implied_apy: float


class PendleApiError(Exception):
    """Pendle-specific API error"""
    
    def __init__(self, message: str, status: Optional[int] = None,
                 code: Optional[str] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details
        self.name = 'PendleApiError'


class PendleMarketAnalyzer:
    """Pendle Market Analysis Tool - Python implementation"""
    
    BASE_URL = "https://api-v2.pendle.finance/core"
    MAX_PAGES = 8  # ~8000 rows upper bound
    RATE_LIMIT_DELAY = 9  # seconds between market requests
    ALERT_DECLINE_RATE_THRESHOLD = 1.5  # 50% higher than average decline rate
    MARKETS_TO_ANALYZE = 10  # Number of markets to analyze (set to all active markets)
    
    # Telegram configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # Supported chains mapping
    CHAINS = {
        1: "Ethereum",
        42161: "Arbitrum One",
        10: "Optimism",
        56: "BNB Smart Chain",
        5000: "Mantle",
        8453: "Base",
        999: "Hyper EVM"
    }
    
    def __init__(self, chain_id: int = 1):
        self.chain_id = chain_id
        self.chain_name = self.CHAINS.get(chain_id, f"Chain {chain_id}")
        
        # Validate Telegram configuration
        if not self.TELEGRAM_BOT_TOKEN or not self.TELEGRAM_CHAT_ID:
            print("⚠️ Telegram configuration incomplete. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file")
        else:
            print(f"📱 Telegram notifications enabled for chat {self.TELEGRAM_CHAT_ID}")
        
    async def fetch_json(self, session: aiohttp.ClientSession, url: str, params: Dict[str, str]) -> Dict[str, Any]:
        """Helper function to fetch JSON data with error handling"""
        # Properly encode URL parameters to handle resume tokens with special characters
        encoded_params = {}
        for k, v in params.items():
            encoded_params[k] = urllib.parse.quote(str(v), safe='')
        
        query_string = "&".join([f"{k}={v}" for k, v in encoded_params.items()])
        full_url = f"{url}?{query_string}" if query_string else url
        
        try:
            async with session.get(full_url) as response:
                if not response.ok:
                    # Log more details for debugging HTTP 400 errors
                    response_text = await response.text()
                    raise PendleApiError(
                        f"HTTP error! status: {response.status}. URL: {full_url}. Response: {response_text[:500]}",
                        status=response.status
                    )
                return await response.json()
        except aiohttp.ClientError as e:
            raise PendleApiError(f"Network error: {str(e)}")
    
    def sleep_with_jitter(self, base_ms: int = 160) -> None:
        """Sleep with random jitter to avoid rate limiting"""
        jitter = random.uniform(0, 100)
        time.sleep((base_ms + jitter) / 1000)
    
    async def get_active_markets(self, session: aiohttp.ClientSession) -> List[Market]:
        """Fetch active markets for the specified chain"""
        print(f"🔍 Fetching active markets for {self.chain_name}...")
        
        try:
            url = f"{self.BASE_URL}/v1/{self.chain_id}/markets/active"
            async with session.get(url) as response:
                if not response.ok:
                    raise PendleApiError(f"HTTP error! status: {response.status}")
                
                data = await response.json()
                markets_data = data.get('markets', [])
                
                markets = []
                for market_data in markets_data:
                    market = Market(
                        name=market_data.get('name', ''),
                        address=market_data.get('address', ''),
                        expiry=market_data.get('expiry', ''),
                        pt=market_data.get('pt', ''),
                        yt=market_data.get('yt', ''),
                        sy=market_data.get('sy', ''),
                        underlying_asset=market_data.get('underlyingAsset', '')
                    )
                    markets.append(market)
                
                print(f"📊 Found {len(markets)} active markets")
                return markets
                
        except Exception as e:
            print(f"❌ Failed to get active markets: {e}")
            raise PendleApiError(f"Failed to get active markets: {e}")
    
    async def get_transactions_all(self, session: aiohttp.ClientSession, market_addr: str) -> List[Transaction]:
        """Fetch all transactions for a specific market with pagination and deduplication"""
        print(f"  📈 Fetching transactions for market {market_addr[:10]}...")
        
        if not self.chain_id:
            raise PendleApiError("Unsupported network")
        
        base = f"{self.BASE_URL}/v4/{self.chain_id}/transactions"
        results = []
        skip = 0
        resume_token = None
        pages = 0
        
        while pages < self.MAX_PAGES:
            params = {
                "market": market_addr,
                "action": "SWAP_PT,SWAP_PY,SWAP_YT",
                "origin": "PENDLE_MARKET,YT",
                "limit": "1000",
                "minValue": "0"
            }
            
            if resume_token:
                params["resumeToken"] = resume_token
            else:
                params["skip"] = str(skip)
            
            try:
                data = await self.fetch_json(session, base, params)
            except Exception as e:
                raise PendleApiError(f"Network error while fetching transactions: {e}")
            
            page = data.get('results', [])
            if not page:
                break
            
            # Convert to Transaction objects
            page_transactions = []
            for tx_data in page:
                # Handle valuation data structure properly
                valuation_data = tx_data.get('valuation', {})
                if isinstance(valuation_data, dict):
                    valuation_usd = valuation_data.get('usd')
                else:
                    valuation_usd = tx_data.get('valuation_usd')
                
                tx = Transaction(
                    id=tx_data.get('id', ''),
                    timestamp=tx_data.get('timestamp', ''),
                    implied_apy=tx_data.get('impliedApy'),
                    valuation_usd=valuation_usd,
                    valuation=valuation_data if isinstance(valuation_data, dict) else None,
                    market=tx_data.get('market', ''),
                    action=tx_data.get('action', ''),
                    origin=tx_data.get('origin', ''),
                    value=tx_data.get('value')
                )
                page_transactions.append(tx)
            
            results.extend(page_transactions)
            pages += 1
            print(f"    📄 Page {pages}: Got {len(page_transactions)} transactions (total: {len(results)})")
            
            resume_token = data.get('resumeToken')
            if not resume_token:
                skip += 1000
            
            if pages >= self.MAX_PAGES:
                print(f"    ⚠️ Truncated transactions due to page cap")
                break
            
            self.sleep_with_jitter()
        
        # Client-side deduplication
        seen_ids = set()
        dedup_transactions = []
        for tx in results:
            if tx.id and tx.id not in seen_ids:
                seen_ids.add(tx.id)
                dedup_transactions.append(tx)
        
        print(f"    🔄 Deduplication: {len(results)} → {len(dedup_transactions)} unique transactions")
        return dedup_transactions
    
    def calculate_current_yt_price(self, transactions: List[Transaction], market: Market) -> float:
        """Calculate current YT price using multiple approaches"""
        current_yt_price = 0.0
        
        # Approach 1: Direct YT transactions with value
        yt_transactions = [
            tx for tx in transactions
            if tx.action and ('SWAP_YT' in tx.action or 'SWAP_PY' in tx.action)
        ]
        
        if yt_transactions:
            latest_yt_txs = [
                tx for tx in yt_transactions
                if tx.value is not None and tx.value is not None and tx.value > 0
            ]
            latest_yt_txs.sort(key=lambda x: datetime.fromisoformat(x.timestamp.replace('Z', '+00:00')), reverse=True)
            
            if latest_yt_txs:
                current_yt_price = latest_yt_txs[0].value or 0.0
        
        # Approach 2: Any transaction with reasonable YT price value
        if current_yt_price == 0:
            price_transactions = [
                tx for tx in transactions
                if tx.value is not None and tx.value is not None and 0.001 < tx.value < 5
            ]
            price_transactions.sort(key=lambda x: datetime.fromisoformat(x.timestamp.replace('Z', '+00:00')), reverse=True)
            
            if price_transactions:
                current_yt_price = price_transactions[0].value or 0.0
        
        # Approach 3: Calculate from implied APY if still no price
        if current_yt_price == 0:
            recent_apy_txs = [
                tx for tx in transactions
                if tx.implied_apy is not None and tx.implied_apy is not None and tx.implied_apy > 0
            ]
            recent_apy_txs.sort(key=lambda x: datetime.fromisoformat(x.timestamp.replace('Z', '+00:00')), reverse=True)
            
            if recent_apy_txs:
                # Simple YT price estimation based on implied APY
                # YT price = 1 / (1 + APY)^time_to_maturity
                try:
                    expiry_date = datetime.fromisoformat(market.expiry.replace('Z', '+00:00'))
                    now_utc = datetime.now(timezone.utc)
                    time_to_maturity_years = max(0.1, (expiry_date - now_utc).days / 365.0)
                    implied_apy = recent_apy_txs[0].implied_apy
                    if implied_apy is not None:
                        current_yt_price = 1 / math.pow(1 + implied_apy, time_to_maturity_years)
                except:
                    pass
        
        return current_yt_price
    
    def calculate_volume_usd(self, transactions: List[Transaction]) -> float:
        """Calculate total volume in USD from transactions matching TypeScript logic"""
        return sum(
            (tx.valuation.get('usd') if tx.valuation and isinstance(tx.valuation, dict) else tx.valuation_usd) or 0
            for tx in transactions
        )
    
    def calculate_average_implied_apy(self, transactions: List[Transaction]) -> float:
        """Calculate average implied APY from transactions"""
        apy_values = [tx.implied_apy for tx in transactions if tx.implied_apy is not None and tx.implied_apy is not None]
        return sum(apy_values) / len(apy_values) if apy_values else 0.0
    
    def calculate_decline_rates(self, transactions: List[Transaction]) -> tuple[float, float]:
        """Calculate historic and latest daily decline rates"""
        
        # Use timezone-aware datetime.now()
        now_utc = datetime.now(timezone.utc)
        
        # Filter transactions with implied APY and sort by timestamp
        apy_transactions = [
            tx for tx in transactions
            if tx.implied_apy is not None and tx.implied_apy is not None and tx.timestamp
        ]
        apy_transactions.sort(key=lambda x: datetime.fromisoformat(x.timestamp.replace('Z', '+00:00')))
        
        # Calculate average decline rate
        average_decline_rate = 0.0
        if len(apy_transactions) > 1:
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
            except:
                pass
        
        # If we have very few transactions, use a simpler calculation
        if average_decline_rate == 0 and len(transactions) > 0:
            recent_txs = transactions[-5:]  # Last 5 transactions
            recent_apy = [tx.implied_apy for tx in recent_txs if tx.implied_apy is not None]
            if len(recent_apy) >= 2:
                apy_diff = recent_apy[-1] - recent_apy[0]
                average_decline_rate = apy_diff * 100  # Simple percentage change
        
        # Calculate latest daily decline rate (last 24 hours)
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
            except:
                pass
        
        return average_decline_rate, latest_daily_decline_rate
    
    async def analyze_market(self, session: aiohttp.ClientSession, market: Market, index: int, total: int) -> MarketAnalysisData:
        """Analyze a single market and return analysis results"""
        print(f"📊 Analyzing market {index + 1}/{total}: {market.name}")
        
        try:
            transactions = await self.get_transactions_all(session, market.address)
            
            # Debug: Log sample transaction structure
            if transactions:
                sample_tx = transactions[0]
                print(f"    🔍 Sample transaction: action={sample_tx.action}, value={sample_tx.value}, "
                      f"impliedApy={sample_tx.implied_apy}, timestamp={sample_tx.timestamp}")
            
            # Calculate current YT price using multiple approaches
            current_yt_price = self.calculate_current_yt_price(transactions, market)
            print(f"    💰 Final YT price: {current_yt_price:.6f}")
            
            # Calculate volume and average APY
            volume_usd = self.calculate_volume_usd(transactions)
            average_implied_apy = self.calculate_average_implied_apy(transactions)
            
            # Calculate decline rates
            average_decline_rate, latest_daily_decline_rate = self.calculate_decline_rates(transactions)
            
            # Check if latest decline rate exceeds average by more than 50%
            decline_rate_exceeds_average = abs(latest_daily_decline_rate) > abs(average_decline_rate) * (self.ALERT_DECLINE_RATE_THRESHOLD)
            
            return MarketAnalysisData(
                market=market,
                current_yt_price=current_yt_price,
                average_decline_rate=average_decline_rate,
                latest_daily_decline_rate=latest_daily_decline_rate,
                decline_rate_exceeds_average=decline_rate_exceeds_average,
                volume_usd=volume_usd,
                implied_apy=average_implied_apy
            )
            
        except Exception as e:
            print(f"    ❌ Failed to analyze market {market.name}: {e}")
            # Return market with zero values instead of skipping
            return MarketAnalysisData(
                market=market,
                current_yt_price=0.0,
                average_decline_rate=0.0,
                latest_daily_decline_rate=0.0,
                decline_rate_exceeds_average=False,
                volume_usd=0.0,
                implied_apy=0.0
            )
    
    def print_analysis_results(self, analysis_results: List[MarketAnalysisData], active_markets_count: int):
        """Print the analysis results in a formatted way"""
        print(f"\n" + "="*80)
        print(f"🎯 PENDLE MARKET ANALYSIS RESULTS")
        print(f"📊 Chain: {self.chain_name} (ID: {self.chain_id})")
        print(f"📈 Total Active Markets: {active_markets_count}")
        print(f"🔍 Markets Analyzed: {len(analysis_results)}")
        print(f"="*80)
        
        # Market Summary Table
        print(f"\n📋 MARKET ANALYSIS SUMMARY:")
        print(f"{'Market Name':<30} {'YT Price':<12} {'Decline Rate':<15} {'Volume (USD)':<15} {'Implied APY':<12} {'Maturity':<12}")
        print("-" * 100)
        
        for analysis in analysis_results:
            maturity_date = datetime.fromisoformat(analysis.market.expiry.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            yt_price_str = f"{analysis.current_yt_price:.4f}" if analysis.current_yt_price > 0 else "N/A"
            
            if analysis.decline_rate_exceeds_average:
                decline_str = f"⚠️ {abs(analysis.latest_daily_decline_rate):.2f}%/day"
            elif abs(analysis.average_decline_rate) > 0.01:
                decline_str = f"{analysis.average_decline_rate:.2f}%/day"
            else:
                decline_str = "Stable"
            
            volume_str = f"${analysis.volume_usd:,.0f}" if analysis.volume_usd > 0 else "N/A"
            apy_str = f"{(analysis.implied_apy * 100):.2f}%" if analysis.implied_apy > 0 else "N/A"
            
            print(f"{analysis.market.name[:28]:<30} {yt_price_str:<12} {decline_str:<15} {volume_str:<15} {apy_str:<12} {maturity_date:<12}")
        
        # Alert Section
        alert_markets = [a for a in analysis_results if a.decline_rate_exceeds_average]
        if alert_markets:
            print(f"\n🚨 ALERT MARKETS (Decline Rate Exceeds Average):")
            for analysis in alert_markets:
                print(f"  ⚠️  {analysis.market.name} on {analysis.market.expiry}")
                print(f"      Latest: {abs(analysis.latest_daily_decline_rate):.2f}% vs Average: {abs(analysis.average_decline_rate):.2f}%")
        
        # Statistics
        total_volume = sum(a.volume_usd for a in analysis_results)
        avg_yt_price = sum(a.current_yt_price for a in analysis_results if a.current_yt_price > 0) / max(1, len([a for a in analysis_results if a.current_yt_price > 0]))
        stable_markets = len([a for a in analysis_results if abs(a.average_decline_rate) <= 0.01])
        
        print(f"\n📊 OVERALL STATISTICS:")
        print(f"  💰 Total Volume: ${total_volume:,.0f}")
        print(f"  📈 Average YT Price: {avg_yt_price:.4f}")
        print(f"  🟢 Stable Markets: {stable_markets}/{len(analysis_results)}")
        print(f"  🔴 Alert Markets: {len(alert_markets)}/{len(analysis_results)}")
        
        print(f"\n" + "="*80)
    
    async def send_telegram_message(self, message: str) -> bool:
        """Send a message to Telegram"""
        if not self.TELEGRAM_BOT_TOKEN or not self.TELEGRAM_CHAT_ID:
            return False
            
        url = f"https://api.telegram.org/bot{self.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": self.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.ok:
                        return True
                    else:
                        error_text = await response.text()
                        print(f"❌ Telegram API error: {response.status} - {error_text}")
                        return False
        except Exception as e:
            print(f"❌ Failed to send Telegram message: {e}")
            return False
    
    async def send_telegram_alerts(self, analysis_results: List[MarketAnalysisData]) -> None:
        """Send Telegram alerts for markets with decline rate issues"""
        alert_markets = [a for a in analysis_results if a.decline_rate_exceeds_average]
        
        if not alert_markets:
            print("📱 No alert markets found - no Telegram notifications sent")
            return
            
        print(f"📱 Sending Telegram alerts for {len(alert_markets)} alert markets...")
        
        # Prepare alert message
        alert_count = len(alert_markets)
        chain_info = f"{self.chain_name} (ID: {self.chain_id})"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        message = f"🚨 <b>Pendle Market Alert</b>\n\n"
        message += f"📊 <b>Chain:</b> {chain_info}\n"
        message += f"⚠️ <b>Alert Count:</b> {alert_count} markets\n\n"
        
        for i, analysis in enumerate(alert_markets, 1):
            market = analysis.market
            maturity_date = datetime.fromisoformat(market.expiry.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            
            # Format numbers for display
            decline_rate = abs(analysis.latest_daily_decline_rate)
            avg_decline_rate = abs(analysis.average_decline_rate)
            volume_usd = analysis.volume_usd
            implied_apy = analysis.implied_apy * 100 if analysis.implied_apy > 0 else 0
            
            # Create market link
            market_link = f"https://app.pendle.finance/trade/markets/{market.address}/swap?view=yt"
            
            message += f"📈 <b>Market #{i}:</b> {market.name}\n"
            message += f"   📊 <b>Decline Rate:</b> {decline_rate:.2f}%per day (avg: {avg_decline_rate:.2f})\n"
            message += f"   💰 <b>Volume (USD):</b> ${volume_usd:,.0f}\n"
            message += f"   📈 <b>Implied APY:</b> {implied_apy:.2f}%\n"
            message += f"   📅 <b>Maturity:</b> {maturity_date}\n"
            message += f"   🔗 <a href='{market_link}'>View Market</a>\n\n"

        message += f"⏰ <b>Analysis Time:</b> {timestamp}\n"
        message += f"🤖 <i>Sent by Pendle Market Analyzer</i>"
        
        # Send the message
        success = await self.send_telegram_message(message)
        
        if success:
            print(f"✅ Telegram alerts sent successfully!")
        else:
            print(f"❌ Failed to send Telegram alerts")
    
    async def run_analysis(self):
        """Main analysis function"""
        print(f"🚀 Starting Pendle Market Analysis for {self.chain_name}")
        print(f"⏰ Analysis started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        connector = aiohttp.TCPConnector(limit=10)
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            try:
                # Fetch active markets
                active_markets = await self.get_active_markets(session)
                
                if not active_markets:
                    print("❌ No active markets found!")
                    return
                
                print(f"📊 Analyzing all {len(active_markets)} active markets")
                # markets_to_analyze = active_markets
                markets_to_analyze = active_markets[:self.MARKETS_TO_ANALYZE]
                # Process markets sequentially to avoid rate limiting
                analysis_results = []
                
                for i, market in enumerate(markets_to_analyze):
                    analysis = await self.analyze_market(session, market, i, len(markets_to_analyze))
                    analysis_results.append(analysis)
                    
                    # Add delay between requests to respect rate limits
                    if i < len(markets_to_analyze) - 1:
                        print(f"    ⏱️  Waiting {self.RATE_LIMIT_DELAY} seconds to respect rate limits...")
                        await asyncio.sleep(self.RATE_LIMIT_DELAY)
                
                # Print results
                self.print_analysis_results(analysis_results, len(active_markets))
                
                # Send Telegram alerts for markets with decline rate issues
                await self.send_telegram_alerts(analysis_results)
                
            except Exception as e:
                print(f"❌ Analysis failed: {e}")
                raise


async def main():
    """Main function"""
    # Parse command line arguments
    chain_id = 1  # Default to Ethereum
    if len(sys.argv) > 1:
        try:
            chain_id = int(sys.argv[1])
        except ValueError:
            print("❌ Invalid chain ID. Using default (1 - Ethereum)")
            print(f"Supported chains: {PendleMarketAnalyzer.CHAINS}")
            return
    
    # Validate chain ID
    if chain_id not in PendleMarketAnalyzer.CHAINS:
        print(f"❌ Unsupported chain ID: {chain_id}")
        print(f"Supported chains:")
        for cid, name in PendleMarketAnalyzer.CHAINS.items():
            print(f"  {cid}: {name}")
        return
    
    # Create and run analyzer
    analyzer = PendleMarketAnalyzer(chain_id)
    await analyzer.run_analysis()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Analysis failed with error: {e}")
        sys.exit(1)