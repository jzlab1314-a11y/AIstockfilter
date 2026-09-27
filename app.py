import reflex as rx
import yfinance as yf
import pandas as pd
import numpy as np
import akshare as ak


# ---------------------------------------------------------
# Data Fetching & Calculation Helpers
# ---------------------------------------------------------
def normalize_ticker(ticker_str: str) -> str:
    ticker = ticker_str.strip().upper()
    if ticker.endswith(".HK"):
        symbol = ticker[:-3]
        if symbol.isdigit():
            return f"{str(int(symbol)).zfill(4)}.HK"
    return ticker


def fetch_stock_df(ticker: str):
    norm_ticker = normalize_ticker(ticker)
    try:
        df = yf.download(norm_ticker, period="1y", interval="1d", progress=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 10:
                return df
    except Exception:
        pass

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


def process_stock_data(ticker: str, atr_period: int, atr_mult: float, vr_period: int):
    df = fetch_stock_df(ticker)
    if df is None or len(df) < vr_period:
        return None

    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VP'] = df['Typical_Price'] * df['Volume']
    df['VWAP'] = df['VP'].cumsum() / df['Volume'].cumsum()

    df['Vol_MA'] = df['Volume'].rolling(window=vr_period).mean()
    df['VR'] = df['Volume'] / df['Vol_MA']

    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift(1))
    low_close = np.abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=atr_period).mean()

    df['Rolling_Max_Close'] = df['Close'].cummax()
    df['ATR_Stop'] = df['Rolling_Max_Close'] - (df['ATR'] * atr_mult)

    df['Up_Target_1'] = df['Close'] + (df['ATR'] * 1.5)
    df['Up_Target_2'] = df['Close'] + (df['ATR'] * 3.0)
    df['Down_Support_1'] = df['ATR_Stop']

    latest = df.iloc[-1]
    close_p = float(latest['Close'])
    vwap_p = float(latest['VWAP'])
    vr_v = float(latest['VR'])
    atr_val = float(latest['ATR'])
    atr_stop_p = float(latest['ATR_Stop'])
    up_t1 = float(latest['Up_Target_1'])
    up_t2 = float(latest['Up_Target_2'])

    upside_pct = round((up_t1 - close_p) / close_p * 100, 2)
    downside_pct = round((close_p - atr_stop_p) / close_p * 100, 2)
    rr_ratio = round(upside_pct / downside_pct, 2) if downside_pct > 0 else 0.0

    vr_status = "放量突破" if vr_v > 1.8 else ("量能乾涸" if vr_v < 0.6 else "正常")

    # Chart Time Series
    chart_df = df.tail(120).reset_index()
    chart_data = []
    for _, row in chart_df.iterrows():
        chart_data.append({
            "Date": str(row['Date'])[:10],
            "Close": round(float(row['Close']), 2),
            "VWAP": round(float(row['VWAP']), 2),
            "Up_Target_1": round(float(row['Up_Target_1']), 2),
            "ATR_Stop": round(float(row['ATR_Stop']), 2)
        })

    # Raw Data Time Series
    raw_df = df.tail(15).reset_index().sort_values(by="Date", ascending=False)
    raw_data = []
    for _, row in raw_df.iterrows():
        raw_data.append({
            "Date": str(row['Date'])[:10],
            "Close": round(float(row['Close']), 2),
            "VWAP": round(float(row['VWAP']), 2),
            "VR": round(float(row['VR']), 2),
            "ATR": round(float(row['ATR']), 2),
            "ATR_Stop": round(float(row['ATR_Stop']), 2),
            "Up_Target_1": round(float(row['Up_Target_1']), 2)
        })

    return {
        "symbol": normalize_ticker(ticker),
        "close": round(close_p, 2),
        "vwap": round(vwap_p, 2),
        "is_above_vwap": close_p > vwap_p,
        "vr": round(vr_v, 2),
        "vr_status": vr_status,
        "atr": round(atr_val, 2),
        "up_t1": round(up_t1, 2),
        "up_t2": round(up_t2, 2),
        "down_s1": round(atr_stop_p, 2),
        "upside_pct": upside_pct,
        "downside_pct": downside_pct,
        "rr_ratio": rr_ratio,
        "is_safe_atr": close_p > atr_stop_p,
        "chart_data": chart_data,
        "raw_data": raw_data
    }


