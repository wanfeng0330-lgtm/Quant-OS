import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi, CandlestickSeries, HistogramSeries, CandlestickData, HistogramData, Time } from 'lightweight-charts'

interface CandlestickChartProps {
  data: Array<{
    time: string
    open: number
    high: number
    low: number
    close: number
    volume?: number
  }>
  height?: number
  width?: number
  theme?: 'light' | 'dark'
  onCrosshairMove?: (param: any) => void
}

export default function CandlestickChart({
  data,
  height = 400,
  width,
  theme = 'light',
  onCrosshairMove,
}: CandlestickChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: width || chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { color: theme === 'dark' ? '#1f2937' : '#ffffff' },
        textColor: theme === 'dark' ? '#d1d5db' : '#374151',
      },
      grid: {
        vertLines: { color: theme === 'dark' ? '#374151' : '#f3f4f6' },
        horzLines: { color: theme === 'dark' ? '#374151' : '#f3f4f6' },
      },
      crosshair: {
        mode: 0,
        vertLine: {
          width: 1,
          color: theme === 'dark' ? '#6b7280' : '#9ca3af',
          style: 2,
        },
        horzLine: {
          width: 1,
          color: theme === 'dark' ? '#6b7280' : '#9ca3af',
          style: 2,
        },
      },
      rightPriceScale: {
        borderColor: theme === 'dark' ? '#374151' : '#e5e7eb',
      },
      timeScale: {
        borderColor: theme === 'dark' ? '#374151' : '#e5e7eb',
        timeVisible: true,
        secondsVisible: false,
      },
    })

    chartRef.current = chart

    // Add candlestick series
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderDownColor: '#ef4444',
      borderUpColor: '#22c55e',
      wickDownColor: '#ef4444',
      wickUpColor: '#22c55e',
    })

    candlestickSeriesRef.current = candlestickSeries

    // Add volume series
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#3b82f6',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '',
    })
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    })

    volumeSeriesRef.current = volumeSeries

    // Set data
    const candlestickData: CandlestickData[] = data.map((item) => ({
      time: item.time as Time,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    }))

    const volumeData: HistogramData[] = data.map((item) => ({
      time: item.time as Time,
      value: item.volume || 0,
      color: item.close >= item.open ? '#22c55e' : '#ef4444',
    }))

    candlestickSeries.setData(candlestickData)
    volumeSeries.setData(volumeData)

    // Fit content
    chart.timeScale().fitContent()

    // Crosshair move handler
    if (onCrosshairMove) {
      chart.subscribeCrosshairMove(onCrosshairMove)
    }

    // Resize handler
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [data, height, width, theme, onCrosshairMove])

  return (
    <div
      ref={chartContainerRef}
      className="w-full"
      style={{ height: `${height}px` }}
    />
  )
}
