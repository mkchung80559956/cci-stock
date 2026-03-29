import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="台股順勢選股分析", layout="wide")

def get_stock_data(ticker):
    pure_ticker = ticker.split('.')[0].strip()
    try:
        # 增加至 7 個月確保指標暖身充足
        df = yf.download(f"{pure_ticker}.TW", period="7mo", interval="1d", progress=False)
        if df.empty or len(df) < 50:
            df = yf.download(f"{pure_ticker}.TWO", period="7mo", interval="1d", progress=False)
        return df
    except:
        return pd.DataFrame()

def analyze_stock(df, vol_multiplier, cci_len):
    # 防護機制：確保數據量足夠計算指標 
    if df is None or df.empty or len(df) < cci_len + 20: 
        return None
    
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        close = df['Close'].ffill().astype(float).squeeze()
        high = df['High'].ffill().astype(float).squeeze()
        low = df['Low'].ffill().astype(float).squeeze()
        volume = df['Volume'].ffill().astype(float).squeeze()

        # 計算 CCI 與 RSI
        cci = ta.cci(high, low, close, length=cci_len)
        rsi6 = ta.rsi(close, length=6)
        rsi14 = ta.rsi(close, length=14)
        
        if cci is None or len(cci) < 2: return None

        vol_ma5 = volume.rolling(window=5).mean()
        c_cci, p_cci = cci.iloc[-1], cci.iloc[-2]
        c_vol, a_vol = volume.iloc[-1], vol_ma5.iloc[-1]

        # 趨勢天數計算
        curr_sign = 1 if c_cci >= 0 else -1
        duration = 0
        for i in range(len(cci)-1, -1, -1):
            if (1 if cci.iloc[i] >= 0 else -1) == curr_sign:
                duration += 1
            else:
                break

        status = "🔥 符合買進" if (p_cci < 0 and c_cci > 0 and c_vol > a_vol * vol_multiplier) else "觀察中"
        
        return {
            "日期": df.index[-1].strftime('%Y-%m-%d'),
            "收盤價": round(close.iloc[-1], 2),
            "CCI方向": "⬆️ 轉強" if c_cci > p_cci else "⬇️ 轉弱",
            "CCI數值": round(np.clip(c_cci, -250, 250), 2),
            "趨勢": f"{'多頭' if curr_sign==1 else '空頭'}({duration}天)",
            "成交量比": round(c_vol / a_vol, 2),
            "綜合狀態": status,
            "df": df, "cci": cci, "rsi6": rsi6, "rsi14": rsi14
        }
    except: return None

# --- UI 介面 ---
st.title("🏹 台股順勢交易選股器")

with st.sidebar:
    st.header("⚙️ 參數設定")
    mode = st.radio("模式", ["熱門股", "自訂"])
    vol_target = st.slider("成交量倍數", 0.5, 2.0, 1.1)
    cci_window = st.number_input("CCI 週期", 10, 40, 14)

popular_list = ["2330", "2317", "2454", "2603", "2609", "3231", "2382", "1513"]

if st.button("🚀 執行診斷"):
    tickers = popular_list if mode == "熱門股" else st.text_area("代碼").split(",")
    results = []
    for t in tickers:
        res = analyze_stock(get_stock_data(t.strip()), vol_target, cci_window)
        if res:
            res["代碼"] = t.strip()
            results.append(res)
            
    if results:
        res_df = pd.DataFrame(results).set_index("代碼")
        
        def color_style(val):
            if val == "⬆️ 轉強": return 'color: red; font-weight: bold'
            if val == "🔥 符合買進": return 'background-color: #FF4B4B; color: white'
            return ''
        
        st.dataframe(res_df.drop(columns=['df','cci','rsi6','rsi14']).style.applymap(color_style), use_container_width=True)

        st.divider()
        selected_stock = st.selectbox("查看詳細圖表", res_df.index)
        s_data = res_df.loc[selected_stock]
        df_p = s_data['df'].tail(60)
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_p.index, y=s_data['cci'].tail(60), name="CCI", line=dict(color='orange')), row=2, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="red", row=2, col=1)
        fig.update_layout(height=600, template="plotly_white", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