# ---------------------------------------------------------
# Reflex State
# ---------------------------------------------------------
class State(rx.State):
    tickers_input: str = "NVDA, 7709.HK, 0981.HK, 0941.HK, 2388.HK, MRVL, ARM"
    atr_period: int = 14
    atr_mult: float = 2.0
    vr_period: int = 20

    filter_above_vwap: bool = False
    filter_vr_mode: str = "不限"
    filter_atr_safe: bool = False
    show_all_scanned: bool = True

    is_loading: bool = False
    all_results: list[dict] = []
    selected_ticker: str = ""

    def run_scan(self):
        self.is_loading = True
        yield

        tickers = [t.strip().upper() for t in self.tickers_input.split(",") if t.strip()]
        scanned = []
        for ticker in tickers:
            data = process_stock_data(ticker, self.atr_period, self.atr_mult, self.vr_period)
            if data:
                # Apply filter logic
                pass_vwap = not self.filter_above_vwap or data["is_above_vwap"]
                pass_atr = not self.filter_atr_safe or data["is_safe_atr"]

                pass_vr = True
                if self.filter_vr_mode == "放量突破 (VR > 1.8)":
                    pass_vr = data["vr"] > 1.8
                elif self.filter_vr_mode == "地量乾涸 (VR < 0.6)":
                    pass_vr = data["vr"] < 0.6

                data["is_qualified"] = pass_vwap and pass_atr and pass_vr
                scanned.append(data)

        self.all_results = scanned
        if scanned and not self.selected_ticker:
            self.selected_ticker = scanned[0]["symbol"]
        self.is_loading = False

    @rx.var
    def displayed_results(self) -> list[dict]:
        if self.show_all_scanned:
            return self.all_results
        return [r for r in self.all_results if r.get("is_qualified", False)]

    @rx.var
    def qualified_count(self) -> int:
        return len([r for r in self.all_results if r.get("is_qualified", False)])

    @rx.var
    def available_tickers(self) -> list[str]:
        return [r["symbol"] for r in self.displayed_results]

    @rx.var
    def current_selected_data(self) -> dict:
        for r in self.all_results:
            if r["symbol"] == self.selected_ticker:
                return r
        return {}


# ---------------------------------------------------------
# UI Layout Components
# ---------------------------------------------------------
def sidebar() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("⚙️ 策略與篩選參數", size="4"),
            rx.text("股票池 (用逗號隔開)", size="2", weight="bold"),
            rx.text_area(
                value=State.tickers_input,
                on_change=State.set_tickers_input,
                rows="3",
                width="100%"
            ),
            rx.divider(),
            rx.text(f"ATR 週期: {State.atr_period}", size="2"),
            rx.slider(value=State.atr_period, min=5, max=30, on_change=State.set_atr_period),
            rx.text(f"ATR 止損倍數 (k): {State.atr_mult}", size="2"),
            rx.slider(value=State.atr_mult, min=1.0, max=4.0, step=0.1, on_change=State.set_atr_mult),
            rx.text(f"VR 均線天數: {State.vr_period}", size="2"),
            rx.slider(value=State.vr_period, min=5, max=60, on_change=State.set_vr_period),
            rx.divider(),
            rx.heading("🔍 篩選過濾條件", size="3"),
            rx.checkbox(
                "股價 > VWAP (趨勢偏多)",
                checked=State.filter_above_vwap,
                on_change=State.set_filter_above_vwap
            ),
            rx.select(
                ["不限", "放量突破 (VR > 1.8)", "地量乾涸 (VR < 0.6)"],
                value=State.filter_vr_mode,
                on_change=State.set_filter_vr_mode,
                width="100%"
            ),
            rx.checkbox(
                "未跌破 ATR 止損價",
                checked=State.filter_atr_safe,
                on_change=State.set_filter_atr_safe
            ),
            rx.checkbox(
                "顯示所有已載入標的",
                checked=State.show_all_scanned,
                on_change=State.set_show_all_scanned
            ),
            rx.button(
                "🚀 開始掃描分析",
                on_click=State.run_scan,
                loading=State.is_loading,
                color_scheme="blue",
                width="100%",
                margin_top="1rem"
            ),
            spacing="3",
            align_items="stretch"
        ),
        padding="1.5rem",
        width="320px",
        background_color=rx.color("accent", 2),
        border_right=f"1px solid {rx.color('gray', 4)}"
    )


