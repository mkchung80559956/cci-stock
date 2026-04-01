import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title="台股精準動能分析-最新數據版", layout="wide")

# --- 核心算力：對齊照片數據的 CCI 邏輯 ---
def calculate_precise_cci(df, period=39):
    if df.empty or len(df) < period:
        return None, None
    
    # 複製一份避免警告
    df = df.copy()
    
    # 1. 計算典型價格 Typical Price (TP)
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    
    # 2. 計算 TP 的 SMA
    df['SMA_TP'] = df['TP'].rolling(window=period).mean()
    
    # 3. 計算平均絕對偏差 (Mean Deviation)
    def calc_md(x):
        return np.mean(np.abs(x - np.mean(x)))
    
    df['MD'] = df['TP'].rolling(window=period).apply(calc_md, raw=True)
    
    # 4. CCI 公式
    df['CCI'] = (df['TP'] - df['SMA_TP']) / (0.015 * df['MD'])
    
    return df['CCI'], df

# --- 數據抓取 (修正為抓取最新日期) ---
def get_stock_data(ticker):
    pure_t = ticker.split('.')[0].strip()
    # 設定抓取到明天，確保包含今天最新的盤中/收盤數據
    end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    try:
        # 使用 download 並關閉快取，確保資料最新
        df = yf.download(f"{pure_t}.TW", start=start_date, end=end_date, progress=False, multi_level_download=False)
        if df.empty or len(df) < 50:
            df = yf.download(f"{pure_t}.TWO", start=start_date, end=end_date, progress=False, multi_level_download=False)
        
        # 處理 yfinance 可能回傳的 MultiIndex 欄位
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        t_obj = yf.Ticker(f"{pure_t}.TW")
        return df, t_obj
    except:
        return pd.DataFrame(), None

# --- UI 介面 ---
st.title("🏹 台股順勢交易：精準對齊版 (最新數據)")

with st.sidebar:
    st.header("🌐 資料庫與模式")
    scan_mode = st.radio("掃描模式", ["自動掃描熱門股", "自訂代碼輸入"])
    
    if scan_mode == "自動掃描熱門股":
        tickers = ["2330", "2317", "2454", "2303", "2603", "2609", "3231", "2382", "1513"]
    else:
        user_input = st.text_area("代碼 (逗號隔開)", "2330, 2317, 2454")
        tickers = [s.strip() for s in user_input.split(",") if s.strip()]
        
    vol_ratio = st.slider("成交量爆量倍數", 0.5, 2.5, 1.1)
    cci_p = st.number_input("CCI 週期", 10, 60, 39)

if st.button("🔍 執行最新診斷"):
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
                
                # 趨勢標籤邏輯
                is_buy = (p_cci < 0 and c_cci > 0 and c_vol > vol_ma5 * vol_ratio)
                
                all_res.append({
                    "代碼": t,
                    "名稱": t_obj.info.get('shortName', t) if t_obj else t,
                    "日期": analyzed_df.index[-1].strftime('%Y-%m-%d'),
                    "收盤價": round(analyzed_df['Close'].iloc[-1], 2),
                    "CCI(39)": round(c_cci, 2),
                    "方向": "⬆️ 轉強" if c_cci > p_cci else "⬇️ 轉弱",
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
    
    st.subheader(f"📊 掃描清單 (數據截至: {results[0]['日期']})")
    
    def highlight(row):
        return ['background-color: #4b0000; color: white' if row['符合買進'] == 'YES' else '' for _ in row]

    event = st.dataframe(df_view.style.apply(highlight, axis=1), 
                        use_container_width=True, hide_index=True, 
                        on_select="rerun", selection_mode="single-row")

    selected_idx = event.selection.rows[0] if event.selection.rows else 0
    sel = results[selected_idx]
    plot_df = sel['df'].tail(60)

    # --- 圖表強化 ---
    st.divider()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.6, 0.4])
    
    fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], 
                               low=plot_df['Low'], close=plot_df['Close'], name="K線"), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['CCI'], name="精準CCI", 
                            line=dict(color='orange', width=3)), row=2, col=1)
    
    fig.add_hline(y=0, line_dash="dash", line_color="#FF3333", line_width=2.5, row=2, col=1)
    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False,
                     title=f"【{sel['代碼']} {sel['名稱']}】精準動能分析")
    st.plotly_chart(fig, use_container_width=True)
