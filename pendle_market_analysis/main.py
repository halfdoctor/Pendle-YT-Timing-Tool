#!/usr/bin/env python3
"""
CLI entry points for Pendle Market Analysis
Provides command-line interface for analyzing single chains or multiple chains
"""

import asyncio
import sys

from pendle_market_analysis.api_client import PendleAPIClient
from pendle_market_analysis.orchestrator import AnalysisOrchestrator, MultiChainAnalysisOrchestrator


async def analyze_single_chain(chain_id: int) -> None:
    """Analyze a single chain"""
    if chain_id not in PendleAPIClient.CHAINS:
        print(f"❌ Unsupported chain ID: {chain_id}")
        return
    
    orchestrator = AnalysisOrchestrator(chain_id)
    await orchestrator.run_analysis()


async def analyze_all_chains() -> None:
    """Analyze all supported chains sequentially"""
    # Create orchestrators for all supported chains
    chain_orchestrators = []
    for chain_id in PendleAPIClient.CHAINS.keys():
        chain_orchestrators.append(AnalysisOrchestrator(chain_id))
    
    # Create multi-chain orchestrator and run analysis
    multi_orchestrator = MultiChainAnalysisOrchestrator(chain_orchestrators)
    await multi_orchestrator.analyze_all_chains()


async def main():
    """Main function - supports both single chain and multi-chain analysis"""
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
                print("  python -m pendle_market_analysis.main 1          # Analyze Ethereum only")
                print("  python -m pendle_market_analysis.main all        # Analyze all chains")
                return
    else:
        # Default: analyze all chains
        print("🔗 No chain specified - analyzing all chains by default")
        print("💡 To analyze a specific chain, use: python -m pendle_market_analysis.main <chain_id>")
        await analyze_all_chains()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        sys.exit(1)