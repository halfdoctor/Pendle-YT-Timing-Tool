# Pendle Market Analysis Tool

This Python script replicates the functionality of the MarketAnalysis.tsx React component and automatically fetches market data from the Pendle protocol to perform comprehensive market analysis.

## Features

- **Real-time Market Data**: Fetches active markets from Pendle's API
- **Transaction Analysis**: Retrieves and analyzes transaction history for each market
- **YT Price Calculation**: Calculates current Yearn Token (YT) prices using multiple approaches
- **Decline Rate Analysis**: Calculates historical and recent daily decline rates
- **Volume Tracking**: Calculates total USD volume for each market
- **APY Analysis**: Computes average implied APY across transactions
- **Alert System**: Identifies markets where decline rates exceed historical averages
- **Rate Limiting**: Implements proper API rate limiting to avoid abuse

## Usage

### Basic Usage
```bash
python pendle_market_analysis.py
```
This will analyze Ethereum markets (default chain ID: 1)

### Specify Chain
```bash
python pendle_market_analysis.py <chain_id>
```

### Supported Chains
- `1`: Ethereum (default)
- `42161`: Arbitrum One
- `10`: Optimism
- `56`: BNB Smart Chain
- `5000`: Mantle
- `8453`: Base
- `999`: Hyper EVM

### Examples
```bash
# Analyze Ethereum
python pendle_market_analysis.py 1

# Analyze Arbitrum
python pendle_market_analysis.py 42161

# Analyze Optimism
python pendle_market_analysis.py 10
```

## Output

The script provides comprehensive analysis results:

### Summary Table
- Market names and addresses
- Current YT prices
- Decline rates (with alerts for abnormal markets)
- Trading volume in USD
- Implied APY percentages
- Maturity dates

### Statistics
- Total active markets on the chain
- Markets successfully analyzed
- Total trading volume
- Average YT price across markets
- Count of stable vs alert markets

### Alert System
Markets with abnormal decline rates (exceeding historical averages) are highlighted with warnings.

## Dependencies

Install required dependencies:
```bash
pip install -r requirements.txt
```

Required packages:
- `aiohttp>=3.8.0` - For async HTTP requests

## API Integration

The script integrates with Pendle's API:

- **Active Markets**: `https://api-v2.pendle.finance/core/v1/{chainId}/markets/active`
- **Transactions**: `https://api-v2.pendle.finance/core/v4/{chainId}/transactions`

## Rate Limiting

- 9-second delays between market analysis requests
- 160ms + random jitter between transaction page requests
- Caps at 8 pages (~8000 transactions) per market to prevent API abuse
- Client-side deduplication of transactions by ID

## Error Handling

- Graceful handling of API failures
- Continues analysis even if individual markets fail
- Provides detailed error messages and sample transaction debugging
- Timezone-aware datetime handling for accurate rate calculations

## File Structure

```
pendle_market_analysis.py    # Main analysis script
requirements.txt             # Python dependencies
README.md                    # This documentation
```

## Key Components

### Data Structures
- `Market`: Market information (name, address, expiry, etc.)
- `Transaction`: Transaction data (timestamp, APY, volume, etc.)
- `MarketAnalysisData`: Analysis results for each market

### Analysis Functions
- `calculate_current_yt_price()`: Multi-approach YT price calculation
- `calculate_volume_usd()`: Total USD volume calculation
- `calculate_average_implied_apy()`: Average APY across transactions
- `calculate_decline_rates()`: Historical and daily decline rate analysis

### Output Formatting
- Clean console output with emojis and formatted tables
- Progress indicators during analysis
- Comprehensive summary statistics
- Alert highlighting for abnormal markets

This tool provides the same functionality as the original TypeScript React component but in a standalone Python script that can be run from the command line for automated market analysis.
