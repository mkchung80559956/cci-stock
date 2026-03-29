import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="台股動能分析-多源版", layout="wide")

# --- 核心分析函數 (支援不同來源標籤) ---
def process_stock(ticker, vol_multiplier, cci_len, source):
    pure_t = ticker.split('.')[0].strip()
    
    try:
        if source == "Yahoo Finance (預設)":
            ticker_obj = yf.Ticker(f"{pure_t}.TW")
            df = ticker_obj.history(period="7mo", interval="1d")
            if df.empty or len(df) < 40:
                ticker_obj = yf.Ticker(f"{pure_t}.TWO")
                df = ticker_obj.history(period="7mo", interval="1d")
        else:
            # 備用來源邏輯 (範例：可擴充其他 API 或直接抓取)
            df = yf.download(f"{pure_t}.TW", period="7mo", progress=False)
            ticker_obj = yf.Ticker(f"{pure_t}.TW") # 僅用於獲取名稱

        if df.empty or len(df) < cci_len + 10: return None

        df.columns = [c.capitalize() for c in df.columns]
        close = df['Close'].ffill().astype(float)
        high = df['High'].ffill().astype(float)
        low = df['Low'].ffill().astype(float)
        volume = df['Volume'].ffill().astype(float)

        # 指標計算
        cci = ta.cci(high, low, close, length=cci_len)
        rsi = ta.rsi(close, length=14)
        vol_ma5 = volume.rolling(window=5).mean()
        
        c_cci, p_cci = cci.iloc[-1], cci.iloc[-2]
        c_vol, a_vol = volume.iloc[-1], vol_ma5.iloc[-1]
        c_rsi = rsi.iloc[-1]

        # 趨勢天數
        curr_sign = 1 if c_cci >= 0 else -1
        duration = 0
        for i in range(len(cci)-1, -1, -1):
            if (1 if cci.iloc[i] >= 0 else -1) == curr_sign: duration += 1
            else: break

        # 警示標籤
        alert_tag = ""
        is_buy = (p_cci < 0 and c_cci > 0 and c_vol > a_vol * vol_multiplier)
        if is_buy:
            tags = []
            if c_cci > 100: tags.append("🚀 超強勢")
            elif duration <= 2: tags.append("🆕 初啟動")
            if c_vol > a_vol * 2: tags.append("💰 爆量攻擊")
            if c_rsi > 70: tags.append("⚠️ 注意過熱")
            alert_tag = " | ".join(tags) if tags else "🔥 訊號確立"

        return {
            "代碼": pure_t,
            "名稱": ticker_obj.info.get('shortName', pure_t),
            "收盤價": round(close.iloc[-1], 2),
            "CCI數值": round(np.clip(c_cci, -250, 250), 2),
            "趨勢": f"{'多頭' if curr_sign==1 else '空頭'}({duration}天)",
            "成交量比": round(c_vol / a_vol, 2),
            "警示標籤": alert_tag,
            "符合買進": "YES" if is_buy else "NO",
            "raw_df": df,
            "raw_cci": cci
        }
    except: return None

# --- UI 介面 ---
st.title("🏹 台股多源選股分析器")

with st.sidebar:
    st.header("🌐 資料庫設定")
    data_source = st.selectbox("選擇資料來源", ["Yahoo Finance (預設)", "備用資料庫 (快速)"])
    
    st.header("⚙️ 模式與參數")
    scan_mode = st.radio("掃描模式", ["自動掃描熱門股", "自訂代碼輸入"])
    
    if scan_mode == "自訂代碼輸入":
        user_input = st.text_area("代碼", "2330, 2317, 2454")
    else:
        user_input = "2330, 2317, 2454, 2303, 2603, 2609, 3231, 2382, 1513, 1503, 2618, 2610"
        
    vol_ratio = st.slider("成交量爆量倍數", 0.5, 2.5, 1.1)
    cci_p = st.number_input("CCI 週期", 10, 40, 14)

if st.button("🔍 執行策略掃描"):
    stocks = [s.strip() for s in user_input.split(",") if s.strip()]
    results = []
    prog = st.progress(0)
    for i, t in enumerate(stocks):
        res = process_stock(t, vol_ratio, cci_p, data_source)
        if res: results.append(res)
        prog.progress((i+1)/len(stocks))
    st.session_state['results'] = results

# --- 顯示與連動 ---
if 'results' in st.session_state and st.session_state['results']:
    data_list = st.session_state['results']
    df_main = pd.DataFrame(data_list).drop(columns=['raw_df', 'raw_cci'])
    
    st.subheader("📊 掃描清單 (點選下方列顯示圖表)")

    def highlight_buy(row):
        color = 'background-color: #4b0000; color: white' if row['符合買進'] == 'YES' else ''
        return [color] * len(row)

    event = st.dataframe(
        df_main.style.apply(highlight_buy, axis=1),
        use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row"
    )

    idx = event.selection.rows[0] if event.selection.rows else 0
    sel = data_list[idx]

    # --- 圖表區 ---
    st.divider()
    df_p = sel['raw_df'].tail(60)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.6, 0.4])
    fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_p.index, y=sel['raw_cci'].tail(60), name="CCI", line=dict(color='orange', width=3)), row=2, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="#FF3333", line_width=2.5, row=2, col=1)
    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, title=f"來源: {data_source} | {sel['代碼']} {sel['名稱']}")
    st.plotly_chart(fig, use_container_width=True)
