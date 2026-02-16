# Event-Driven Trading System

A production-style Python trading system built around a synchronous pub/sub event bus. Features a full pipeline from market data ingestion to order execution, with risk management, portfolio tracking, performance metrics, SQLite persistence, equity curve visualization, and a CLI-driven backtest engine.

## Pipeline

```
MarketDataFeed → Strategy → OrderManager → RiskManager → ExecutionSimulator → PortfolioTracker → Metrics
    (synthetic /                                    ↓                                                ↓
     CSV / yfinance)                         RiskVetoEvent                                    EquityChart
                                           (logged, not executed)
```

Every stage communicates exclusively through events — no direct coupling between components.

## Project Structure

```
Event-Driven-Trading-System/
├── src/
│   └── trading/
│       ├── events/
│       │   └── types.py              # All typed event dataclasses + enums
│       ├── bus/
│       │   └── event_bus.py          # Core pub/sub engine (subscribe / publish / run)
│       ├── market_data/
│       │   ├── feed.py               # Synthetic OHLCV tick generator
│       │   ├── csv_loader.py         # Historical data replay from CSV
│       │   └── yfinance_loader.py    # Real market data from Yahoo Finance
│       ├── signal/
│       │   ├── generator.py          # Random BUY/SELL/HOLD (stub strategy)
│       │   ├── ma_crossover.py       # SMA fast/slow crossover strategy
│       │   └── rsi.py                # RSI overbought/oversold crossover strategy
│       ├── order_manager/
│       │   └── manager.py            # Converts signals to market orders
│       ├── risk/
│       │   └── manager.py            # Position limit + max drawdown checks
│       ├── execution/
│       │   └── simulator.py          # Fills approved orders with slippage
│       ├── portfolio/
│       │   └── tracker.py            # Tracks cash, positions, and P&L
│       ├── metrics/
│       │   └── calculator.py         # Sharpe, drawdown, win rate, total return
│       ├── persistence/
│       │   └── sqlite_writer.py      # Writes all events to SQLite
│       ├── visualization/
│       │   └── chart.py              # Equity curve + drawdown chart (matplotlib)
│       ├── backtest/
│       │   └── engine.py             # Wires full pipeline from config dict
│       └── logger/
│           └── handler.py            # Structured logging for all event types
├── config/
│   └── default.yaml                  # Default run configuration
├── tests/                            # 86 pytest tests (one file per component)
├── main.py                           # CLI entry point
├── pyproject.toml
└── requirements.txt
```

## Event Types

| Event | Description |
|---|---|
| `MarketDataEvent` | OHLCV bar from the feed |
| `SignalEvent` | BUY / SELL / HOLD with strength (0–1) |
| `OrderEvent` | Market order from the order manager |
| `ApprovedOrderEvent` | Order that passed all risk checks |
| `RiskVetoEvent` | Order rejected by the risk manager |
| `FillEvent` | Simulated fill with slippage and commission |
| `PortfolioUpdateEvent` | Position, P&L, cash, and equity snapshot |

All events are **frozen dataclasses** — immutable value objects.

## Design

- **EventBus** — synchronous in-process pub/sub backed by `queue.Queue`. Components call `subscribe(EventType, handler)` and `publish(event)`. The bus is drained by calling `run()`.
- **Component Protocol** — every pipeline stage exposes a single `register(bus)` method for uniform wiring.
- **Risk intercept** — `RiskManager` sits between `OrderManager` and `ExecutionSimulator`. Only `ApprovedOrderEvent`s reach the simulator.
- **Config-driven** — all parameters (symbol, strategy, risk limits, fees) live in `config/default.yaml` and can be overridden via CLI flags.
- **Dependencies** — `pyyaml` for config, `yfinance` for real market data, `matplotlib` for charts.

## Getting Started

**Requirements:** Python 3.11+

```bash
# Install dependencies
pip install -r requirements.txt

# Run with default config (AAPL, 100 ticks, MA crossover)
PYTHONPATH=src python main.py
```

**Windows PowerShell:**
```powershell
$env:PYTHONPATH="src"; python main.py
```

**Windows CMD:**
```cmd
set PYTHONPATH=src && python main.py
```

## CLI Options

