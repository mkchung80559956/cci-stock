import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np

st.set_page_config(page_title="台股順勢選股器-視覺強化版", layout="wide")

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
    """計算目前的 CCI 趨勢（正或負）已經持續了幾天"""
    curr_sign = 1 if cci_series.iloc[-1] >= 0 else -1
    duration = 0
    for i in range(len(cci_series)-1, -1, -1):
        sign = 1 if cci_series.iloc[i] >= 0 else -1
        if sign == curr_sign:
            duration += 1
        else:
            break
    return duration, "多頭" if curr_sign == 1 else "空頭"

def analyze_stock(df, vol_multiplier, cci_len):
    if df.empty or len(df) < cci_len + 10: 
        return None
    
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df['Close'].ffill().astype(float).squeeze()
        high = df['High'].ffill().astype(float).squeeze()
        low = df['Low'].ffill().astype(float).squeeze()
        volume = df['Volume'].ffill().astype(float).squeeze()

        # 計算指標
        cci = ta.cci(high, low, close, length=cci_len)
        rsi6 = ta.rsi(close, length=6)
        rsi14 = ta.rsi(close, length=14)
        vol_ma5 = volume.rolling(window=5).mean()

        c_cci, p_cci = cci.iloc[-1], cci.iloc[-2]
        c_rsi6, p_rsi6 = rsi6.iloc[-1], rsi6.iloc[-2]
        c_rsi14, p_rsi14 = rsi14.iloc[-1], rsi14.iloc[-2]
        c_vol, a_vol = volume.iloc[-1], vol_ma5.iloc[-1]

        # 修正 CCI 極端值
        display_cci = np.clip(c_cci, -250, 250)
        
        # 計算趨勢天數
        duration, trend_type = calculate_trend_duration(cci)

        # 判定方向
        cci_direction = "⬆️ 轉強" if c_cci > p_cci else "⬇️ 轉弱"
        
        # 買進策略
        cond_cci = p_cci < 0 and c_cci > 0
        cond_rsi = p_rsi6 < p_rsi14 and c_rsi6 > c_rsi14
        cond_vol = c_vol > (a_vol * vol_multiplier)

        status = "🔥 符合買進" if (cond_cci and cond_rsi and cond_vol) else "觀察中"
        
        return {
            "數據日期": df.index[-1].strftime('%Y-%m-%d'),
            "收盤價": round(close.iloc[-1], 2),
            "CCI方向": cci_direction,
            "CCI數值": round(display_cci, 2),
            "趨勢類型": trend_type,
            "趨勢天數": duration,
            "成交量比": round(c_vol / a_vol, 2),
            "綜合狀態": status
        }
    except:
        return None

# --- UI ---
st.title("🏹 台股順勢交易選股器 (視覺強化版)")

with st.sidebar:
    st.header("⚙️ 參數設定")
    mode = st.radio("掃描模式", ["熱門股", "自訂"])
    vol_target = st.slider("成交量倍數", 0.5, 2.0, 1.1)
    cci_window = st.number_input("CCI 週期", 10, 40, 14)

popular_list = ["2330", "2317", "2454", "2603", "2609", "3231", "2382", "1513", "1503", "2303"]

if st.button("🚀 開始分析"):
    tickers = popular_list if mode == "熱門股" else st.text_area("代碼").split(",")
    all_res = []
    for t in tickers:
        df_data = get_stock_data(t.strip())
        res = analyze_stock(df_data, vol_target, cci_window)
        if res:
            res["代碼"] = t.strip()
            all_res.append(res)
            
    if all_res:
        res_df = pd.DataFrame(all_res).set_index("代碼")
        
        # 定義顏色樣式
        def color_style(val):
            if val == "⬆️ 轉強": return 'color: red; font-weight: bold'
            if val == "⬇️ 轉弱": return 'color: green'
            if val == "🔥 符合買進": return 'background-color: red; color: white'
            return ''

        st.subheader("📊 趨勢掃描清單")
        st.dataframe(res_df.style.applymap(color_style), use_container_width=True)
