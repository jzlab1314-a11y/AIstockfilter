# 📈 量化股票篩選器與風險監控儀表板 (Quantitative Stock Screener & Risk Dashboard)

A modern full-stack web application built with **Reflex (Python)**, **yfinance**, and **AkShare** designed for quantitative stock screening, VWAP trend filtering, volume ratio (VR) analysis, and ATR-based dynamic multi-level target/stop-loss prediction.

---

## 🌟 Key Features

* **Multi-Market Data Support:** Seamlessly fetches historical stock data for US markets (via `yfinance`) and Hong Kong stocks (via `AkShare` with automatic padding/formatting).
* **Advanced Quantitative Indicators:**
  * **VWAP (Volume Weighted Average Price):** Trend confirmation and bias monitoring.
  * **VR (Volume Ratio):** Detects breakout surges (`VR > 1.8`) or dry-up periods (`VR < 0.6`).
  * **ATR (Average True Range):** Dynamic volatility calculation for intelligent risk management.
* **Dynamic Multi-Level Targets & Stops:**
  * Conservative Target 1 (`T1`) & Aggressive Target 2 (`T2`).
  * ATR-based Trailing Stop Loss (`S1`) with live upside/downside percentage calculations and Risk-to-Reward ratio (`R:R`).
* **Interactive Dashboard UI:**
  * Fully customizable parameters via sidebar sliders (ATR period, multiplier, VR period, watchlist inputs).
  * Real-time filtering toggles.
  * Interactive charts powered by Recharts (Line charts with tooltips) and detailed historical data tabs.

---

## 🛠️ Tech Stack

* **Frontend & Backend:** [Reflex](https://reflex.dev/) (Python-based full-stack framework)
* **Data Sources:** `yfinance`, `AkShare`
* **Data Processing:** `pandas`, `numpy`

---

## 🚀 Getting Started Locally

### Prerequisites
Make sure you have **Python 3.11+** and `pip` installed.

### Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git)
   cd 股票篩選器與風險監控儀表板
