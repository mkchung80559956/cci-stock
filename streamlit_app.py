import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

def get_stock_data(ticker):
    # 抓取數據並加上後綴
    try:
        df = yf.download(f"{ticker}.TW", period="6mo", interval="1d")
        if df.empty or len(df) < 40:
            df = yf.download(f"{ticker}.TWO", period="6mo", interval="1d")
        return df
    except:
        return pd.DataFrame()

def check_strategy(df):
    if df is None or len(df) < 40: 
        return False, "數據不足"
    
    try:
        # 強制轉換為 Series 以避免 AttributeError
        close_ser = df['Close'].squeeze()
        high_ser = df['High'].squeeze()
        low_ser = df['Low'].squeeze()
        volume_ser = df['Volume'].squeeze()

        # 計算指標
        cci = ta.cci(high_ser, low_ser, close_ser, length=39)
        rsi6 = ta.rsi(close_ser, length=6)
        rsi14 = ta.rsi(close_ser, length=14)
        vol_ma5 = volume_ser.rolling(window=5).mean()

        # 確保指標計算成功
        if cci is None or rsi6 is None or rsi14 is None:
            return False, "指標計算失敗"

        # 取得最新與前一筆數據
        curr_cci = cci.iloc[-1]
        prev_cci = cci.iloc[-2]
        curr_rsi6, prev_rsi6 = rsi6.iloc[-1], rsi6.iloc[-2]
        curr_rsi14, prev_rsi14 = rsi14.iloc[-1], rsi14.iloc[-2]
        curr_vol = volume_ser.iloc[-1]
        avg_vol = vol_ma5.iloc[-1]

        # 策略邏輯
        cci_breakout = prev_cci < 0 and curr_cci > 0
        rsi_gold_cross = prev_rsi6 < prev_rsi14 and curr_rsi6 > curr_rsi14
        vol_surge = curr_vol > (avg_vol * 2)

        if cci_breakout and rsi_gold_cross and vol_surge:
            return True, "🔥 符合條件"
        return False, "未達標"
    except Exception as e:
        return False, f"計算錯誤: {str(e)}"

# Streamlit UI
st.title("🚀 台股量價動能選股器")
st.sidebar.header("設定")

stock_input = st.sidebar.text_input("輸入股票代碼 (例如: 2330, 2317, 2603)", "2330, 2317, 2454, 2603")
tickers = [s.strip() for s in stock_input.split(",")]

if st.button("開始掃描"):
    results = []
    progress_bar = st.progress(0)
    
    for i, ticker in enumerate(tickers):
        df = get_stock_data(ticker)
        if not df.empty:
            is_match, reason = check_strategy(df)
            if is_match:
                results.append({
                    "股票": ticker, 
                    "狀態": reason, 
                    "目前價格": round(float(df['Close'].iloc[-1]), 2),
                    "成交量": int(df['Volume'].iloc[-1])
                })
        progress_bar.progress((i + 1) / len(tickers))
    
    if results:
        st.success(f"掃描完成！找到 {len(results)} 檔符合條件")
        st.table(pd.DataFrame(results))
    else:
        st.info("目前清單中沒有股票符合條件。")
