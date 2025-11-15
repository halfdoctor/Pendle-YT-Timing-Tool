# Pendle Market Analysis Tool

This Python script replicates the functionality of the MarketAnalysis.tsx React component and automatically fetches market data from the Pendle protocol to perform comprehensive market analysis with advanced notification caching to prevent duplicate alerts.

## Features

- **Real-time Market Data**: Fetches active markets from Pendle's API
- **Transaction Analysis**: Retrieves and analyzes transaction history for each market
- **YT Price Calculation**: Calculates current Yearn Token (YT) prices using multiple approaches
- **Decline Rate Analysis**: Calculates historical and recent daily decline rates
- **Volume Tracking**: Calculates total USD volume for each market
- **APY Analysis**: Computes average implied APY across transactions
- **Alert System**: Identifies markets where decline rates exceed historical averages
- **Rate Limiting**: Implements proper API rate limiting to avoid abuse
- **Notification Caching**: Prevents duplicate Telegram alerts for 24 hours per market

## Usage

### Basic Usage
```bash
python pendle_market_analysis_optimized.py
```
This will analyze all chains with notification caching enabled (default: 24-hour cache)

### Specify Chain
```bash
python pendle_market_analysis_optimized.py <chain_id>
```

### Analyze All Chains
```bash
python pendle_market_analysis_optimized.py all
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
python pendle_market_analysis_optimized.py 1

# Analyze Arbitrum
python pendle_market_analysis_optimized.py 42161

# Analyze Optimism
python pendle_market_analysis_optimized.py 10

# Analyze all chains
python pendle_market_analysis_optimized.py all
```

## Notification Caching System

The notification caching system prevents duplicate Telegram alerts for the same market within a configurable time period, significantly reducing notification spam and providing a more manageable alert experience.

### How It Works

#### Cache Mechanism
- When a market alert is successfully sent via Telegram, the market address and chain ID are cached with a timestamp
- The cache persists across script runs using a JSON file (`notification_cache.json`)
- Each cached entry includes:
  - Market address and chain ID
  - Market name
  - Timestamp when notification was sent
  - Cache duration (24 hours by default)

#### Cache Duration
- **Default**: 24 hours
- **Configurable**: Can be adjusted by passing `cache_duration_hours` parameter
- **Behavior**: After 24 hours, the market becomes eligible for notification again

#### Cache Management
- **Automatic cleanup**: Expired cache entries are automatically removed
- **Manual clearing**: Cache can be cleared using `clear_cache()` method
- **Statistics**: Cache status and statistics are displayed on startup

### Custom Cache Duration

The cache duration can be customized programmatically:

```python
# 12-hour cache
orchestrator = AnalysisOrchestrator(chain_id=1, cache_duration_hours=12)

# 48-hour cache
notifier = Notifier(chain_id=1, chain_name="Ethereum", cache_duration_hours=48)
```

### Cache File Structure

The cache is stored in `notification_cache.json` with the following structure:

```json
{
  "1:0x1234567890abcdef": {
    "market_address": "0x1234567890abcdef",
    "chain_id": 1,
    "market_name": "Example Market",
    "timestamp": "2025-11-15T16:30:00Z",
    "cache_duration_hours": 24
  },
  "137:0xabcdef1234567890": {
    "market_address": "0xabcdef1234567890",
    "chain_id": 137,
    "market_name": "Polygon Market",
    "timestamp": "2025-11-15T16:35:00Z",
    "cache_duration_hours": 24
  }
}
```

### Logging and Monitoring

#### Startup Messages
```
💾 Notification cache: 3 active, 1 expired entries
```

#### During Analysis
```
📱 Skipping 2 markets due to 24h notification cache
   ⏭️ Example Market (cached)
   ⏭️ Another Market (cached)
   ... and 0 more

📱 Sending Telegram alerts for 1 new alert markets...
💾 Cached 1 notifications for 24 hours
✅ Telegram alerts sent successfully for 1 markets!
🧹 Cleaned up 1 expired cache entries
```

