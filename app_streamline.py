import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import akshare as ak

st.set_page_config(
    page_title="量化股票篩選器 | VWAP & ATR 多空預測儀表板",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ---------------------------------------------------------
# 1. 股票代號正規化與數據抓取 (yfinance + akshare 雙引擎)
# ---------------------------------------------------------
def normalize_ticker(ticker_str):
    ticker = ticker_str.strip().upper()
    if ticker.endswith(".HK"):
        symbol = ticker[:-3]
        if symbol.isdigit():
            return f"{str(int(symbol)).zfill(4)}.HK"
    return ticker


@st.cache_data(ttl=1800)
def fetch_stock_data(ticker):
    norm_ticker = normalize_ticker(ticker)

    # 引擎 1: yfinance
    try:
        df = yf.download(norm_ticker, period="1y", interval="1d", progress=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 10:
                return df
    except Exception:
        pass

    # 引擎 2: akshare
    if norm_ticker.endswith(".HK"):
        try:
            hk_num = norm_ticker.split(".")[0].zfill(5)
            df = ak.stock_hk_hist(symbol=hk_num, period="daily", start_date="20230101", adjust="qfq")
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "日期": "Date", "開盤": "Open", "收盤": "Close",
                    "最高": "High", "最低": "Low", "成交量": "Volume"
                })
                df["Date"] = pd.to_datetime(df["Date"])
                df.set_index("Date", inplace=True)
                return df
        except Exception:
            pass

    return None


