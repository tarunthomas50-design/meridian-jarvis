"""
Meridian Capital Partners — Global Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH = CACHE_DIR / "meridian.db"

CACHE_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Universe ──────────────────────────────────────────────────────────────────
BENCHMARK_TICKERS = [
    "SPY", "QQQ", "IWM", "DIA",
    "XLK", "XLF", "XLV", "XLE", "XLI", "XLC", "XLY", "XLP", "XLB", "XLRE", "XLU",
    "^VIX", "TLT", "HYG",
]

# ── Portfolio ─────────────────────────────────────────────────────────────────
AUM = 200.0           # Starting capital in USD
NUM_LONGS = 10        # Target number of long positions
NUM_SHORTS = 5        # Target short positions (for small account — fewer)
MAX_POSITION_PCT = 0.10   # Max 10% per position (~$20 max)
MAX_SECTOR_PCT = 0.30     # Max 30% per sector
GROSS_EXPOSURE = 1.50     # 150% gross
NET_EXPOSURE_RANGE = (0.0, 0.10)  # 0–10% net

# ── Scoring weights (default = normal regime) ─────────────────────────────────
FACTOR_WEIGHTS = {
    "momentum":     0.20,
    "quality":      0.20,
    "value":        0.15,
    "revisions":    0.15,
    "insider":      0.10,
    "growth":       0.10,
    "short_interest": 0.05,
    "institutional":  0.05,
}

# Regime-conditional weights
REGIME_WEIGHTS = {
    "low_vol":   {"momentum": 0.28, "quality": 0.20, "value": 0.10, "revisions": 0.15,
                  "insider": 0.10, "growth": 0.10, "short_interest": 0.04, "institutional": 0.03},
    "normal":    FACTOR_WEIGHTS,
    "high_vol":  {"momentum": 0.10, "quality": 0.28, "value": 0.22, "revisions": 0.15,
                  "insider": 0.10, "growth": 0.08, "short_interest": 0.04, "institutional": 0.03},
}

VIX_LOW = 15
VIX_HIGH = 25

# ── Risk limits ───────────────────────────────────────────────────────────────
MAX_BETA = 0.20
CIRCUIT_BREAKER_DAILY = 0.015    # 1.5%  → SIZE_DOWN 30%
CIRCUIT_BREAKER_DAILY_HARD = 0.025  # 2.5% → CLOSE_ALL_TODAY
CIRCUIT_BREAKER_WEEKLY = 0.04    # 4%   → SIZE_DOWN 30%
CIRCUIT_BREAKER_DRAWDOWN = 0.08  # 8%   → KILL_SWITCH

# ── SEC EDGAR ─────────────────────────────────────────────────────────────────
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Meridian Capital tarunthomas50@gmail.com")
SEC_RATE_LIMIT = 8   # requests per second

# ── Misc ──────────────────────────────────────────────────────────────────────
LOOKBACK_DAYS = 365 * 3    # 3-year price history
MOMENTUM_LOOKBACK = 252    # 12-month momentum
BETA_LOOKBACK = 60
COV_LOOKBACK = 120
