import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="台股順勢選股+圖表分析", layout="wide")

def get_stock_data(ticker):
    pure_ticker = ticker.split('.')[0].strip()
    try:
        df = yf.download(f"{pure_ticker}.TW", period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 50:
            df = yf.download(f"{pure_ticker}.TWO", period="6mo", interval="1d", progress=False)
        return df
    except:
        return pd.DataFrame()

def calculate_trend_duration(cci_series):
    curr_sign = 1 if cci_series.iloc[-1] >= 0 else -1
    duration = 0
    for i in range(len(cci_series)-1, -1, -1):
        if (1 if cci_series.iloc[i] >= 0 else -1) == curr_sign:
            duration += 1
        else:
            break
    return duration, "多頭" if curr_sign == 1 else "空頭"

def analyze_stock(df, vol_multiplier, cci_len):
    if df.empty or len(df) < cci_len + 10: return None
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        close = df['Close'].ffill().astype(float).squeeze()
        high = df['High'].ffill().astype(float).squeeze()
        low = df['Low'].ffill().astype(float).squeeze()
        volume = df['Volume'].ffill().astype(float).squeeze()

        cci = ta.cci(high, low, close, length=cci_len)
        rsi6 = ta.rsi(close, length=6)
        rsi14 = ta.rsi(close, length=14)
        vol_ma5 = volume.rolling(window=5).mean()

        c_cci, p_cci = cci.iloc[-1], cci.iloc[-2]
        c_rsi6, p_rsi6 = rsi6.iloc[-1], rsi6.iloc[-2]
        c_rsi14, p_rsi14 = rsi14.iloc[-1], rsi14.iloc[-2]
        c_vol, a_vol = volume.iloc[-1], vol_ma5.iloc[-1]

        duration, trend_type = calculate_trend_duration(cci)
        cci_dir = "⬆️ 轉強" if c_cci > p_cci else "⬇️ 轉弱"
        
        cond_cci = p_cci < 0 and c_cci > 0
        cond_rsi = p_rsi6 < p_rsi14 and c_rsi6 > c_rsi14
        cond_vol = c_vol > (a_vol * vol_multiplier)
        status = "🔥 符合買進" if (cond_cci and cond_rsi and cond_vol) else "觀察中"
        
        return {
            "日期": df.index[-1].strftime('%Y-%m-%d'),
            "收盤價": round(close.iloc[-1], 2),
            "CCI方向": cci_dir,
            "CCI數值": round(np.clip(c_cci, -250, 250), 2),
            "趨勢": f"{trend_type}({duration}天)",
            "成交量比": round(c_vol / a_vol, 2),
            "綜合狀態": status,
            "df": df, "cci": cci, "rsi6": rsi6, "rsi14": rsi14
        }
    except: return None

# --- UI ---
st.title("🏹 台股順勢交易選股器 (含技術圖表)")

with st.sidebar:
    st.header("⚙️ 參數設定")
    mode = st.radio("模式", ["熱門股", "自訂"])
    vol_target = st.slider("成交量倍數", 0.5, 2.0, 1.1)
    cci_window = st.number_input("CCI 週期", 10, 40, 14)

popular_list = ["2330", "2317", "2454", "2603", "2609", "3231", "2382", "1513", "1503"]

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
        
        # 顯示表格 (視覺強化)
        def color_style(val):
            if val == "⬆️ 轉強": return 'color: red; font-weight: bold'
            if val == "🔥 符合買進": return 'background-color: #FF4B4B; color: white'
            return ''
        
        st.subheader("📊 趨勢掃描清單")
        st.dataframe(res_df.drop(columns=['df','cci','rsi6','rsi14']).style.applymap(color_style), use_container_width=True)

        # --- 繪製圖表區 ---
        st.divider()
        st.subheader("📈 個股技術走勢詳解")
        selected_stock = st.selectbox("選擇要查看圖表的股票", res_df.index)
        
        s_data = res_df.loc[selected_stock]
        df_plot = s_data['df'].tail(60) # 只看最近60天
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, row_heights=[0.5, 0.25, 0.25],
                           subplot_titles=(f"{selected_stock} K線圖", "CCI 指標", "RSI 指標"))

        # 1. K線圖
        fig.add_trace(go.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], 
                                   low=df_plot['Low'], close=df_plot['Close'], name="K線"), row=1, col=1)
        
        # 2. CCI 圖
        fig.add_trace(go.Scatter(x=df_plot.index, y=s_data['cci'].tail(60), line=dict(color='orange'), name="CCI"), row=2, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=100, line_dash="dot", line_color="gray", row=2, col=1)
        fig.add_hline(y=-100, line_dash="dot", line_color="gray", row=2, col=1)

        # 3. RSI 圖
        fig.add_trace(go.Scatter(x=df_plot.index, y=s_data['rsi6'].tail(60), name="RSI6", line=dict(color='red')), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_plot.index, y=s_data['rsi14'].tail(60), name="RSI14", line=dict(color='blue')), row=3, col=1)

        fig.update_layout(height=800, template="plotly_white", showlegend=False, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
