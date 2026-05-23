# Meridian Capital Partners — JARVIS Dashboard
## Setup & Deployment Guide

---

## 🏃 Run Locally (5 minutes)

### 1. Install Python 3.11+
Download from python.org if not installed.

### 2. Install dependencies
```bash
cd "ls_equity_fund"
pip install -r requirements.txt
```

### 3. Run the dashboard
```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## 📱 Deploy to Render (Free — accessible from mobile anywhere)

### Step 1: Push to GitHub
1. Create a free GitHub account at github.com
2. Create a new repository called `meridian-jarvis`
3. Upload the `ls_equity_fund` folder contents to the repo

### Step 2: Deploy on Render
1. Go to https://render.com and sign up free
2. Click **New → Web Service**
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` — click **Deploy**
5. Wait ~5 minutes for build

### Step 3: Access on mobile
- Render gives you a URL like `https://meridian-jarvis.onrender.com`
- Open this on any phone browser — bookmark it!
- The dark theme is mobile-optimized

**Note:** Free Render tier sleeps after 15 min inactivity.
First load takes ~30s to wake up. Upgrade to Starter ($7/mo) for always-on.

---

## 📊 How to Use the Dashboard

### Page I — Portfolio
- See all open positions with live P&L
- View realized trade history and win rate
- Close positions by ID

### Page II — Screener
- Click **🔄 Refresh Scores** to score S&P 500 stocks (takes 3-5 min first run)
- Filter by signal (LONG/SHORT) and sector
- Top 5 long/short candidates shown at bottom

### Page III — Risk
- Circuit breaker status (daily loss, drawdown, VIX)
- Position sizing rules for your $200 account
- Tail risk alerts

### Page IV — Market
- Live index performance (SPY, QQQ, IWM, VIX)
- Sector heatmap
- Price chart with 50-day MA for any ticker
- Quick fundamentals lookup

### Page V — Add Trade
- Log any trade you've executed through your broker
- Position size calculator — enter ticker + conviction → get recommended shares
- Earnings date checker

---

## 💡 Trading Workflow (Manual)

1. **Morning**: Check Page IV (Market) for regime + sector strength
2. **Screener**: Check Page II for top LONG/SHORT signals
3. **Risk Check**: Use Page III checklist before any trade
4. **Size**: Use Page V calculator to size position for $200 AUM
5. **Execute**: Place trade in your broker app
6. **Log**: Use Page V → "Log a Manual Trade" to track in JARVIS
7. **Monitor**: Page I shows live P&L on all positions

---

## ⚙️ Configuration

Edit `config.py` to adjust:
- `AUM = 200.0` → your starting capital
- `NUM_LONGS = 10` → target long positions
- `MAX_POSITION_PCT = 0.10` → max 10% per trade
- `FACTOR_WEIGHTS` → change factor weightings

---

## 🔄 Data Refresh Schedule

Recommended manual refresh cadence:
- **Daily**: Click "Refresh Scores" on Screener page
- **Weekly**: Universe auto-refreshes from Wikipedia
- **On-demand**: Fundamentals fetch on Screener page

All data stored locally in `cache/meridian.db` (SQLite).

---

## ⚠️ Disclaimer

This is an educational tool for learning quantitative investing concepts.
Not financial advice. Always do your own research before trading.
With $200, focus on learning the system — don't risk money you can't afford to lose.
