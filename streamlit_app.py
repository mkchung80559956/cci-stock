import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="台股精準動能分析", layout="wide")

# --- 核心算力：對齊照片數據的 CCI 邏輯 ---
def calculate_precise_cci(df, period=39):
    if df.empty or len(df) < period:
        return None, None
    
    # 1. 計算典型價格 Typical Price (TP) - 這是對齊照片關鍵
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    
    # 2. 計算 TP 的 39 期簡單移動平均 (SMA)
    df['SMA_TP'] = df['TP'].rolling(window=period).mean()
    
    # 3. 計算平均絕對偏差 (Mean Deviation)
    def calc_md(x):
        return np.mean(np.abs(x - np.mean(x)))
    
    df['MD'] = df['TP'].rolling(window=period).apply(calc_md, raw=True)
    
    # 4. CCI 公式: (TP - SMA) / (0.015 * MD)
    df['CCI'] = (df['TP'] - df['SMA_TP']) / (0.015 * df['MD'])
    
    return df['CCI'], df

# --- 數據抓取 ---
def get_stock_data(ticker):
    pure_t = ticker.split('.')[0].strip()
    # 抓取 1 年數據以確保 39 期計算緩衝充足
    t_obj = yf.Ticker(f"{pure_t}.TW")
    df = t_obj.history(period="1y")
    if df.empty or len(df) < 50:
        t_obj = yf.Ticker(f"{pure_t}.TWO")
        df = t_obj.history(period="1y")
    return df, t_obj

# --- UI 介面 ---
st.title("🏹 台股順勢交易：精準對齊版 (CCI 39T)")

with st.sidebar:
    st.header("🌐 資料庫與模式")
    scan_mode = st.radio("掃描模式", ["自動掃描熱門股", "自訂代碼輸入"])
    
    if scan_mode == "自動掃描熱門股":
        tickers = ["2330", "2317", "2454", "2303", "2603", "2609", "3231", "2382", "1513"]
    else:
        user_input = st.text_area("代碼 (逗號隔開)", "2330, 2317, 2454")
        tickers = [s.strip() for s in user_input.split(",") if s.strip()]
        
    vol_ratio = st.slider("成交量爆量倍數", 0.5, 2.5, 1.1)
    cci_p = st.number_input("CCI 週期 (照片為39)", 10, 60, 39)

if st.button("🔍 執行精準診斷"):
    all_res = []
    prog = st.progress(0)
    for i, t in enumerate(tickers):
        raw_df, t_obj = get_stock_data(t)
        if not raw_df.empty:
            cci_series, analyzed_df = calculate_precise_cci(raw_df, cci_p)
            if cci_series is not None:
                c_cci, p_cci = cci_series.iloc[-1], cci_series.iloc[-2]
                vol_ma5 = analyzed_df['Volume'].rolling(5).mean().iloc[-1]
                c_vol = analyzed_df['Volume'].iloc[-1]
                
                # 趨勢與標籤
                is_buy = (p_cci < 0 and c_cci > 0 and c_vol > vol_ma5 * vol_ratio)
                
                all_res.append({
                    "代碼": t,
                    "名稱": t_obj.info.get('shortName', t),
                    "收盤價": round(analyzed_df['Close'].iloc[-1], 2),
                    "CCI(精準)": round(c_cci, 2),
                    "趨勢方向": "⬆️ 轉強" if c_cci > p_cci else "⬇️ 轉弱",
                    "成交量比": round(c_vol / vol_ma5, 2),
                    "符合買進": "YES" if is_buy else "NO",
                    "df": analyzed_df
                })
        prog.progress((i+1)/len(tickers))
    st.session_state['data'] = all_res

# --- 顯示與點擊連動 ---
if 'data' in st.session_state and st.session_state['data']:
    results = st.session_state['data']
    df_view = pd.DataFrame(results).drop(columns=['df'])
    
    st.subheader("📊 掃描清單 (點選下方列連動圖表)")
    
    def highlight(row):
        return ['background-color: #4b0000; color: white' if row['符合買進'] == 'YES' else '' for _ in row]

    event = st.dataframe(df_view.style.apply(highlight, axis=1), 
                        use_container_width=True, hide_index=True, 
                        on_select="rerun", selection_mode="single-row")

    # 取得點選資料
    selected_idx = event.selection.rows[0] if event.selection.rows else 0
    sel = results[selected_idx]
    plot_df = sel['df'].tail(60)

    # --- 圖表強化 ---
    st.divider()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.6, 0.4])
    
    # K線
    fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], 
                               low=plot_df['Low'], close=plot_df['Close'], name="K線"), row=1, col=1)
    
    # CCI (精準 Typical Price 版)
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['CCI'], name="精準CCI", 
                            line=dict(color='orange', width=3)), row=2, col=1)
    
    # 方向強化虛線
    fig.add_hline(y=0, line_dash="dash", line_color="#FF3333", line_width=2.5, row=2, col=1)
    fig.add_hline(y=100, line_dash="dot", line_color="rgba(255,255,255,0.2)", row=2, col=1)
    fig.add_hline(y=-100, line_dash="dot", line_color="rgba(255,255,255,0.2)", row=2, col=1)

    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False,
                     title=f"【{sel['代碼']} {sel['名稱']}】精準動能分析 (Typical Price 模型)")
    st.plotly_chart(fig, use_container_width=True)
