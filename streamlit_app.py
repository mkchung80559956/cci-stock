import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np

st.set_page_config(page_title="台股量價策略終極版", layout="wide")

def get_stock_data(ticker):
    pure_ticker = ticker.split('.')[0].strip()
    try:
        # 抓取 6 個月資料確保 CCI(39) 有足夠暖身期
        df = yf.download(f"{pure_ticker}.TW", period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 45:
            df = yf.download(f"{pure_ticker}.TWO", period="6mo", interval="1d", progress=False)
        return df
    except:
        return pd.DataFrame()

def analyze_stock(df, vol_multiplier, cci_len):
    if df.empty or len(df) < cci_len + 5: 
        return None
    
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 確保數據為浮點數且移除空值
        close = df['Close'].ffill().astype(float).squeeze()
        high = df['High'].ffill().astype(float).squeeze()
        low = df['Low'].ffill().astype(float).squeeze()
        volume = df['Volume'].ffill().astype(float).squeeze()

        # 計算指標
        cci = ta.cci(high, low, close, length=cci_len)
        rsi6 = ta.rsi(close, length=6)
        rsi14 = ta.rsi(close, length=14)
        vol_ma5 = volume.rolling(window=5).mean()

        # 取得最新與前一日數值
        c_cci = cci.iloc[-1]
        p_cci = cci.iloc[-2]
        
        # --- 異常值檢查 ---
        # 如果出現 inf 或 nan，或絕對值超過 1000，進行限幅處理
        if pd.isna(c_cci) or np.isinf(c_cci):
            return None
        
        display_cci = np.clip(c_cci, -1000, 1000) # 強制限制在 -1000 ~ 1000 之間

        c_rsi6, p_rsi6 = rsi6.iloc[-1], rsi6.iloc[-2]
        c_rsi14, p_rsi14 = rsi14.iloc[-1], rsi14.iloc[-2]
        c_vol, a_vol = volume.iloc[-1], vol_ma5.iloc[-1]

        # 策略判定
        cond_cci = p_cci < 0 and c_cci > 0
        cond_rsi = p_rsi6 < p_rsi14 and c_rsi6 > c_rsi14
        cond_vol = c_vol > (a_vol * vol_multiplier)

        status = "🔥 符合" if (cond_cci and cond_rsi and cond_vol) else "未達標"
        
        return {
            "數據日期": df.index[-1].strftime('%Y-%m-%d'),
            "收盤價": round(close.iloc[-1], 2),
            "CCI數值": round(display_cci, 2),
            "RSI(6)": round(c_rsi6, 2),
            "成交量比": round(c_vol / a_vol, 2),
            "狀態": status
        }
    except:
        return None

# --- UI 介面 ---
st.title("🛡️ 台股策略選股器 (異常值修正版)")

with st.sidebar:
    st.header("⚙️ 設定")
    mode = st.radio("模式", ["熱門股掃描", "自訂代碼"])
    vol_ratio = st.slider("成交量爆量倍數", 0.5, 2.0, 1.1, 0.1)
    cci_p = st.number_input("CCI 週期", 10, 60, 14)

popular_list = ["2330", "2317", "2454", "2303", "2603", "2609", "3231", "2382", "1513", "6235"]

if st.button("開始掃描"):
    tickers = popular_list if mode == "熱門股掃描" else st.text_area("輸入代碼").split(",")
    results = []
    
    for t in tickers:
        df_data = get_stock_data(t.strip())
        res = analyze_stock(df_data, vol_ratio, cci_p)
        if res:
            res["代碼"] = t.strip()
            results.append(res)
            
    if results:
        df_final = pd.DataFrame(results).set_index("代碼")
        st.dataframe(df_final.style.highlight_max(axis=0, subset=['成交量比']), use_container_width=True)
