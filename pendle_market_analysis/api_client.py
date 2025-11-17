#!/usr/bin/env python3
"""
Optimized API client for Pendle Market Analysis
Enhanced with advanced rate limiting, caching, batching, and monitoring
"""

import asyncio
import hashlib
import json
import os
import random
import time
import urllib.parse
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import aiohttp

from pendle_market_analysis.models import Market, Transaction, PendleApiError


@dataclass
class RequestMetrics:
    """Track API request metrics for optimization"""
    total_requests: int = 0
    rate_limited: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_response_time: float = 0.0
    computing_units_used: int = 0


@dataclass
class RateLimitState:
    """Manage rate limiting state and computing unit tracking with adaptive behavior"""
    tokens_per_second: float = 5.0  # Conservative rate limit
    computing_unit_budget: int = 1000  # Daily budget
    max_retry_duration: float = 30.0  # Maximum retry duration in seconds
    
    def __post_init__(self):
        self.computing_units: Dict[str, int] = defaultdict(int)
        self.request_times: deque = deque(maxlen=100)  # Track last 100 requests
        self.rate_limit_violations: deque = deque(maxlen=50)  # Track rate limit violations
        self.adaptive_cooldown: float = 0.0  # Additional cooldown based on violations
        self.last_reset_date: date = datetime.now().date()
    
    def can_make_request(self, endpoint: str = "", computing_units: int = 1) -> bool:
        """Check if we can make a request without hitting rate limits"""
        now = time.time()
        
        # Check if we need to reset daily budget
        self._check_daily_reset()
        
        # Clean old requests (older than 1 second)
        while self.request_times and now - self.request_times[0] > 1.0:
            self.request_times.popleft()
        
        # Apply adaptive cooldown if we've been rate limited recently
        if self.adaptive_cooldown > 0:
            if now - self.rate_limit_violations[-1] if self.rate_limit_violations else 0 < self.adaptive_cooldown:
                return False
            else:
                self.adaptive_cooldown = 0.0  # Reset adaptive cooldown
        
        # Check if we're within rate limits
        if len(self.request_times) >= self.tokens_per_second:
            return False
            
        # Check computing unit budget
        if self.computing_unit_budget - self.computing_units.get(endpoint, 0) < computing_units:
            return False
            
        return True
    
    def record_request(self, endpoint: str = "", computing_units: int = 1):
        """Record that we made a request"""
        self.request_times.append(time.time())
        self.computing_units[endpoint] += computing_units
        self.computing_unit_budget -= computing_units
    
    def record_rate_limit_violation(self, retry_after: Optional[float] = None):
        """Record a rate limit violation and adjust adaptive behavior"""
        now = time.time()
        self.rate_limit_violations.append(now)
        
        # Increase adaptive cooldown based on recent violations
        recent_violations = [t for t in self.rate_limit_violations if now - t < 300]  # Last 5 minutes
        
        if len(recent_violations) > 3:
            self.adaptive_cooldown = min(5.0, len(recent_violations) * 0.5)  # Max 5 second cooldown
        
        # Use Retry-After header value if provided
        if retry_after:
            self.adaptive_cooldown = max(self.adaptive_cooldown, retry_after)
    
    def get_recommended_delay(self) -> float:
        """Get recommended delay before next request based on current state"""
        now = time.time()
        
        # Base delay from adaptive cooldown
        delay = self.adaptive_cooldown if self.adaptive_cooldown > 0 else 0
        
        # Add delay based on recent rate limit violations
        recent_violations = [t for t in self.rate_limit_violations if now - t < 60]  # Last minute
        if recent_violations:
            delay = max(delay, len(recent_violations) * 0.5)
        
        return min(delay, self.max_retry_duration)
    
    def _check_daily_reset(self):
        """Reset daily computing unit budget if new day"""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.reset_budget()
            self.last_reset_date = current_date
    
    def reset_budget(self):
        """Reset daily computing unit budget"""
        self.computing_unit_budget = 1000
        self.computing_units.clear()
        self.rate_limit_violations.clear()
        self.adaptive_cooldown = 0.0
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current rate limiting metrics for monitoring"""
        now = time.time()
        recent_violations = [t for t in self.rate_limit_violations if now - t < 300]  # Last 5 minutes
        
        return {
            'tokens_per_second': self.tokens_per_second,
            'computing_unit_budget_remaining': self.computing_unit_budget,
            'recent_rate_limit_violations': len(recent_violations),
            'adaptive_cooldown': self.adaptive_cooldown,
            'requests_in_last_second': len([t for t in self.request_times if now - t < 1.0]),
            'last_reset_date': self.last_reset_date.isoformat()
        }


@dataclass
class CacheEntry:
    """Cache entry with TTL"""
    data: Any
    timestamp: datetime
    ttl_seconds: int
    
    @property
    def is_expired(self) -> bool:
        return time.time() - self.timestamp.timestamp() > self.ttl_seconds


class PendleAPIClientOptimized:
    """Enhanced Pendle API client with advanced optimization features"""
    
    # API version tracking for compatibility
    API_VERSION = "v4"
    BASE_URL = "https://api-v2.pendle.finance/core"
    
    # Version mapping for different endpoints
    ENDPOINT_VERSIONS = {
        "markets": "v1",
        "transactions": "v4",
        "limit-orders": "v2",
        "prices": "v1",
        "assets": "v1"
    }
    
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
    
    # API endpoint computing unit costs based on API specification
    COMPUTING_UNIT_COSTS = {
        "limit-orders": 3,  # Limit order endpoints
        "markets": 1,       # Market endpoints
        "transactions": 2,  # Transaction endpoints
        "prices": 1,        # Price endpoints
        "assets": 1,        # Asset endpoints
        "takers": 8,        # Taker limit order matching (high cost)
        "makers": 5,        # Maker limit order endpoints
        "sdk": 5            # SDK endpoints
    }
    
    # Cache TTL settings (in seconds)
    CACHE_TTL = {
        "markets": 1800,  # 30 minutes
        "transactions": 300,  # 5 minutes
        "prices": 60,  # 1 minute
        "assets": 3600  # 1 hour
    }
    
    def __init__(self, chain_id: int = 1, enable_cache: bool = True,
                 cache_dir: str = ".cache", max_concurrent: int = 5):
        self.chain_id = chain_id
        self.chain_name = self.CHAINS.get(chain_id, f"Chain {chain_id}")
        self.enable_cache = enable_cache
        self.cache_dir = Path(cache_dir)
        self.max_concurrent = max_concurrent
        
        # Initialize caching
        if self.enable_cache:
            self.cache_dir.mkdir(exist_ok=True)
            self._memory_cache: Dict[str, CacheEntry] = {}
        
        # Rate limiting and metrics
        self.rate_limiter = RateLimitState()
        self.metrics = RequestMetrics()
        self._session = None
        
        # Performance settings
        self.TRANSACTION_LIMIT_RECENT = 1000
        self.DAYS_OF_DATA = 120
        self.BASE_DELAY_MS = 160  # As per documentation recommendation
        self.MIN_TRANSACTIONS_FOR_ANALYSIS = 5
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key"""
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key for request"""
        sorted_params = tuple(sorted(params.items()))
        return f"{endpoint}_{hashlib.md5(str(sorted_params).encode()).hexdigest()}"
    
    def _load_from_cache(self, cache_key: str) -> Optional[Any]:
        """Load data from cache (memory + disk)"""
        if not self.enable_cache:
            return None
        
        # Check memory cache first
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if not entry.is_expired:
                self.metrics.cache_hits += 1
                return entry.data
            else:
                del self._memory_cache[cache_key]
        
        # Check disk cache
        cache_path = self._get_cache_path(cache_key)
        try:
            if cache_path.exists():
                with open(cache_path, 'r') as f:
                    cache_data = json.load(f)
                
                entry = CacheEntry(
                    data=cache_data['data'],
                    timestamp=datetime.fromisoformat(cache_data['timestamp']),
                    ttl_seconds=cache_data['ttl_seconds']
                )
                
                if not entry.is_expired:
                    self.metrics.cache_hits += 1
                    # Store in memory cache too
                    self._memory_cache[cache_key] = entry
                    return entry.data
                else:
                    cache_path.unlink()  # Remove expired cache file
                    
        except (json.JSONDecodeError, KeyError, OSError):
            pass  # Handle corrupted cache gracefully
        
        self.metrics.cache_misses += 1
        return None
    
    def _save_to_cache(self, cache_key: str, data: Any, ttl_category: str):
        """Save data to cache (memory + disk)"""
        if not self.enable_cache:
            return
        
        ttl = self.CACHE_TTL.get(ttl_category, 300)
        
        # Memory cache
        entry = CacheEntry(
            data=data,
            timestamp=datetime.now(),
            ttl_seconds=ttl
        )
        self._memory_cache[cache_key] = entry
        
        # Disk cache
        cache_path = self._get_cache_path(cache_key)
        try:
            cache_data = {
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'ttl_seconds': ttl
            }
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except OSError:
            pass  # Handle disk cache errors gracefully
    
    def _get_computing_units(self, endpoint: str) -> int:
        """Get computing units cost for an endpoint"""
        for key, cost in self.COMPUTING_UNIT_COSTS.items():
            if key in endpoint:
                return cost
        return 1  # Default cost
    
    async def _make_request_with_retry(self, session: aiohttp.ClientSession,
                                     url: str, params: Dict[str, Any],
                                     endpoint: str = "", max_retries: int = 5,
                                     cache_ttl_category: str = "default") -> Dict[str, Any]:
        """Enhanced request method with advanced retry and caching"""
        start_time = time.time()
        
        # Generate cache key
        cache_key = self._get_cache_key(url, params)
        
        # Try to load from cache first
        if params:  # Only cache GET requests with params
            cached_data = self._load_from_cache(cache_key)
            if cached_data is not None:
                return cached_data
        
        # Get computing units cost
        computing_units = self._get_computing_units(endpoint or url)
        
        # Check rate limits
        if not self.rate_limiter.can_make_request(endpoint, computing_units):
            # Wait for rate limit to reset
            await asyncio.sleep(1.0)
        
        encoded_params = {}
        for k, v in params.items():
            encoded_params[k] = urllib.parse.quote(str(v), safe='')
        
        query_string = "&".join([f"{k}={v}" for k, v in encoded_params.items()])
        full_url = f"{url}?{query_string}" if query_string else url
        
        last_exception = None
        
        for retry_count in range(max_retries + 1):
            try:
                # Record the request
                self.rate_limiter.record_request(endpoint, computing_units)
                self.metrics.total_requests += 1
                
                async with session.get(full_url) as response:
                    if response.ok:
                        data = await response.json()
                        
                        # Cache successful response
                        if params:
                            self._save_to_cache(cache_key, data, cache_ttl_category)
                        
                        # Update metrics
                        response_time = time.time() - start_time
                        self.metrics.avg_response_time = (
                            (self.metrics.avg_response_time * (self.metrics.total_requests - 1) + response_time)
                            / self.metrics.total_requests
                        )
                        
                        return data
                        
                    elif response.status == 429:
                        self.metrics.rate_limited += 1
                        
                        # Parse retry-after header if available
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            delay = float(retry_after)
                            self.rate_limiter.record_rate_limit_violation(delay)
                        else:
                            # Exponential backoff based on documentation (160ms + random)
                            delay = (self.BASE_DELAY_MS / 1000) * (2 ** retry_count) + random.uniform(0, 0.5)
                            self.rate_limiter.record_rate_limit_violation()
                        
                        print(f"    ⏱️ Rate limited (429), retrying in {delay:.1f}s...")
                        await asyncio.sleep(delay)
                        continue
                        
                    else:
                        # Use enhanced error handling with detailed information
                        raise PendleApiError.from_response(response, endpoint)
                        
            except aiohttp.ClientError as e:
                last_exception = e
                if retry_count < max_retries:
                    # Network error backoff
                    delay = (self.BASE_DELAY_MS / 1000) * (retry_count + 1) + random.uniform(0, 0.2)
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise PendleApiError(f"Network error after {max_retries} retries: {str(e)}")
        
        raise PendleApiError(f"Request failed after {max_retries + 1} attempts: {str(last_exception)}")
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create an optimized aiohttp session"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.max_concurrent,
                limit_per_host=3,
                keepalive_timeout=60,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(
                total=30,
                connect=10,
                sock_read=10
            )
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'PendleMarketAnalysis/2.0',
                    'Accept': 'application/json'
                }
            )
        
        return self._session
    
    async def close(self):
        """Clean up resources"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def get_api_metrics(self) -> Dict[str, Any]:
        """Get comprehensive API metrics for monitoring"""
        rate_limit_metrics = self.rate_limiter.get_metrics_summary()
        
        return {
            'request_metrics': {
                'total_requests': self.metrics.total_requests,
                'rate_limited': self.metrics.rate_limited,
                'cache_hits': self.metrics.cache_hits,
                'cache_misses': self.metrics.cache_misses,
                'cache_hit_rate': self.metrics.cache_hits / max(1, self.metrics.cache_hits + self.metrics.cache_misses),
                'avg_response_time': self.metrics.avg_response_time,
                'computing_units_used': self.metrics.computing_units_used
            },
            'rate_limit_metrics': rate_limit_metrics,
            'configuration': {
                'chain_id': self.chain_id,
                'chain_name': self.chain_name,
                'enable_cache': self.enable_cache,
                'max_concurrent': self.max_concurrent,
                'api_version': self.API_VERSION
            },
            'performance_indicators': {
                'requests_per_minute': len([t for t in self.rate_limiter.request_times if time.time() - t < 60]),
                'error_rate': self.metrics.rate_limited / max(1, self.metrics.total_requests),
                'efficiency_score': self._calculate_efficiency_score()
            }
        }
    
    def _calculate_efficiency_score(self) -> float:
        """Calculate efficiency score based on cache hits, response times, and error rates"""
        if self.metrics.total_requests == 0:
            return 1.0
        
        cache_efficiency = self.metrics.cache_hits / max(1, self.metrics.total_requests)
        time_efficiency = max(0, 1 - (self.metrics.avg_response_time / 10.0))  # Penalty for slow responses
        error_penalty = max(0, 1 - (self.metrics.rate_limited / max(1, self.metrics.total_requests)))
        
        return (cache_efficiency * 0.4 + time_efficiency * 0.4 + error_penalty * 0.2)
    
    def reset_metrics(self):
        """Reset all metrics for a fresh analysis run"""
        self.metrics = RequestMetrics()
        self.rate_limiter.reset_budget()
        
        # Clear cache if requested
        if self.enable_cache:
            self._memory_cache.clear()
    
    def log_performance_summary(self):
        """Log a comprehensive performance summary"""
        metrics = self.get_api_metrics()
        
        print(f"\n📊 API Performance Summary for {metrics['configuration']['chain_name']}:")
        print(f"  Requests: {metrics['request_metrics']['total_requests']}")
        print(f"  Cache Hit Rate: {metrics['request_metrics']['cache_hit_rate']:.2%}")
        print(f"  Avg Response Time: {metrics['request_metrics']['avg_response_time']:.3f}s")
        print(f"  Rate Limited: {metrics['request_metrics']['rate_limited']}")
        print(f"  Efficiency Score: {metrics['performance_indicators']['efficiency_score']:.3f}/1.0")
        print(f"  Computing Units Remaining: {metrics['rate_limit_metrics']['computing_unit_budget_remaining']}")
        print(f"  Active Rate Limit Violations: {metrics['rate_limit_metrics']['recent_rate_limit_violations']}")
    
    def validate_cache_keys(self) -> Dict[str, bool]:
        """Validate cache key generation for all relevant endpoints"""
        validation_results = {}
        
        # Test cache key generation for different endpoint types
        test_cases = [
            ("markets", {"chainId": "1"}, "Market data"),
            ("transactions", {"market": "0x123", "limit": "100"}, "Transaction data"),
            ("prices", {"asset": "0x456"}, "Price data"),
            ("assets", {"address": "0x789"}, "Asset data")
        ]
        
        for endpoint, params, description in test_cases:
            cache_key = self._get_cache_key(endpoint, params)
            cache_path = self._get_cache_path(cache_key)
            
            validation_results[description] = {
                'cache_key': cache_key,
                'cache_path': str(cache_path),
                'key_length': len(cache_key),
                'path_exists': cache_path.parent.exists()
            }
        
        return validation_results
    
    async def get_active_markets(self, session: Optional[aiohttp.ClientSession] = None) -> List[Market]:
        """Enhanced market fetching with caching and optimization"""
        print(f"🔍 Fetching active markets for {self.chain_name}...")
        
        if session is None:
            session = await self.get_session()
        
        try:
            endpoint = f"v1/{self.chain_id}/markets/active"
            url = f"{self.BASE_URL}/{endpoint}"
            
            # Use optimized request with caching
            data = await self._make_request_with_retry(
                session, url, {},
                endpoint=endpoint,
                cache_ttl_category="markets"
            )
            
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
    
    async def batch_get_transactions(self, market_addresses: List[str]) -> Dict[str, List[Transaction]]:
        """Batch fetch transactions for multiple markets efficiently"""
        print(f"🔄 Batch fetching transactions for {len(market_addresses)} markets...")
        
        if not market_addresses:
            return {}
        
        session = await self.get_session()
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def fetch_single_market(market_addr: str) -> Tuple[str, List[Transaction]]:
            async with semaphore:
                try:
                    transactions = await self.get_transactions(session, market_addr)
                    return market_addr, transactions
                except Exception as e:
                    print(f"    ⚠️ Failed to fetch transactions for {market_addr[:10]}: {e}")
                    return market_addr, []
        
        # Execute batch requests
        tasks = [fetch_single_market(addr) for addr in market_addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        transaction_data = {}
        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                market_addr, transactions = result
                transaction_data[market_addr] = transactions
        
        print(f"✅ Completed batch fetch for {len(transaction_data)} markets")
        return transaction_data
    
    async def get_transactions(self, session: aiohttp.ClientSession, market_addr: str,
                             use_advanced_filters: bool = True) -> List[Transaction]:
        """Enhanced transaction fetching with advanced optimization"""
        print(f"  📈 Fetching optimized transactions for {market_addr[:10]}...")
        
        base = f"{self.BASE_URL}/v4/{self.chain_id}/transactions"
        results = []
        skip = 0
        resume_token = None
        pages = 0
        seen_ids = set()
        
        from datetime import datetime, timedelta, timezone, date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.DAYS_OF_DATA)
        
        # Enhanced filtering for better performance
        base_params = {
            "market": market_addr,
            "limit": "1000",  # Use max limit for fewer requests
            "minValue": "0"
        }
        
        if use_advanced_filters:
            # Only fetch swap actions that matter for decline rate analysis
            base_params["action"] = "SWAP_PT,SWAP_PY,SWAP_YT"
            base_params["origin"] = "PENDLE_MARKET,YT"
        
        while pages < 4:  # Limit pages as per documentation
            params = base_params.copy()
            
            if resume_token:
                params["resumeToken"] = resume_token
            else:
                params["skip"] = str(skip)
            
            try:
                endpoint = f"v4/{self.chain_id}/transactions"
                data = await self._make_request_with_retry(
                    session, base, params,
                    endpoint=endpoint,
                    cache_ttl_category="transactions"
                )
            except Exception as e:
                print(f"    ⚠️ Failed to fetch page {pages + 1}: {e}")
                break
            
            page = data.get('results', [])
            if not page:
                break
            
            # Process transactions with enhanced filtering
            page_transactions = []
            for tx_data in page:
                tx_id = tx_data.get('id', '')
                
                # Early deduplication
                if tx_id in seen_ids:
                    continue
                seen_ids.add(tx_id)
                
                # Enhanced date filtering
                tx_timestamp = tx_data.get('timestamp', '')
                if tx_timestamp:
                    try:
                        tx_datetime = datetime.fromisoformat(tx_timestamp.replace('Z', '+00:00'))
                        # Only fetch recent data to save on processing
                        if tx_datetime < cutoff_date and pages > 1:
                            continue
                    except:
                        pass  # If we can't parse timestamp, include it
                
                # Essential field validation
                if tx_data.get('impliedApy') is None:
                    continue
                
                # Enhanced valuation handling
                valuation_usd = None
                valuation_data = tx_data.get('valuation', {})
                if isinstance(valuation_data, dict):
                    valuation_usd = valuation_data.get('usd')
                elif isinstance(valuation_data, (int, float)):
                    valuation_usd = valuation_data
                else:
                    valuation_usd = tx_data.get('valuation_usd')
                
                # Only include transactions with meaningful value
                if valuation_usd is not None and valuation_usd < 1:
                    continue
                
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
            
            # Early termination with better logic
            if len(results) >= self.TRANSACTION_LIMIT_RECENT:
                print(f"    ✅ Reached transaction limit ({len(results)} transactions)")
                break
            
            # Adaptive pagination pause
            resume_token = data.get('resumeToken')
            if not resume_token:
                skip += 1000  # Use larger chunks for skip-based pagination
            else:
                # Adaptive delay based on response time
                await asyncio.sleep(self.BASE_DELAY_MS / 1000)
        
        print(f"    🔄 Final: {len(results)} unique, recent transactions")
        return results
    
    async def get_asset_prices_batch(self, asset_ids: List[str]) -> Dict[str, Any]:
        """Batch fetch asset prices efficiently"""
        if not asset_ids:
            return {}
        
        print(f"💰 Fetching prices for {len(asset_ids)} assets...")
        
        session = await self.get_session()
        
        # Batch requests (API might support comma-separated IDs)
        batch_size = 50  # Reasonable batch size
        price_data = {}
        
        for i in range(0, len(asset_ids), batch_size):
            batch = asset_ids[i:i + batch_size]
            asset_ids_param = ",".join(batch)
            
            try:
                endpoint = f"v1/{self.chain_id}/assets/prices"
                url = f"{self.BASE_URL}/{endpoint}"
                
                params = {
                    "assetIds": asset_ids_param
                }
                
                data = await self._make_request_with_retry(
                    session, url, params,
                    endpoint=endpoint,
                    cache_ttl_category="prices"
                )
                
                # Process price data
                prices = data.get('prices', {})
                price_data.update(prices)
                
            except Exception as e:
                print(f"    ⚠️ Failed to fetch price batch {i//batch_size + 1}: {e}")
                continue
        
        print(f"✅ Retrieved prices for {len(price_data)} assets")
        return price_data
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        cache_hit_rate = 0
        if self.metrics.cache_hits + self.metrics.cache_misses > 0:
            cache_hit_rate = self.metrics.cache_hits / (self.metrics.cache_hits + self.metrics.cache_misses)
        
        return {
            "total_requests": self.metrics.total_requests,
            "rate_limited_requests": self.metrics.rate_limited,
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "cache_hit_rate": cache_hit_rate,
            "avg_response_time_ms": self.metrics.avg_response_time * 1000,
            "computing_units_used": dict(self.rate_limiter.computing_units),
            "computing_units_remaining": self.rate_limiter.computing_unit_budget
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.get_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# Legacy compatibility wrapper
class PendleAPIClient(PendleAPIClientOptimized):
    """Backward compatibility wrapper - inherits all optimizations"""
    
    def __init__(self, chain_id: int = 1):
        super().__init__(chain_id, enable_cache=True)
        
    async def fetch_json_optimized(self, session: aiohttp.ClientSession, url: str,
                                 params: Dict[str, str], retry_count: int = 0) -> Dict[str, Any]:
        """Legacy method - delegates to optimized version"""
        return await self._make_request_with_retry(session, url, params)