#### Cache Information
Access cache information programmatically:

```python
notifier = Notifier(chain_id=1)
print(notifier.get_cache_info())
```

### Benefits of Notification Caching

1. **Reduced Notification Spam**: Same market won't trigger alerts repeatedly
2. **Better User Experience**: Users receive meaningful alerts instead of duplicates
3. **API Efficiency**: Reduces unnecessary Telegram API calls
4. **Persistent State**: Cache survives script restarts
5. **Configurable**: Adjustable cache duration for different use cases
6. **Transparent**: Clear logging shows which markets are cached/skipped

## Modular Architecture

The tool has been refactored from a monolithic 766-line file into a clean modular structure for better maintainability and testability.

### File Structure

```
pendle_market_analysis/
├── __init__.py           # Package initialization and exports
├── models.py             # Data structures and exceptions
├── api_client.py         # API interaction layer
├── analyzer.py           # Core analysis logic
├── notifier.py           # Output formatting and notifications
├── orchestrator.py       # Workflow coordination
└── main.py              # CLI entry points

pendle_market_analysis_optimized.py  # Backward compatibility wrapper
```

### Component Details

#### `models.py`
- **Market**, **Transaction**, **DeclineRateAnalysis** data structures
- **PendleApiError**, **AnalysisError**, **NotificationError** exceptions

#### `api_client.py`
- **PendleAPIClient**: Handles all HTTP interactions
- Market fetching, transaction retrieval with retry logic

#### `analyzer.py`
- **PendleAnalyzer**: Core calculation logic
- Decline rate calculations, volume analysis, APY computations

#### `notifier.py`
- **Notifier**: Output formatting and notifications
- Console output, Telegram alerts, result presentation
- **NotificationCache**: Handles notification deduplication

#### `orchestrator.py`
- **AnalysisOrchestrator**: Coordinates the workflow
- **MultiChainAnalysisOrchestrator**: Handles multi-chain analysis

### New Modular Usage

```python
from pendle_market_analysis import AnalysisOrchestrator, PendleAnalyzer

# Single chain analysis
orchestrator = AnalysisOrchestrator(chain_id=1, cache_duration_hours=24)
await orchestrator.run_analysis()

# Using individual components
from pendle_market_analysis import PendleAnalyzer
analyzer = PendleAnalyzer()
result = analyzer.analyze_market(market, transactions)
```

### CLI Usage

```bash
# Using the new modular CLI
python -m pendle_market_analysis.main 1          # Analyze Ethereum only
python -m pendle_market_analysis.main all        # Analyze all chains

# Using the backward compatibility wrapper
python pendle_market_analysis_optimized.py 1
python pendle_market_analysis_optimized.py all
```

### Backward Compatibility

The original interface continues to work exactly as before:

```python
from pendle_market_analysis_optimized import OptimizedPendleAnalyzer

analyzer = OptimizedPendleAnalyzer(chain_id=1)
await analyzer.run_optimized_analysis()
```

## Automation & Deployment

For production deployment and automated scheduling:

### Cron Job Setup

Add to your crontab for automated execution:

```bash
# Edit crontab
crontab -e

# Add this line to run every hour
0 * * * * /path/to/run_pendle.sh
```

### Deployment Script

Use the provided `run_pendle.sh` script for automated execution:

```bash
# Make executable
chmod +x run_pendle.sh

# Run manually
./run_pendle.sh

# Or with cron (already configured in the script)
# * * * * * /path/to/run_pendle.sh
```

### Environment Setup

The script includes automatic environment setup:
- Virtual environment activation
- Log file creation with timestamps
- Error logging to `pendle.log`

### Telegram Configuration

Configure Telegram notifications by setting environment variables in a `.env` file:

