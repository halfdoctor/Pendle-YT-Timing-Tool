#!/usr/bin/env python3
"""
API client for Pendle Market Analysis
Handles all HTTP interactions with the Pendle API
"""

import asyncio
import os
import random
import urllib.parse
from typing import Dict, List, Optional, Any
import aiohttp

from pendle_market_analysis.models import Market, Transaction, PendleApiError


class PendleAPIClient:
    """Handles all API interactions with Pendle Finance"""
    
    BASE_URL = "https://api-v2.pendle.finance/core"
    
    CHAINS = {
        1: "Ethereum",
        42161: "Arbitrum One", 
        10: "Optimism",
        56: "BNB Smart Chain",
        5000: "Mantle",
        8453: "Base",
        999: "Hyper EVM",
        146: "Sonic",
        9745: "Plasma",
        80094: "Berachain"
    }
    
    def __init__(self, chain_id: int = 1):
        self.chain_id = chain_id
        self.chain_name = self.CHAINS.get(chain_id, f"Chain {chain_id}")
        
        # Performance optimization settings
        self.TRANSACTION_LIMIT_RECENT = 1000
        self.DAYS_OF_DATA = 120
        self.BASE_DELAY_MS = 50
        self.MIN_TRANSACTIONS_FOR_ANALYSIS = 5
    
    async def fetch_json_optimized(self, session: aiohttp.ClientSession, url: str, 
                                 params: Dict[str, str], retry_count: int = 0) -> Dict[str, Any]:
        """Optimized JSON fetch with intelligent retry logic"""
        encoded_params = {}
        for k, v in params.items():
            encoded_params[k] = urllib.parse.quote(str(v), safe='')
        
        query_string = "&".join([f"{k}={v}" for k, v in encoded_params.items()])
        full_url = f"{url}?{query_string}" if query_string else url
        
        max_retries = 5
        base_delay = 1
        
        try:
            async with session.get(full_url) as response:
                if response.ok:
                    return await response.json()
                elif response.status == 429 and retry_count < max_retries:
                    # Exponential backoff for rate limiting
                    delay = base_delay * (2 ** retry_count) + random.uniform(0, 1)
                    print(f"    ⏱️ Rate limited, retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    return await self.fetch_json_optimized(session, url, params, retry_count + 1)
                else:
                    raise PendleApiError(f"HTTP error! status: {response.status}")
                    
        except aiohttp.ClientError as e:
            if retry_count < max_retries:
                delay = base_delay * (retry_count + 1)
                await asyncio.sleep(delay)
                return await self.fetch_json_optimized(session, url, params, retry_count + 1)
            raise PendleApiError(f"Network error: {str(e)}")
    
    async def get_active_markets(self, session: aiohttp.ClientSession) -> List[Market]:
        """Fetch active markets with error handling"""
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
    
    async def get_transactions(self, session: aiohttp.ClientSession, market_addr: str) -> List[Transaction]:
        """Optimized transaction fetching focused on decline rate analysis"""
        print(f"  📈 Fetching optimized transactions for {market_addr[:10]}...")
        
        base = f"{self.BASE_URL}/v4/{self.chain_id}/transactions"
        results = []
        skip = 0
        resume_token = None
        pages = 0
        seen_ids = set()
        
        from datetime import datetime, timedelta, timezone
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.DAYS_OF_DATA)
        
        while pages < 4:  # Reduced from 8 pages
            params = {
                "market": market_addr,
                "action": "SWAP_PT,SWAP_PY,SWAP_YT",
                "origin": "PENDLE_MARKET,YT",
                "limit": "500",
                "minValue": "0"
            }
            
            if resume_token:
                params["resumeToken"] = resume_token
            else:
                params["skip"] = str(skip)
            
            try:
                data = await self.fetch_json_optimized(session, base, params)
            except Exception as e:
                print(f"    ⚠️ Failed to fetch page {pages + 1}: {e}")
                break
            
            page = data.get('results', [])
            if not page:
                break
            
            # Process transactions with early filtering and deduplication
            page_transactions = []
            for tx_data in page:
                tx_id = tx_data.get('id', '')
                
                # Early deduplication
                if tx_id in seen_ids:
                    continue
                seen_ids.add(tx_id)
                
                # Filter by date if timestamp available
                tx_timestamp = tx_data.get('timestamp', '')
                if tx_timestamp:
                    try:
                        tx_datetime = datetime.fromisoformat(tx_timestamp.replace('Z', '+00:00'))
                        if tx_datetime < cutoff_date and pages > 0:  # Allow first page regardless
                            continue
                    except:
                        pass  # If we can't parse timestamp, include it
                
                # Quick check for implied APY (essential for decline rate analysis)
                if tx_data.get('impliedApy') is None:
                    continue
                
                # Handle valuation data
                valuation_data = tx_data.get('valuation', {})
                if isinstance(valuation_data, dict):
                    valuation_usd = valuation_data.get('usd')
                else:
                    valuation_usd = tx_data.get('valuation_usd')
                
                tx = Transaction(
                    id=tx_id,
                    timestamp=tx_timestamp,
                    implied_apy=tx_data.get('impliedApy'),
                    valuation_usd=valuation_usd,
                    market=tx_data.get('market', ''),
                    action=tx_data.get('action', ''),
                    value=tx_data.get('value')
                )
                page_transactions.append(tx)
            
            results.extend(page_transactions)
            pages += 1
            print(f"    📄 Page {pages}: {len(page_transactions)} filtered transactions")
            
            # Early termination if we have enough recent data
            if len(results) >= self.TRANSACTION_LIMIT_RECENT:
                print(f"    ✅ Reached transaction limit ({len(results)} transactions)")
                break
            
            resume_token = data.get('resumeToken')
            if not resume_token:
                skip += 500  # Reduced chunk size
            else:
                # Brief pause for cursor-based pagination
                await asyncio.sleep(self.BASE_DELAY_MS / 1000)
        
        print(f"    🔄 Final: {len(results)} unique, recent transactions")
        return results