def calculate_indicators(df, atr_period=14, atr_multiplier=2.0, vr_ma_period=20):
    data = df.copy()
    data['Typical_Price'] = (data['High'] + data['Low'] + data['Close']) / 3
    data['VP'] = data['Typical_Price'] * data['Volume']
    data['VWAP'] = data['VP'].cumsum() / data['Volume'].cumsum()

    data['Vol_MA'] = data['Volume'].rolling(window=vr_ma_period).mean()
    data['VR'] = data['Volume'] / data['Vol_MA']

    high_low = data['High'] - data['Low']
    high_close = np.abs(data['High'] - data['Close'].shift(1))
    low_close = np.abs(data['Low'] - data['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    data['ATR'] = tr.rolling(window=atr_period).mean()

    data['Rolling_Max_Close'] = data['Close'].cummax()
    data['ATR_Stop'] = data['Rolling_Max_Close'] - (data['ATR'] * atr_multiplier)

    # 多空預測線 (Up Target & Down Support Projections)
    data['Up_Target_1'] = data['Close'] + (data['ATR'] * 1.5)
    data['Up_Target_2'] = data['Close'] + (data['ATR'] * 3.0)
    data['Down_Support_1'] = data['ATR_Stop']
    data['Down_Support_2'] = data['Close'] - (data['ATR'] * 3.0)

    return data


# ---------------------------------------------------------
# 2. 邊欄參數設定
# ---------------------------------------------------------
st.sidebar.title("⚙️ 策略與篩選參數")

default_tickers = "NVDA, 7709.HK, 0981.HK, 0941.HK, 2388.HK, MRVL, ARM"
tickers_input = st.sidebar.text_area("股票池 (用逗號隔開)", value=default_tickers, height=100)
ticker_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

st.sidebar.markdown("---")
st.sidebar.subheader("指標參數設定")
atr_period = st.sidebar.slider("ATR 週期", 5, 30, 14)
atr_mult = st.sidebar.slider("ATR 止損倍數 (k)", 1.0, 4.0, 2.0, step=0.1)
vr_period = st.sidebar.slider("量比 (VR) 移動均線天數", 5, 60, 20)

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 篩選過濾條件")
filter_above_vwap = st.sidebar.checkbox("股價 > VWAP (趨勢偏多)", value=False)
filter_vr_mode = st.sidebar.selectbox("成交量狀態 (VR 條件)", ["不限", "放量突破 (VR > 1.8)", "地量乾涸 (VR < 0.6)"])
filter_atr_safe = st.sidebar.checkbox("未跌破 ATR 止損價", value=False)

st.sidebar.markdown("---")
show_all_scanned = st.sidebar.checkbox("顯示所有已載入標的 (包含不合條件者)", value=True)

# ---------------------------------------------------------
# 3. 主畫面與資料處理
# ---------------------------------------------------------
st.title("📈 量化股票篩選器 & 多空目標預測儀表板")
st.caption("結合 VWAP 站穩、Volume Ratio 放量/縮量 及 ATR 多空目標動態預測")

if not ticker_list:
    st.warning("請在側邊欄輸入至少一檔股票代號。")
    st.stop()

all_results = []
progress_bar = st.progress(0)

for idx, ticker in enumerate(ticker_list):
    df = fetch_stock_data(ticker)

    if df is None or len(df) < vr_period:
        st.warning(f"⚠️ 無法取得 {ticker} 數據，請檢查代碼。")
        progress_bar.progress((idx + 1) / len(ticker_list))
        continue

    df_calc = calculate_indicators(df, atr_period=atr_period, atr_multiplier=atr_mult, vr_ma_period=vr_period)
    latest = df_calc.iloc[-1]

    close_p = float(latest['Close'])
    vwap_p = float(latest['VWAP'])
    vr_v = float(latest['VR'])
    atr_val = float(latest['ATR'])
    atr_stop_p = float(latest['ATR_Stop'])

    up_t1 = float(latest['Up_Target_1'])
    up_t2 = float(latest['Up_Target_2'])
    down_s1 = float(latest['Down_Support_1'])
    down_s2 = float(latest['Down_Support_2'])

    upside_pct_1 = round((up_t1 - close_p) / close_p * 100, 2)
    downside_pct_1 = round((close_p - down_s1) / close_p * 100, 2)

    risk_reward_ratio = round(upside_pct_1 / downside_pct_1, 2) if downside_pct_1 > 0 else 0

    is_above_vwap = close_p > vwap_p
    is_safe_atr = close_p > atr_stop_p

    vr_status = "正常"
    if vr_v > 1.8:
        vr_status = "放量突破"
    elif vr_v < 0.6:
        vr_status = "量能乾涸"

    pass_vwap = not filter_above_vwap or is_above_vwap
    pass_atr = not filter_atr_safe or is_safe_atr

    pass_vr = True
    if filter_vr_mode == "放量突破 (VR > 1.8)":
        pass_vr = vr_v > 1.8
    elif filter_vr_mode == "地量乾涸 (VR < 0.6)":
        pass_vr = vr_v < 0.6

    is_qualified = pass_vwap and pass_atr and pass_vr

    all_results.append({
        "代號": normalize_ticker(ticker),
        "符合條件": "✅ 是" if is_qualified else "❌ 否",
        "最新收盤價": round(close_p, 2),
        "VWAP": round(vwap_p, 2),
        "上漲目標 T1 (+1.5x ATR)": round(up_t1, 2),
        "潛在上漲幅度 (%)": f"+{upside_pct_1}%",
        "下跌止損 S1 (ATR Stop)": round(down_s1, 2),
        "最大潛在風險 (%)": f"-{downside_pct_1}%",
        "風報比 (R:R)": risk_reward_ratio,
        "量比 (VR)": round(vr_v, 2),
        "量能狀態": vr_status,
        "ATR (14D)": round(atr_val, 2),
        "Is_Qualified": is_qualified,
        "Up_T1": round(up_t1, 2),
        "Up_T2": round(up_t2, 2),
        "Down_S1": round(down_s1, 2),
        "Down_S2": round(down_s2, 2),
        "Upside_Pct_1": upside_pct_1,
        "Downside_Pct_1": downside_pct_1,
        "DF_Data": df_calc
    })

    progress_bar.progress((idx + 1) / len(ticker_list))

progress_bar.empty()

# ---------------------------------------------------------
# 4. 結果呈現與詳細選單
# ---------------------------------------------------------
qualified_results = [r for r in all_results if r["Is_Qualified"]]

st.subheader(f"🎯 符合條件標的 ({len(qualified_results)} / {len(all_results)})")

display_list = all_results if show_all_scanned else qualified_results

if display_list:
    res_df = pd.DataFrame(display_list)

    display_cols = [
        "代號", "符合條件", "最新收盤價", "VWAP",
        "上漲目標 T1 (+1.5x ATR)", "潛在上漲幅度 (%)",
        "下跌止損 S1 (ATR Stop)", "最大潛在風險 (%)", "風報比 (R:R)", "量比 (VR)"
    ] if show_all_scanned else [
        "代號", "最新收盤價", "VWAP",
        "上漲目標 T1 (+1.5x ATR)", "潛在上漲幅度 (%)",
        "下跌止損 S1 (ATR Stop)", "最大潛在風險 (%)", "風報比 (R:R)", "量比 (VR)"
    ]

    st.dataframe(res_df[display_cols], width="stretch")

    st.markdown("---")

    # ---------------------------------------------------------
    # 5. 詳細按鈕與個股多空預測模組
    # ---------------------------------------------------------
    st.subheader("🔍 個股詳細數據與多空目標預測")

    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        selected_ticker = st.selectbox("選擇要調閱的股票代號:", res_df["代號"].tolist())
    with col_btn:
        st.write("")  # 間距調整
        st.write("")
        show_detail_btn = st.button("📊 載入個股深度解析", type="primary")

    selected_row = res_df[res_df["代號"] == selected_ticker].iloc[0]

    with st.expander(f"📌 {selected_ticker} 多空目標與風控細節 (點擊展開/收合)", expanded=True):
        tab1, tab2, tab3 = st.tabs(["🎯 多空目標預測", "📈 技術線圖", "📋 歷史數據細節"])

        with tab1:
            st.markdown(f"### 🎯 {selected_ticker} 多空價位預測矩陣")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🚀 核心上漲目標 (T1)", f"${selected_row['Up_T1']}", delta=f"+{selected_row['Upside_Pct_1']}%")
            c2.metric("🔥 強勢突破目標 (T2)", f"${selected_row['Up_T2']}",
                      delta=f"+{round(selected_row['Upside_Pct_1'] * 2, 2)}%")
            c3.metric("🛡️ 下跌風控止損 (S1)", f"${selected_row['Down_S1']}",
                      delta=f"-{selected_row['Downside_Pct_1']}%", delta_color="inverse")
            c4.metric("⚖️ 潛在風報比 (R:R)", f"{selected_row['風報比 (R:R)']}:1")

            st.markdown("""
            * **T1 (保守目標)**：當前收盤價 + 1.5 × ATR，適合做第一波段獲利分批減碼。
            * **T2 (激進目標)**：當前收盤價 + 3.0 × ATR，適合強勢主升段續抱目標。
            * **S1 (關鍵止損)**：多頭移動止損線 (Rolling ATR Stop)，跌破即代表多頭結構失效。
            """)

        with tab2:
            chart_df = selected_row["DF_Data"].tail(120)
            chart_data = pd.DataFrame({
                "收盤價": chart_df["Close"],
                "VWAP": chart_df["VWAP"],
                "上漲目標 T1": chart_df["Up_Target_1"],
                "ATR 風控止損 S1": chart_df["ATR_Stop"]
            })
            st.line_chart(chart_data)

        with tab3:
            st.markdown("#### 最近 15 個交易日關鍵指標明細")
            raw_display = selected_row["DF_Data"][['Close', 'VWAP', 'VR', 'ATR', 'ATR_Stop', 'Up_Target_1']].tail(15)
            st.dataframe(raw_display.sort_index(ascending=False), width="stretch")

else:
    st.info("目前沒有符合所選篩選條件的股票。請勾選側邊欄「顯示所有已載入標的」或放寬過濾設定。")