```bash
# .env file
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
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
Markets with abnormal decline rates (exceeding historical averages) are highlighted with warnings and trigger Telegram notifications (with caching to prevent duplicates).

## Dependencies

Install required dependencies:
```bash
pip install -r requirements.txt
```

Required packages:
- `aiohttp>=3.8.0` - For async HTTP requests
- `python-dotenv>=0.19.0` - For environment variable management

## API Integration

The script integrates with Pendle's API:

- **Active Markets**: `https://api-v2.pendle.finance/core/v1/{chainId}/markets/active`
- **Transactions**: `https://api-v2.pendle.finance/core/v4/{chainId}/transactions`

### API Features
- **Retry Logic**: Built-in retry with 160ms + random delay between requests
- **Pagination**: Hybrid approach using `skip` and `resumeToken`
- **Deduplication**: Client-side deduplication by transaction ID
- **Rate Limiting**: Caps at 8 pages (~8000 records) per market

## Rate Limiting

- 5-second delays between market analysis batches
- 160ms + random jitter between transaction page requests
- Caps at 8 pages (~8000 transactions) per market to prevent API abuse
- Client-side deduplication of transactions by ID
- Automatic backoff on API errors

## Error Handling

- **Graceful Degradation**: Continues analysis even if individual markets fail
- **Detailed Logging**: Provides comprehensive error messages and debugging info
- **Timezone Awareness**: Proper datetime handling for accurate rate calculations
- **Custom Exceptions**: Specific error types for different failure modes
- **Cache Resilience**: Handles cache file corruption gracefully

## Configuration Options

### Environment Variables

**Required for Telegram notifications:**
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Target chat ID for notifications

**Cache Configuration:**
- Cache duration configurable via code parameters
- Cache file location: `notification_cache.json` (current directory)

### Performance Settings

- **Concurrent Markets**: 2 simultaneous market analyses
- **Batch Size**: Configurable via `MARKETS_TO_ANALYZE`
- **Timeout**: 300 seconds total request timeout

## Troubleshooting

### Cache Issues

#### Cache Not Working
1. Check file permissions for cache directory
2. Verify Telegram configuration is correct
3. Ensure cache file path is writable

#### Notifications Still Duplicate
1. Check cache duration setting
2. Clear cache manually: `notifier.clear_cache()`
3. Verify market addresses are consistent

#### Cache File Issues
1. Delete `notification_cache.json` to reset
2. Check for file corruption or invalid JSON
3. Verify sufficient disk space

### API Issues

#### Rate Limiting
- Reduce concurrent markets if hitting limits
- Increase delays between requests
- Check Pendle API status

#### Network Errors
- Verify internet connectivity
- Check firewall/proxy settings
- Review API endpoint accessibility

## Performance Impact

### Notification Cache
- **Minimal**: Cache operations are fast JSON read/write
- **Memory**: Small memory footprint (one entry per alerted market)
- **Disk**: Negligible disk space usage
- **Startup**: Minor delay for cache loading (usually <100ms)

### Overall Performance
- **Concurrent Processing**: Analyzes multiple markets simultaneously
- **Smart Data Limiting**: Early termination for stale markets
- **Optimized Requests**: Efficient API request patterns
- **Memory Efficient**: Streams large transaction datasets

## Testing

All components have been tested for import compatibility:

```bash
# Test imports
python -c "from pendle_market_analysis.models import Market, Transaction, PendleApiError; print('✅ Models import successful')"
python -c "from pendle_market_analysis.analyzer import PendleAnalyzer; print('✅ All core components import successful')"

# Test backward compatibility
python -c "from pendle_market_analysis_optimized import OptimizedPendleAnalyzer; print('✅ Backward compatibility wrapper works')"

# Test notification cache
python demo_notification_cache.py
```

## Future Enhancements

Potential improvements for future versions:
- Multiple cache duration tiers based on market importance
- Cache analytics and reporting
- Advanced cache invalidation rules
- Integration with external cache systems (Redis)
- Cache warming for frequently analyzed markets
- Webhook support for real-time notifications
- Database storage for historical analysis
- Machine learning-based alert thresholds

This tool provides the same functionality as the original TypeScript React component but in a standalone Python script that can be run from the command line for automated market analysis with intelligent notification management.
