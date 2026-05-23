"""
Portfolio state management — SQLite-backed, manually updated.
Tracks positions, P&L, and position sizing for $200 AUM.
"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, AUM, MAX_POSITION_PCT, NUM_LONGS, NUM_SHORTS

logger = logging.getLogger(__name__)


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            side TEXT NOT NULL,              -- LONG or SHORT
            shares REAL NOT NULL,
            entry_price REAL NOT NULL,
            entry_date TEXT NOT NULL,
            current_price REAL,
            sector TEXT,
            notes TEXT,
            composite_score_at_entry REAL,
            updated_at TEXT,
            closed INTEGER DEFAULT 0,
            close_price REAL,
            close_date TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            total_value REAL,
            cash REAL,
            long_exposure REAL,
            short_exposure REAL,
            gross_exposure REAL,
            net_exposure REAL,
            unrealized_pnl REAL,
            realized_pnl REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS realized_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            side TEXT,
            shares REAL,
            entry_price REAL,
            exit_price REAL,
            entry_date TEXT,
            exit_date TEXT,
            pnl REAL,
            pnl_pct REAL,
            holding_days INTEGER
        )
    """)
    conn.commit()
    conn.close()


def add_position(ticker: str, side: str, shares: float, entry_price: float,
                 sector: str = "", score: float = None, notes: str = "") -> int:
    """Add a new manual trade position."""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        """INSERT INTO portfolio_positions
           (ticker, side, shares, entry_price, entry_date, sector,
            composite_score_at_entry, notes, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (ticker.upper(), side.upper(), shares, entry_price,
         datetime.now().strftime("%Y-%m-%d"),
         sector, score, notes, datetime.now().isoformat())
    )
    conn.commit()
    pos_id = cur.lastrowid
    conn.close()
    logger.info(f"Added {side} position: {shares} shares of {ticker} @ ${entry_price:.2f}")
    return pos_id


def close_position(position_id: int, close_price: float):
    """Mark position as closed and record realized P&L."""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT * FROM portfolio_positions WHERE id=?", (position_id,)
    ).fetchone()
    if not row:
        conn.close()
        return

    cols = [d[0] for d in conn.execute("PRAGMA table_info(portfolio_positions)").fetchall()]
    pos = dict(zip(cols, row))
    side = pos["side"]
    shares = pos["shares"]
    entry = pos["entry_price"]
    entry_date = pos["entry_date"]

    if side == "LONG":
        pnl = (close_price - entry) * shares
    else:  # SHORT
        pnl = (entry - close_price) * shares

    pnl_pct = pnl / (entry * shares)
    entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
    holding_days = (datetime.now() - entry_dt).days

    conn.execute(
        "UPDATE portfolio_positions SET closed=1, close_price=?, close_date=? WHERE id=?",
        (close_price, datetime.now().strftime("%Y-%m-%d"), position_id)
    )
    conn.execute(
        """INSERT INTO realized_trades
           (ticker, side, shares, entry_price, exit_price, entry_date, exit_date, pnl, pnl_pct, holding_days)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (pos["ticker"], side, shares, entry, close_price,
         entry_date, datetime.now().strftime("%Y-%m-%d"),
         pnl, pnl_pct, holding_days)
    )
    conn.commit()
    conn.close()
    logger.info(f"Closed position {position_id}: P&L ${pnl:.2f} ({pnl_pct*100:.1f}%)")


def get_open_positions() -> pd.DataFrame:
    """Return all open positions with live prices refreshed."""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT * FROM portfolio_positions WHERE closed=0 ORDER BY entry_date DESC",
        conn
    )
    conn.close()

    if df.empty:
        return df

    # Refresh current prices
    tickers = df["ticker"].unique().tolist()
    try:
        prices = {}
        for tk in tickers:
            info = yf.Ticker(tk).fast_info
            prices[tk] = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
    except Exception:
        prices = {}

    df["current_price"] = df["ticker"].map(prices)
    df["current_price"] = pd.to_numeric(df["current_price"], errors="coerce")
    df["entry_price"] = pd.to_numeric(df["entry_price"], errors="coerce")
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce")

    df["market_value"] = df["current_price"] * df["shares"]
    df["cost_basis"] = df["entry_price"] * df["shares"]

    df["unrealized_pnl"] = np.where(
        df["side"] == "LONG",
        (df["current_price"] - df["entry_price"]) * df["shares"],
        (df["entry_price"] - df["current_price"]) * df["shares"]
    )
    df["unrealized_pnl_pct"] = df["unrealized_pnl"] / df["cost_basis"]

    return df


def get_portfolio_summary(aum: float = AUM) -> dict:
    """Calculate portfolio-level metrics."""
    pos = get_open_positions()
    realized = get_realized_trades()

    long_positions = pos[pos["side"] == "LONG"] if not pos.empty else pd.DataFrame()
    short_positions = pos[pos["side"] == "SHORT"] if not pos.empty else pd.DataFrame()

    long_exposure = long_positions["market_value"].sum() if not long_positions.empty else 0
    short_exposure = short_positions["market_value"].sum() if not short_positions.empty else 0
    gross = long_exposure + short_exposure
    net = long_exposure - short_exposure
    unrealized_pnl = pos["unrealized_pnl"].sum() if not pos.empty else 0
    realized_pnl = realized["pnl"].sum() if not realized.empty else 0
    total_pnl = unrealized_pnl + realized_pnl
    current_value = aum + total_pnl

    return {
        "aum": aum,
        "current_value": current_value,
        "total_return_pct": (current_value - aum) / aum * 100,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": realized_pnl,
        "total_pnl": total_pnl,
        "long_exposure": long_exposure,
        "short_exposure": short_exposure,
        "gross_exposure": gross,
        "net_exposure": net,
        "num_longs": len(long_positions),
        "num_shorts": len(short_positions),
        "cash": max(0, aum - gross),
    }


def get_realized_trades() -> pd.DataFrame:
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM realized_trades ORDER BY exit_date DESC", conn)
    conn.close()
    return df


def position_size_recommendation(price: float, aum: float = AUM,
                                 score: float = 50, max_pct: float = MAX_POSITION_PCT) -> dict:
    """
    Recommend position size for $200 AUM.
    Higher composite score → larger position (up to max_pct).
    """
    base_pct = max_pct * 0.5  # base 5% for neutral score
    tilt = (score - 50) / 50  # -1 to +1
    position_pct = base_pct + tilt * (max_pct - base_pct)
    position_pct = max(0.02, min(max_pct, position_pct))  # clamp 2%-10%

    dollar_amount = aum * position_pct
    shares = int(dollar_amount / price) if price > 0 else 0
    actual_dollar = shares * price

    return {
        "recommended_pct": position_pct * 100,
        "dollar_amount": dollar_amount,
        "actual_dollar": actual_dollar,
        "shares": shares,
        "price": price,
        "pct_of_aum": actual_dollar / aum * 100,
    }


def update_current_price(position_id: int, price: float):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE portfolio_positions SET current_price=?, updated_at=? WHERE id=?",
        (price, datetime.now().isoformat(), position_id)
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _init_db()
    # Demo: add a test position
    pid = add_position("AAPL", "LONG", 1, 185.0, sector="Technology", score=75)
    print(f"Added position ID: {pid}")
    pos = get_open_positions()
    print(pos[["ticker", "side", "shares", "entry_price", "current_price", "unrealized_pnl"]])
    summary = get_portfolio_summary()
    print(f"\nPortfolio Summary: ${summary['current_value']:.2f} ({summary['total_return_pct']:.1f}% return)")