```bash
python main.py --symbol MSFT                        # override ticker
python main.py --ticks 500                          # override number of bars (synthetic only)
python main.py --seed 7                             # override random seed
python main.py --strategy rsi                       # switch strategy (ma_crossover | rsi | random)
python main.py --no-db                              # disable SQLite persistence
python main.py --config my.yaml                     # use a custom config file

# Real market data from Yahoo Finance
python main.py --from 2024-01-01 --to 2024-12-31

# Equity curve chart
python main.py --chart                              # show interactive chart after run
python main.py --save-chart curve.png               # save chart to file instead

# Combine flags
python main.py --symbol TSLA --from 2024-01-01 --to 2024-12-31 --strategy rsi --chart
```

## Configuration (`config/default.yaml`)

```yaml
simulation:
  symbol: AAPL
  n_ticks: 100
  seed: 42
  # Uncomment to use real Yahoo Finance data instead of synthetic:
  # data_source: yfinance
  # start: "2024-01-01"
  # end:   "2024-12-31"
  # interval: "1d"

strategy:
  type: ma_crossover   # options: ma_crossover | rsi | random
  fast_period: 5       # MA crossover
  slow_period: 20      # MA crossover
  period: 14           # RSI
  overbought: 70.0     # RSI
  oversold: 30.0       # RSI

order_manager:
  quantity: 100

execution:
  slippage_bps: 1
  commission_per_share: 0.01

risk:
  max_position: 500
  max_drawdown_pct: 10.0

portfolio:
  starting_cash: 100000.0

persistence:
  enabled: true
  db_path: trading.db

visualization:
  enabled: false
  save_path: equity_curve.png   # only used when enabled: true
```

## Strategies

| Strategy | Key | Description |
|---|---|---|
| MA Crossover | `ma_crossover` | BUY when fast SMA crosses above slow SMA; SELL on downward cross |
| RSI | `rsi` | BUY when RSI crosses below oversold (30); SELL when it crosses above overbought (70) |
| Random | `random` | Random BUY/SELL/HOLD — useful for baseline comparison |

## Data Sources

| Source | How to activate | Description |
|---|---|---|
| Synthetic | default | Random walk OHLCV generator — reproducible with `--seed` |
| CSV | `CSVFeed` in code | Replay from a CSV with columns `date,open,high,low,close,volume` |
| Yahoo Finance | `--from` / `--to` flags | Downloads real historical data via `yfinance` |

## Sample Output

```
12:40:50  [MarketData] AAPL @ 2024-01-02T09:30:00  O=150.00 H=150.29 L=149.86 C=150.28 V=889284
12:40:50  [Signal]     AAPL @ 2024-01-02T10:01:00  dir=SELL strength=0.0008
12:40:50  [Order]      AAPL @ 2024-01-02T10:01:00  id=22e1edaa dir=SELL qty=100 price=152.92
12:40:50  [Approved]   AAPL @ 2024-01-02T10:01:00  id=22e1edaa dir=SELL qty=100
12:40:50  [Fill]       AAPL @ 2024-01-02T10:01:00  order=22e1edaa dir=SELL qty=100 price=152.9243 comm=1.00
12:40:50  [Portfolio]  AAPL @ 2024-01-02T10:01:00  pos=-100 avg=0.00 rpnl=15292.43 cash=115291.43 equity=99999.43

Backtest: AAPL  (100 ticks)

============================================
  PERFORMANCE REPORT
============================================
  Total return      : -0.00 %
  Max drawdown      :  0.00 %
  Sharpe ratio      : -1.8675
  Win rate          :  0.0 %
  Total trades      : 2
  Profitable trades : 0
  Final equity      : $99,999.88
============================================
```

## Tests

```
tests/
├── test_event_bus.py           # subscribe, publish, dispatch, ordering
├── test_market_data.py         # tick count, OHLCV constraints, timestamps
├── test_csv_loader.py          # CSV parsing, symbol, OHLCV values
├── test_yfinance_loader.py     # mocked yfinance download, event count, OHLCV values
├── test_signal.py              # random strategy coverage
├── test_ma_crossover.py        # warmup, BUY/SELL crossovers, strength
├── test_rsi_strategy.py        # warmup, oversold/overbought crossovers, strength
├── test_order_manager.py       # BUY/SELL → order, HOLD dropped, price tracking
├── test_execution.py           # fill per order, slippage band, commission
├── test_risk_manager.py        # approve, position veto, drawdown veto
├── test_portfolio_tracker.py   # cash, realized P&L, equity
├── test_metrics.py             # return, drawdown, win rate, Sharpe
├── test_sqlite_writer.py       # tables created, rows inserted per event type
├── test_equity_chart.py        # data collection, save-to-file
└── test_backtest_engine.py     # full pipeline run, report populated
```

```bash
pytest tests/ -v
# 86 passed
```

## License

MIT — see [LICENSE](LICENSE).
