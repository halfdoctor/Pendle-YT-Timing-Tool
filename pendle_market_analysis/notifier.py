#!/usr/bin/env python3
"""
Output formatting and notification system for Pendle Market Analysis
Handles console output formatting and Telegram alerts
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import aiohttp

from pendle_market_analysis.models import DeclineRateAnalysis, PendleApiError, NotificationError


class NotificationCache:
    """Handles caching of sent notifications to prevent duplicates"""
    
    def __init__(self, cache_file: str = "notification_cache.json", cache_duration_hours: int = 24):
        self.cache_file = cache_file
        self.cache_duration_hours = cache_duration_hours
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Dict]:
        """Load notification cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load notification cache: {e}")
        return {}
    
    def _save_cache(self) -> None:
        """Save notification cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save notification cache: {e}")
    
    def _get_cache_key(self, market_address: str, chain_id: int) -> str:
        """Generate cache key for market"""
        return f"{chain_id}:{market_address}"
    
    def is_market_notified_recently(self, market_address: str, chain_id: int) -> bool:
        """Check if market was notified within cache duration"""
        cache_key = self._get_cache_key(market_address, chain_id)
        
        if cache_key not in self.cache:
            return False
        
        # Check if notification is within the cache duration
        notification_time = datetime.fromisoformat(self.cache[cache_key]['timestamp'])
        expiry_time = notification_time + timedelta(hours=self.cache_duration_hours)
        current_time = datetime.now(timezone.utc)
        
        return current_time < expiry_time
    
    def cache_market_notification(self, market_address: str, chain_id: int, market_name: str) -> None:
        """Cache a market notification"""
        cache_key = self._get_cache_key(market_address, chain_id)
        current_time = datetime.now(timezone.utc).isoformat()
        
        self.cache[cache_key] = {
            'market_address': market_address,
            'chain_id': chain_id,
            'market_name': market_name,
            'timestamp': current_time,
            'cache_duration_hours': self.cache_duration_hours
        }
        
        self._save_cache()
        print(f"💾 Cached notification for market {market_name} (expires in {self.cache_duration_hours} hours)")
    
    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries"""
        current_time = datetime.now(timezone.utc)
        expired_keys = []
        
        for cache_key, cache_data in self.cache.items():
            notification_time = datetime.fromisoformat(cache_data['timestamp'])
            expiry_time = notification_time + timedelta(hours=cache_data['cache_duration_hours'])
            
            if current_time >= expiry_time:
                expired_keys.append(cache_key)
        
        # Remove expired entries
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            self._save_cache()
            print(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        current_time = datetime.now(timezone.utc)
        active_count = 0
        expired_count = 0
        
        for cache_data in self.cache.values():
            notification_time = datetime.fromisoformat(cache_data['timestamp'])
            expiry_time = notification_time + timedelta(hours=cache_data['cache_duration_hours'])
            
            if current_time < expiry_time:
                active_count += 1
            else:
                expired_count += 1
        
        return {
            'total_entries': len(self.cache),
            'active_entries': active_count,
            'expired_entries': expired_count,
            'cache_file': self.cache_file,
            'cache_duration_hours': self.cache_duration_hours
        }



class Notifier:
    """Handles all output formatting and notification functionality"""
    
    def __init__(self, chain_id: int = 1, chain_name: str = "Ethereum", cache_duration_hours: int = 24):
        # Get chain information
        self.chain_id = chain_id
        self.chain_name = chain_name
        
        # Telegram configuration
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Initialize notification cache
        self.cache = NotificationCache(cache_duration_hours=cache_duration_hours)
        
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("⚠️ Telegram configuration incomplete. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file")
        else:
            print(f"📱 Telegram notifications enabled for chat {self.telegram_chat_id}")
        
        # Print cache stats on initialization
        stats = self.cache.get_cache_stats()
        print(f"💾 Notification cache: {stats['active_entries']} active, {stats['expired_entries']} expired entries")
    
    def print_optimized_results(self, analysis_results: List[DeclineRateAnalysis], active_markets_count: int) -> List[DeclineRateAnalysis]:
        """Print optimized analysis results"""
        print(f"\n" + "="*90)
        print(f"🚀 OPTIMIZED PENDLE MARKET ANALYSIS RESULTS")
        print(f"📊 Chain: {self.chain_name} (ID: {self.chain_id})")
        print(f"📈 Total Active Markets: {active_markets_count}")
        print(f"🔍 Markets Analyzed: {len(analysis_results)}")
        print(f"⏱️ Processing: Concurrent analysis with smart data limiting")
        print(f"="*90)
        
        # Priority Alert Section
        alert_markets = [a for a in analysis_results if a.decline_rate_exceeds_average]
        if alert_markets:
            print(f"\n🚨 IMMEDIATE ATTENTION REQUIRED:")
            for analysis in sorted(alert_markets, key=lambda x: abs(x.latest_daily_decline_rate), reverse=True):
                maturity_date = datetime.fromisoformat(analysis.market.expiry.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                print(f"  🔴 {analysis.market.name}")
                print(f"      Decline: {abs(analysis.latest_daily_decline_rate):.2f}%/day (avg: {abs(analysis.average_decline_rate):.2f}%)")
                print(f"      Volume: ${analysis.volume_usd:,.0f} | APY: {analysis.implied_apy*100:.1f}% | Maturity: {maturity_date}")
        else:
            print(f"\n✅ NO ALERT MARKETS FOUND")
        
        # Summary Table
        print(f"\n📋 ANALYSIS SUMMARY:")
        print(f"{'Market':<35} {'Decline Rate':<15} {'Volume':<12} {'APY':<8} {'Data Fresh':<12}")
        print("-" * 85)
        
        for analysis in analysis_results:
            market_name = analysis.market.name[:33]
            if analysis.decline_rate_exceeds_average:
                decline_str = f"🚨{abs(analysis.latest_daily_decline_rate):.1f}%"
            elif abs(analysis.average_decline_rate) > 0.1:
                decline_str = f"{analysis.latest_daily_decline_rate:+.1f}%"
            else:
                decline_str = "Stable"
            
            volume_str = f"${analysis.volume_usd/1000:.0f}k" if analysis.volume_usd > 0 else "N/A"
            apy_str = f"{analysis.implied_apy*100:.1f}%" if analysis.implied_apy > 0 else "N/A"
            freshness = f"{analysis.data_freshness_hours:.1f}h"
            
            print(f"{market_name:<35} {decline_str:<15} {volume_str:<12} {apy_str:<8} {freshness:<12}")
        
        # Statistics
        total_volume = sum(a.volume_usd for a in analysis_results)
        avg_freshness = sum(a.data_freshness_hours for a in analysis_results) / len(analysis_results) if analysis_results else 0
        
        print(f"\n📊 PERFORMANCE METRICS:")
        print(f"  💰 Total Volume: ${total_volume:,.0f}")
        print(f"  ⚡ Average Data Freshness: {avg_freshness:.1f} hours")
        print(f"  🚨 Alert Markets: {len(alert_markets)}/{len(analysis_results)}")
        
        if alert_markets:
            max_decline = max(abs(a.latest_daily_decline_rate) for a in alert_markets)
            print(f"  📈 Highest Decline Rate: {max_decline:.2f}%/day")
        
        print(f"\n" + "="*90)
        
        return alert_markets  # Return alert markets for Telegram
    
    async def send_telegram_message(self, message: str) -> bool:
        """Send a message to Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return False
            
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
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
    
    async def send_telegram_alerts(self, alert_markets: List[DeclineRateAnalysis]) -> None:
        """Send Telegram alerts for markets with decline rate issues"""
        if not alert_markets:
            print("📱 No alert markets found - no Telegram notifications sent")
            return
        
        # Clean up expired cache entries
        expired_count = self.cache.cleanup_expired_cache()
        
        # Filter markets that need notification (not cached recently)
        markets_to_notify = []
        markets_cached = []
        
        for analysis in alert_markets:
            market = analysis.market
            if self.cache.is_market_notified_recently(market.address, self.chain_id):
                markets_cached.append(analysis)
            else:
                markets_to_notify.append(analysis)
        
        # Log caching results
        if markets_cached:
            print(f"📱 Skipping {len(markets_cached)} markets due to 24h notification cache")
            for analysis in markets_cached[:3]:  # Show first 3 as examples
                market = analysis.market
                print(f"   ⏭️ {market.name} (cached)")
            if len(markets_cached) > 3:
                print(f"   ... and {len(markets_cached) - 3} more")
        
        if not markets_to_notify:
            print("📱 All alert markets are within cache period - no new Telegram notifications sent")
            return
            
        print(f"📱 Sending Telegram alerts for {len(markets_to_notify)} new alert markets...")
        
        # Prepare alert message
        alert_count = len(markets_to_notify)
        chain_info = f"{self.chain_name} (ID: {self.chain_id})"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        message = f"🚨 <b>Pendle Market Alert</b>\n\n"
        message += f"📊 <b>Chain:</b> {chain_info}\n"
        message += f"⚠️ <b>Alert Count:</b> {alert_count} markets\n"
        if markets_cached:
            message += f"⏭️ <b>Skipped (cached):</b> {len(markets_cached)} markets\n"
        message += f"\n"
        
        for i, analysis in enumerate(markets_to_notify, 1):
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
            message += f"   📊 <b>Decline Rate:</b> {decline_rate:.2f}%/day (avg: {avg_decline_rate:.2f}%)\n"
            message += f"   💰 <b>Volume (USD):</b> ${volume_usd:,.0f}\n"
            message += f"   📈 <b>Implied APY:</b> {implied_apy:.2f}%\n"
            message += f"   📅 <b>Maturity:</b> {maturity_date}\n"
            message += f"   🔗 <a href='{market_link}'>View Market</a>\n\n"

        message += f"⏰ <b>Analysis Time:</b> {timestamp}\n"
        message += f"🤖 <i>Sent by Pendle Market Analyzer</i>"
        
        # Send the message
        success = await self.send_telegram_message(message)
        
        if success:
            # Cache the markets that were just notified
            for analysis in markets_to_notify:
                market = analysis.market
                self.cache.cache_market_notification(market.address, self.chain_id, market.name)
            
            print(f"✅ Telegram alerts sent successfully for {len(markets_to_notify)} markets!")
            print(f"💾 Cached {len(markets_to_notify)} notifications for 24 hours")
        else:
            print(f"❌ Failed to send Telegram alerts")
    
    def get_cache_info(self) -> str:
        """Get formatted cache information for display"""
        stats = self.cache.get_cache_stats()
        
        info = f"📊 Notification Cache Status:\n"
        info += f"   💾 Cache File: {stats['cache_file']}\n"
        info += f"   ⏰ Cache Duration: {stats['cache_duration_hours']} hours\n"
        info += f"   📈 Active Entries: {stats['active_entries']}\n"
        info += f"   🗑️ Expired Entries: {stats['expired_entries']}\n"
        info += f"   📋 Total Entries: {stats['total_entries']}"
        
        return info
    
    def clear_cache(self) -> bool:
        """Clear all cache entries"""
        try:
            # Clear in-memory cache
            self.cache.cache = {}
            
            # Clear file cache
            if os.path.exists(self.cache.cache_file):
                os.remove(self.cache.cache_file)
            
            print(f"🧹 Notification cache cleared successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to clear cache: {e}")
            return False