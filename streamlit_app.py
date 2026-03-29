import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

def get_stock_data(ticker):
    # 抓取近半年的數據以計算指標
    df = yf.download(f"{ticker}.TW", period="6mo", interval="1d")
    if df.empty:
        df = yf.download(f"{ticker}.TWO", period="6mo", interval="1d")
    return df

def check_strategy(df):
    if len(df) < 40: return False, "數據不足"
    
    # 計算指標
    # CCI (39)
    cci = ta.cci(df['High'], df['Low'], df['Close'], length=39)
    # RSI (6, 14)
    rsi6 = ta.rsi(df['Close'], length=6)
    rsi14 = ta.rsi(df['Close'], length=14)
    # 成交量均線 (5日)
    vol_ma5 = df['Volume'].rolling(window=5).mean()

    # 取得最新兩筆數據判斷交叉
    curr_cci = cci.iloc[-1]
    prev_cci = cci.iloc[-2]
    curr_rsi6, prev_rsi6 = rsi6.iloc[-1], rsi6.iloc[-2]
    curr_rsi14, prev_rsi14 = rsi14.iloc[-1], rsi14.iloc[-2]
    curr_vol = df['Volume'].iloc[-1]
    avg_vol = vol_ma5.iloc[-1]

    # 判斷條件
    cci_breakout = prev_cci < 0 and curr_cci > 0
    rsi_gold_cross = prev_rsi6 < prev_rsi14 and curr_rsi6 > curr_rsi14
    vol_surge = curr_vol > (avg_vol * 2)

    if cci_breakout and rsi_gold_cross and vol_surge:
        return True, "符合條件"
    return False, "未達標"

# Streamlit 介面
st.title("🚀 台股量價動能選股器")
st.sidebar.header("設定")

stock_input = st.sidebar.text_input("輸入股票代碼 (多檔請用逗號隔開)", "2330, 2317, 2454, 2603")
tickers = [s.strip() for s in stock_input.split(",")]

if st.button("開始掃描"):
    results = []
    progress_bar = st.progress(0)
    
    for i, ticker in enumerate(tickers):
        with st.spinner(f"正在分析 {ticker}..."):
            df = get_stock_data(ticker)
            if not df.empty:
                is_match, reason = check_strategy(df)
                if is_match:
                    results.append({"股票代碼": ticker, "狀態": "🔥 符合策略", "收盤價": round(df['Close'].iloc[-1], 2)})
            progress_bar.progress((i + 1) / len(tickers))
    
    if results:
        st.success(f"掃描完成！找到 {len(results)} 檔符合條件的股票")
        st.table(pd.DataFrame(results))
    else:
        st.info("目前沒有股票符合此篩選條件。")