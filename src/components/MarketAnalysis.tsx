import { useState, Suspense, lazy } from 'react';
import { useTranslation } from 'react-i18next';
import { chainsArray } from '../constant/chain';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select';
import { Button } from './ui/button';
import Container from './Container';

import { getActiveMarkets, getTransactionsAll } from '@/api/pendle';
import type { Market } from '@/api/pendle';

interface MarketAnalysisData {
    market: Market;
    currentYTPrice: number;
    averageDeclineRate: number;
    latestDailyDeclineRate: number;
    declineRateExceedsAverage: boolean;
    volumeUSD: number;
    impliedApy: number;
}

interface ChartDataPoint {
    time: number;
    ytPrice: number | null;
    points: number | null;
    fairValue: number;
}

const Chart = lazy(async () => ({ default: (await import('./Chart')).Chart }));

export function MarketAnalysis() {
    const { t } = useTranslation();
    const [selectedChain, setSelectedChain] = useState<string>(chainsArray[0]?.chainId.toString() || "1");
    const [marketAnalysis, setMarketAnalysis] = useState<MarketAnalysisData[]>([]);
    const [activeMarketsCount, setActiveMarketsCount] = useState<number>(0);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [selectedMarketForChart, setSelectedMarketForChart] = useState<MarketAnalysisData | null>(null);
    const [chartData, setChartData] = useState<ChartDataPoint[]>([]);

    const handleChainChange = (value: string) => {
        setSelectedChain(value);
        setMarketAnalysis([]);
        setActiveMarketsCount(0);
        setSelectedMarketForChart(null);
        setChartData([]);
    };

    const fetchMarkets = async () => {
        setIsLoading(true);
        try {
            const activeMarkets = await getActiveMarkets(parseInt(selectedChain));
            // Set the total count of active markets for the selected chain
            setActiveMarketsCount(activeMarkets.length);
            
            // Take first 5 markets
            const marketsToAnalyze = activeMarkets.slice(0, 10);

            // Process markets sequentially to avoid rate limiting
            const analysisResults: MarketAnalysisData[] = [];
            
            for (let i = 0; i < marketsToAnalyze.length; i++) {
                const market = marketsToAnalyze[i];
                try {
                    console.log(`Analyzing market ${i + 1}/${marketsToAnalyze.length}: ${market.name}`);
                    
                    const transactions = await getTransactionsAll(selectedChain, market.address.toString());
                    
                    // Debug: Log sample transaction structure
                    if (transactions.length > 0) {
                        console.log(`Sample transaction for ${market.name}:`, {
                            action: transactions[0].action,
                            value: transactions[0].value,
                            impliedApy: transactions[0].impliedApy,
                            timestamp: transactions[0].timestamp
                        });
                    }
                    
                    // Calculate current YT price using multiple approaches
                    let currentYTPrice = 0;
                    
                    // Approach 1: Direct YT transactions with value
                    const ytTransactions = transactions.filter(tx =>
                        tx.action && (tx.action.includes('SWAP_YT') || tx.action.includes('SWAP_PY'))
                    );
                    
                    if (ytTransactions.length > 0) {
                        const latestYtTx = ytTransactions
                            .filter(tx => tx.value !== null && tx.value !== undefined && tx.value > 0)
                            .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0];
                        
                        if (latestYtTx && latestYtTx.value) {
                            currentYTPrice = latestYtTx.value;
                        }
                    }
                    
                    // Approach 2: Any transaction with reasonable YT price value
                    if (currentYTPrice === 0) {
                        const priceTransactions = transactions
                            .filter(tx => tx.value !== null && tx.value !== undefined && tx.value > 0.001 && tx.value < 5)
                            .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
                        
                        if (priceTransactions.length > 0) {
                            currentYTPrice = priceTransactions[0].value || 0;
                        }
                    }
                    
                    // Approach 3: Calculate from implied APY if still no price
                    if (currentYTPrice === 0 && transactions.length > 0) {
                        const recentApyTx = transactions
                            .filter(tx => tx.impliedApy !== undefined && tx.impliedApy !== null && tx.impliedApy > 0)
                            .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0];
                        
                        if (recentApyTx && recentApyTx.impliedApy !== undefined) {
                            // Simple YT price estimation based on implied APY
                            // This is a rough calculation - YT price = 1 / (1 + APY)^time_to_maturity
                            const timeToMaturityYears = Math.max(0.1, (new Date(market.expiry).getTime() - Date.now()) / (1000 * 60 * 60 * 24 * 365));
                            currentYTPrice = 1 / Math.pow(1 + recentApyTx.impliedApy, timeToMaturityYears);
                        }
                    }
                    
                    console.log(`Final YT price for ${market.name}: ${currentYTPrice.toFixed(6)}`);

                    // Calculate volume and average APY
                    const volumeUSD = transactions.reduce((sum, tx) =>
                        sum + (tx.valuation?.usd || tx.valuation_usd || 0), 0
                    );
                    
                    const impliedApyValues = transactions
                        .filter(tx => tx.impliedApy !== undefined && tx.impliedApy !== null)
                        .map(tx => tx.impliedApy!);
                    
                    const averageImpliedApy = impliedApyValues.length > 0
                        ? impliedApyValues.reduce((sum, apy) => sum + apy, 0) / impliedApyValues.length
                        : 0;

                    // Calculate historic YT price decline rate using implied APY changes
                    let averageDeclineRate = 0;
                    const impliedApyTransactions = transactions
                        .filter(tx => tx.impliedApy !== undefined && tx.impliedApy !== null && tx.timestamp)
                        .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
                    
                    if (impliedApyTransactions.length > 1) {
                        const timeSpan = (new Date(impliedApyTransactions[impliedApyTransactions.length - 1].timestamp).getTime()
                            - new Date(impliedApyTransactions[0].timestamp).getTime()) / (1000 * 60 * 60 * 24); // Convert to days
                        
                        if (timeSpan > 0) {
                            // Calculate rate of change in implied APY (which correlates with YT price)
                            const apyChange = impliedApyTransactions[impliedApyTransactions.length - 1].impliedApy! - impliedApyTransactions[0].impliedApy!;
                            averageDeclineRate = (apyChange / timeSpan) * 100; // Percentage change per day
                        }
                    }
                    
                    // If we have very few transactions, use a simpler calculation
                    if (averageDeclineRate === 0 && transactions.length > 0) {
                        const recentTxs = transactions.slice(-5); // Last 5 transactions
                        if (recentTxs.length >= 2) {
                            const recentApy = recentTxs.filter(tx => tx.impliedApy !== undefined && tx.impliedApy !== null)
                                .map(tx => tx.impliedApy!);
                            if (recentApy.length >= 2) {
                                const apyDiff = recentApy[recentApy.length - 1] - recentApy[0];
                                averageDeclineRate = apyDiff * 100; // Simple percentage change
                            }
                        }
                    }

                    // Calculate latest daily decline rate (last 24 hours)
                    let latestDailyDeclineRate = 0;
                    const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);
                    const recentTransactions = transactions
                        .filter(tx => tx.impliedApy !== undefined && tx.impliedApy !== null && new Date(tx.timestamp).getTime() >= oneDayAgo)
                        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
                    
                    if (recentTransactions.length >= 2) {
                        const latestApy = recentTransactions[0].impliedApy!;
                        const previousApy = recentTransactions[recentTransactions.length - 1].impliedApy!;
                        const timeDiffHours = (new Date(recentTransactions[0].timestamp).getTime() - new Date(recentTransactions[recentTransactions.length - 1].timestamp).getTime()) / (1000 * 60 * 60);
                        if (timeDiffHours > 0) {
                            latestDailyDeclineRate = ((latestApy - previousApy) / timeDiffHours) * 24; // Extrapolate to daily rate
                        }
                    }

                    // Check if latest decline rate exceeds average by more than 50%
                    const declineRateExceedsAverage = Math.abs(latestDailyDeclineRate) > Math.abs(averageDeclineRate) * 1.00001;

                    analysisResults.push({
                        market,
                        currentYTPrice,
                        averageDeclineRate,
                        latestDailyDeclineRate,
                        declineRateExceedsAverage,
                        volumeUSD,
                        impliedApy: averageImpliedApy
                    });
                    
                    // Add delay between requests to respect rate limits
                    if (i < marketsToAnalyze.length - 1) {
                        await new Promise(resolve => setTimeout(resolve, 9000)); // 9 second delay
                    }
                    
                } catch (error) {
                    console.warn(`Failed to analyze market ${market.name}:`, error);
                    // Add market with zero values instead of skipping
                    analysisResults.push({
                        market,
                        currentYTPrice: 0,
                        averageDeclineRate: 0,
                        latestDailyDeclineRate: 0,
                        declineRateExceedsAverage: false,
                        volumeUSD: 0,
                        impliedApy: 0
                    });
                }
            }

            setMarketAnalysis(analysisResults);

        } catch (error) {
            console.error('Failed to fetch markets:', error);
            setActiveMarketsCount(0);
        } finally {
            setIsLoading(false);
        }
    };

    const loadMarketChart = async (marketData: MarketAnalysisData) => {
        setSelectedMarketForChart(marketData);
        setIsLoading(true);
        
        try {
            const transactions = await getTransactionsAll(selectedChain, marketData.market.address.toString());
            
            // Create chart data from transactions
            const chartData = transactions
                .filter(tx => tx.impliedApy !== undefined)
                .map(tx => ({
                    time: new Date(tx.timestamp).getTime(),
                    ytPrice: tx.value || 0,
                    points: null,
                    fairValue: (tx.impliedApy || 0) * 100
                }))
                .sort((a, b) => a.time - b.time);
                
            setChartData(chartData);
        } catch (error) {
            console.error('Failed to load market chart:', error);
            setChartData([]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Container className='pt-4 sm:pt-6 space-y-8'>
            {/* Header Section */}
            <div className='bg-card card-elevated rounded-xl p-4 sm:p-6 bg-gradient-to-br from-card to-card/80'>
                <div className='flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between'>
                    <div>
                        <h2 className="text-2xl font-bold mb-2">{t('analysis.title')}</h2>
                        <p className="text-muted-foreground">
                            {t('analysis.description')}
                        </p>
                    </div>
                    
                    <div className='flex gap-4 items-center'>
                        <div className='flex flex-col space-y-2 w-full sm:w-auto'>
                            <label className='text-sm font-medium text-muted-foreground whitespace-nowrap'>
                                {t('main.chain')}
                            </label>
                            <Select value={selectedChain} onValueChange={handleChainChange}>
                                <SelectTrigger className="w-full sm:w-[200px] input-enhanced">
                                    <SelectValue placeholder={t('main.selectChain')} />
                                </SelectTrigger>
                                <SelectContent>
                                    {chainsArray.map((chain) => (
                                        <SelectItem key={chain.chainId} value={chain.chainId.toString()}>
                                            {chain.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        
                        <Button
                            onClick={fetchMarkets}
                            disabled={isLoading}
                            className="input-enhanced mt-6 sm:mt-0">
                            {isLoading ? t('common.loading') : t('analysis.analyzeMarkets')}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Active Markets Count */}
            {activeMarketsCount > 0 && (
                <div className='bg-card card-elevated rounded-xl p-4 sm:p-6 bg-gradient-to-br from-green-50 to-green-100 border border-green-200'>
                    <div className='flex items-center gap-3'>
                        <div className='flex items-center justify-center w-10 h-10 bg-green-200 rounded-full'>
                            <svg className="w-5 h-5 text-green-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                            </svg>
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold text-green-800">
                                {activeMarketsCount} Active Markets
                            </h3>
                            <p className="text-sm text-green-600">
                                Currently available on {chainsArray.find(chain => chain.chainId.toString() === selectedChain)?.name || 'Selected Chain'}
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Loading Indicator */}
            {isLoading && (
                <div className="text-center">
                    <div className="inline-flex items-center gap-2 text-muted-foreground bg-muted/30 px-4 py-2 rounded-lg border border-border/40">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                        <span>{t('analysis.analyzingMarkets')}</span>
                    </div>
                </div>
            )}

            {/* Market Analysis Results */}
            {marketAnalysis.length > 0 && (
                <div className='bg-card card-elevated rounded-xl p-4 sm:p-6 bg-gradient-to-br from-card to-card/80'>
                    <h3 className="text-xl font-semibold mb-4">{t('analysis.marketResults')}</h3>
                    
                    <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'>
                        {marketAnalysis.map((analysis) => (
                            <div
                                key={analysis.market.address}
                                className='bg-muted/50 card-subtle p-4 rounded-lg cursor-pointer hover:bg-muted/70 transition-colors'
                                onClick={() => loadMarketChart(analysis)}
                            >
                                <div className='space-y-3'>
                                    <div className='font-medium text-sm truncate' title={analysis.market.name}>
                                        {analysis.market.name}
                                    </div>
                                    
                                    <div className='grid grid-cols-2 gap-2 text-xs'>
                                        <div className='text-muted-foreground'>
                                            {t('analysis.currentYTPrice')}
                                        </div>
                                        <div className='font-medium text-right'>
                                            {analysis.currentYTPrice > 0 ? analysis.currentYTPrice.toFixed(4) : 'N/A'}
                                        </div>
                                        
                                        <div className='text-muted-foreground'>
                                            {t('analysis.declineRate')}
                                        </div>
                                        <div className={`font-medium text-right ${analysis.declineRateExceedsAverage ? 'bg-red-100 text-red-800 px-2 py-1 rounded border border-red-300' : (Math.abs(analysis.averageDeclineRate) > 0.01 ? (analysis.averageDeclineRate < 0 ? 'text-red-500' : 'text-green-500') : 'text-muted-foreground')}`}>
                                            {analysis.declineRateExceedsAverage ? (
                                                <span className="flex items-center gap-1">
                                                    ⚠️ {Math.abs(analysis.latestDailyDeclineRate).toFixed(2)}% / day
                                                </span>
                                            ) : Math.abs(analysis.averageDeclineRate) > 0.01 ? `${analysis.averageDeclineRate.toFixed(2)}% / day` : 'Stable'}
                                        </div>
                                        
                                        {analysis.declineRateExceedsAverage && (
                                            <>
                                                <div className='text-muted-foreground text-xs'>
                                                    Latest vs Average
                                                </div>
                                                <div className='font-medium text-right text-xs text-red-600'>
                                                    {Math.abs(analysis.latestDailyDeclineRate).toFixed(2)}% vs {Math.abs(analysis.averageDeclineRate).toFixed(2)}%
                                                </div>
                                            </>
                                        )}
                                        
                                        <div className='text-muted-foreground'>
                                            {t('analysis.volume')}
                                        </div>
                                        <div className='font-medium text-right'>
                                            ${analysis.volumeUSD > 0 ? analysis.volumeUSD.toLocaleString(undefined, { maximumFractionDigits: 0 }) : 'N/A'}
                                        </div>
                                        
                                        <div className='text-muted-foreground'>
                                            {t('analysis.impliedApy')}
                                        </div>
                                        <div className='font-medium text-right'>
                                            {analysis.impliedApy > 0 ? `${(analysis.impliedApy * 100).toFixed(2)}%` : 'N/A'}
                                        </div>
                                        
                                        <div className='text-muted-foreground'>
                                            {t('analysis.maturity')}
                                        </div>
                                        <div className='font-medium text-right'>
                                            {new Date(analysis.market.expiry).toLocaleDateString()}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Chart Display */}
            {selectedMarketForChart && chartData.length > 0 && (
                <div className='bg-card card-elevated rounded-xl p-4 sm:p-6 bg-gradient-to-br from-card to-card/80'>
                    <h3 className="text-xl font-semibold mb-4">
                        {t('analysis.chartTitle')} - {selectedMarketForChart.market.name}
                    </h3>
                    
                    <Suspense fallback={
                        <div className="flex items-center justify-center h-64 text-muted-foreground">
                            {t('common.loading')}
                        </div>
                    }>
                        <Chart
                            data={chartData}
                            marketName={selectedMarketForChart.market.name}
                            underlyingAmount={1000}
                            chainName={chainsArray.find(chain => chain.chainId.toString() === selectedChain)?.name || t('common.unknown')}
                            maturityDate={new Date(selectedMarketForChart.market.expiry)}
                        />
                    </Suspense>
                </div>
            )}
        </Container>
    );
}