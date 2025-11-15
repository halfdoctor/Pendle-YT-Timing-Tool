#!/usr/bin/env python3
"""
Output formatting and notification system for Pendle Market Analysis
Handles console output formatting and Telegram alerts
"""

import os
from datetime import datetime
from typing import List

import aiohttp

from pendle_market_analysis.models import DeclineRateAnalysis, PendleApiError, NotificationError


class Notifier:
    """Handles all output formatting and notification functionality"""
    
    def __init__(self, chain_id: int = 1, chain_name: str = "Ethereum"):
        # Get chain information
        self.chain_id = chain_id
        self.chain_name = chain_name
        
        # Telegram configuration
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("⚠️ Telegram configuration incomplete. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file")
        else:
            print(f"📱 Telegram notifications enabled for chat {self.telegram_chat_id}")
    
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
            print(f"✅ Telegram alerts sent successfully!")
        else:
            print(f"❌ Failed to send Telegram alerts")