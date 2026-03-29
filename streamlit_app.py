import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

def get_stock_data(ticker):
    pure_ticker = ticker.split('.')[0].strip()
    # 先試上市 (.TW)
    df = yf.download(f"{pure_ticker}.TW", period="6mo", interval="1d", progress=False)
    # 若無數據試上櫃 (.TWO)
    if df.empty or len(df) < 40:
        df = yf.download(f"{pure_ticker}.TWO", period="6mo", interval="1d", progress=False)
    return df

def analyze_stock(df, vol_multiplier):
    if df.empty or len(df) < 40: 
        return None
    
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df['Close'].astype(float).squeeze()
        high = df['High'].astype(float).squeeze()
        low = df['Low'].astype(float).squeeze()
        volume = df['Volume'].astype(float).squeeze()

        # 計算指標
        cci = ta.cci(high, low, close, length=39)
        rsi6 = ta.rsi(close, length=6)
        rsi14 = ta.rsi(close, length=14)
        vol_ma5 = volume.rolling(window=5).mean()

        # 取得最新數值
        c_cci = cci.iloc[-1]
        p_cci = cci.iloc[-2]
        c_rsi6, p_rsi6 = rsi6.iloc[-1], rsi6.iloc[-2]
        c_rsi14, p_rsi14 = rsi14.iloc[-1], rsi14.iloc[-2]
        c_vol = volume.iloc[-1]
        a_vol = vol_ma5.iloc[-1]

        # 判定條件
        cond_cci = p_cci < 0 and c_cci > 0
        cond_rsi = p_rsi6 < p_rsi14 and c_rsi6 > c_rsi14
        cond_vol = c_vol > (a_vol * vol_multiplier)

        status = "🔥 符合" if (cond_cci and cond_rsi and cond_vol) else "未達標"
        
        return {
            "收盤價": round(close.iloc[-1], 2),
            "CCI(39)": round(c_cci, 2),
            "RSI(6)": round(c_rsi6, 2),
            "RSI(14)": round(c_rsi14, 2),
            "成交量比": round(c_vol / a_vol, 2),
            "狀態": status
        }
    except:
        return None

st.title("🚀 台股量價診斷器")

with st.sidebar:
    st.header("參數設定")
    vol_ratio = st.slider("成交量爆量倍數", 0.5, 3.0, 1.0, 0.1)
    # 加入更多熱門股供測試
    default_list = "2330, 2317, 2454, 2603, 2303, 2609, 2618, 3231, 2382, 1513"
    stock_input = st.text_area("輸入代碼 (逗號隔開)", default_list)

if st.button("開始診斷"):
    tickers = [s.strip() for s in stock_input.replace("\n", ",").split(",") if s.strip()]
    all_data = []
    progress_bar = st.progress(0)
    
    for i, t in enumerate(tickers):
        df = get_stock_data(t)
        result = analyze_stock(df, vol_ratio)
        if result:
            result["代碼"] = t
            all_data.append(result)
        progress_bar.progress((i + 1) / len(tickers))
    
    if all_data:
        res_df = pd.DataFrame(all_data).set_index("代碼")
        # 顯示所有掃描過的股票，方便查看指標數值
        st.subheader("全數追蹤清單")
        st.dataframe(res_df.style.applymap(lambda x: 'color: red' if x == "🔥 符合" else '', subset=['狀態']))
        
        # 另外過濾出符合條件的
        matches = res_df[res_df["狀態"] == "🔥 符合"]
        if not matches.empty:
            st.success(f"發現 {len(matches)} 檔符合策略！")
            st.table(matches)
        else:
            st.warning("目前清單中無股票同時滿足：CCI破0、RSI金叉、成交量爆量。")
