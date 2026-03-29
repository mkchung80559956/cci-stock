import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

def get_stock_data(ticker):
    # 移除使用者可能誤輸入的後綴，由程式統一處理
    pure_ticker = ticker.split('.')[0]
    
    # 嘗試上市代碼
    df = yf.download(f"{pure_ticker}.TW", period="6mo", interval="1d", progress=False)
    # 如果上市抓不到，嘗試上櫃代碼
    if df.empty or len(df) < 40:
        df = yf.download(f"{pure_ticker}.TWO", period="6mo", interval="1d", progress=False)
    return df

def check_strategy(df, vol_multiplier):
    if df.empty or len(df) < 40: 
        return False, "數據長度不足"
    
    try:
        # 處理多重索引問題 (yfinance 新版特性)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close_ser = df['Close'].astype(float)
        high_ser = df['High'].astype(float)
        low_ser = df['Low'].astype(float)
        volume_ser = df['Volume'].astype(float)

        # 指標計算
        cci = ta.cci(high_ser, low_ser, close_ser, length=39)
        rsi6 = ta.rsi(close_ser, length=6)
        rsi14 = ta.rsi(close_ser, length=14)
        vol_ma5 = volume_ser.rolling(window=5).mean()

        # 取得數值
        curr_cci = cci.iloc[-1]
        prev_cci = cci.iloc[-2]
        curr_rsi6, prev_rsi6 = rsi6.iloc[-1], rsi6.iloc[-2]
        curr_rsi14, prev_rsi14 = rsi14.iloc[-1], rsi14.iloc[-2]
        curr_vol = volume_ser.iloc[-1]
        avg_vol = vol_ma5.iloc[-1]

        # 策略邏輯
        cci_ok = prev_cci < 0 and curr_cci > 0
        rsi_ok = prev_rsi6 < prev_rsi14 and curr_rsi6 > curr_rsi14
        vol_ok = curr_vol > (avg_vol * vol_multiplier)

        if cci_ok and rsi_ok and vol_ok:
            return True, "符合條件"
        
        # 顯示沒過的原因 (Debug 用)
        reasons = []
        if not cci_ok: reasons.append("CCI未突破0")
        if not rsi_ok: reasons.append("RSI未金叉")
        if not vol_ok: reasons.append("量能未達標")
        return False, f"未達標 ({', '.join(reasons)})"

    except Exception as e:
        return False, f"計算錯誤: {str(e)}"

# UI 介面
st.title("🚀 台股量價動能選股器")

with st.sidebar:
    st.header("參數調整")
    vol_ratio = st.slider("成交量爆量倍數 (相較5日均量)", 1.0, 3.0, 1.5, 0.1)
    stock_input = st.text_area("輸入代碼 (逗號隔開)", "2330, 2317, 2454, 2603, 2303, 2609, 2618")

if st.button("開始掃描"):
    tickers = [s.strip() for s in stock_input.replace("\n", ",").split(",") if s.strip()]
    results = []
    progress_bar = st.progress(0)
    
    for i, ticker in enumerate(tickers):
        df = get_stock_data(ticker)
        if not df.empty:
            is_match, msg = check_strategy(df, vol_ratio)
            if is_match:
                results.append({
                    "代碼": ticker,
                    "收盤價": round(float(df['Close'].iloc[-1]), 2),
                    "成交量": int(df['Volume'].iloc[-1]),
                    "狀態": "🔥 符合"
                })
        progress_bar.progress((i + 1) / len(tickers))
    
    if results:
        st.success(f"找到 {len(results)} 檔符合條件")
        st.table(pd.DataFrame(results))
    else:
        st.warning("目前清單中沒有股票符合所有條件。您可以嘗試調低左側的『成交量倍數』。")