def main_content() -> rx.Component:
    sel = State.current_selected_data

    return rx.box(
        rx.vstack(
            rx.heading("📈 量化股票篩選器 & 多空目標預測儀表板", size="6"),
            rx.text("結合 VWAP 站穩、Volume Ratio 放量/縮量 及 ATR 多空目標動態預測", color="gray"),
            rx.badge(f"🎯 符合條件標的 ({State.qualified_count} / {State.all_results.length})", size="3",
                     color_scheme="green"),

            # Scanned Stocks Data Table
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("代號"),
                        rx.table.column_header_cell("符合條件"),
                        rx.table.column_header_cell("最新價"),
                        rx.table.column_header_cell("VWAP"),
                        rx.table.column_header_cell("上漲目標 T1"),
                        rx.table.column_header_cell("潛在上漲 (%)"),
                        rx.table.column_header_cell("止損價 S1"),
                        rx.table.column_header_cell("風報比 (R:R)"),
                        rx.table.column_header_cell("量比 (VR)")
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        State.displayed_results,
                        lambda row: rx.table.row(
                            rx.table.cell(row["symbol"]),
                            rx.table.cell(rx.cond(row["is_qualified"], "✅ 是", "❌ 否")),
                            rx.table.cell(f"${row['close']}"),
                            rx.table.cell(f"${row['vwap']}"),
                            rx.table.cell(f"${row['up_t1']}"),
                            rx.table.cell(f"+{row['upside_pct']}%"),
                            rx.table.cell(f"${row['down_s1']}"),
                            rx.table.cell(f"{row['rr_ratio']}:1"),
                            rx.table.cell(f"{row['vr']} ({row['vr_status']})")
                        )
                    )
                ),
                width="100%",
                margin_y="1rem"
            ),
            rx.divider(),

            # Detail Section
            rx.heading("🔍 個股深度解析與多空預測", size="5"),
            rx.hstack(
                rx.text("選擇標的:", weight="bold"),
                rx.select(
                    State.available_tickers,
                    value=State.selected_ticker,
                    on_change=State.set_selected_ticker
                ),
                align_items="center"
            ),

            rx.cond(
                State.selected_ticker != "",
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("🎯 多空目標預測", value="targets"),
                        rx.tabs.trigger("📈 技術線圖", value="chart"),
                        rx.tabs.trigger("📋 歷史數據明細", value="raw")
                    ),
                    rx.tabs.content(
                        rx.grid(
                            rx.card(rx.text("🚀 保守目標 T1"), rx.heading(f"${sel['up_t1']}", color="green"),
                                    rx.text(f"+{sel['upside_pct']}%")),
                            rx.card(rx.text("🔥 強勢目標 T2"), rx.heading(f"${sel['up_t2']}", color="green")),
                            rx.card(rx.text("🛡️ 風控止損 S1"), rx.heading(f"${sel['down_s1']}", color="red"),
                                    rx.text(f"-{sel['downside_pct']}%")),
                            rx.card(rx.text("⚖️ 風報比 R:R"), rx.heading(f"{sel['rr_ratio']}:1", color="blue")),
                            columns="4",
                            gap="4",
                            padding_top="1rem"
                        ),
                        value="targets"
                    ),
                    rx.tabs.content(
                        rx.recharts.line_chart(
                            rx.recharts.line(data_key="Close", stroke="#8884d8", name="收盤價"),
                            rx.recharts.line(data_key="VWAP", stroke="#82ca9d", name="VWAP"),
                            rx.recharts.line(data_key="Up_Target_1", stroke="#ffc658", name="目標 T1"),
                            rx.recharts.line(data_key="ATR_Stop", stroke="#ff7300", name="止損 S1"),
                            rx.recharts.x_axis(data_key="Date"),
                            rx.recharts.y_axis(),
                            rx.recharts.graph_tool_tip(),
                            data=sel["chart_data"],
                            width="100%",
                            height=350
                        ),
                        value="chart"
                    ),
                    rx.tabs.content(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("日期"),
                                    rx.table.column_header_cell("收盤價"),
                                    rx.table.column_header_cell("VWAP"),
                                    rx.table.column_header_cell("VR"),
                                    rx.table.column_header_cell("ATR"),
                                    rx.table.column_header_cell("ATR 止損")
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    sel["raw_data"],
                                    lambda r: rx.table.row(
                                        rx.table.cell(r["Date"]),
                                        rx.table.cell(r["Close"]),
                                        rx.table.cell(r["VWAP"]),
                                        rx.table.cell(r["VR"]),
                                        rx.table.cell(r["ATR"]),
                                        rx.table.cell(r["ATR_Stop"])
                                    )
                                )
                            )
                        ),
                        value="raw"
                    ),
                    default_value="targets",
                    width="100%"
                )
            ),
            spacing="4",
            align_items="stretch"
        ),
        padding="2rem",
        flex="1"
    )


def index() -> rx.Component:
    return rx.hstack(
        sidebar(),
        main_content(),
        on_mount=State.run_scan,
        spacing="0",
        min_height="100vh"
    )


app = rx.App()
app.add_page(index, title="量化股票篩選器 | Reflex Dashboard")
