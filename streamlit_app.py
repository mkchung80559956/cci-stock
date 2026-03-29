import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np

# 頁面配置
st.set_page_config(page_title="台股順勢交易選股器", layout="wide")

def get_stock_data(ticker):
    pure_ticker = ticker.split('.')[0].strip()
    try:
        df = yf.download(f"{pure_ticker}.TW", period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 50:
            df = yf.download(f"{pure_ticker}.TWO", period="6mo", interval="1d", progress=False)
        return df
    except:
        return pd.DataFrame()

def analyze_stock(df, vol_multiplier, cci_len):
    if df.empty or len(df) < cci_len + 10: 
        return None
    
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 數據清理與轉換
        close = df['Close'].ffill().astype(float).squeeze()
        high = df['High'].ffill().astype(float).squeeze()
        low = df['Low'].ffill().astype(float).squeeze()
        volume = df['Volume'].ffill().astype(float).squeeze()

        # 計算指標
        cci = ta.cci(high, low, close, length=cci_len)
        rsi6 = ta.rsi(close, length=6)
        rsi14 = ta.rsi(close, length=14)
        vol_ma5 = volume.rolling(window=5).mean()

        # 取得最新值與前值
        c_cci, p_cci = cci.iloc[-1], cci.iloc[-2]
        c_rsi6, p_rsi6 = rsi6.iloc[-1], rsi6.iloc[-2]
        c_rsi14, p_rsi14 = rsi14.iloc[-1], rsi14.iloc[-2]
        c_vol, a_vol = volume.iloc[-1], vol_ma5.iloc[-1]

        # --- 處理 CCI 不符常理的數值 ---
        # 若分母太小導致數值爆炸，我們將其限制在 ±200 之間（這是技術分析最有意義的區間）
        display_cci = np.clip(c_cci, -200, 200)

        # --- 判定方向 ---
        cci_direction = "⬆️ 轉強" if c_cci > p_cci else "⬇️ 轉弱"
        
        # 買進策略判定
        cond_cci = p_cci < 0 and c_cci > 0
        cond_rsi = p_rsi6 < p_rsi14 and c_rsi6 > c_rsi14
        cond_vol = c_vol > (a_vol * vol_multiplier)

        status = "🔥 符合買進" if (cond_cci and cond_rsi and cond_vol) else "觀察中"
        
        return {
            "日期": df.index[-1].strftime('%Y-%m-%d'),
            "收盤價": round(close.iloc[-1], 2),
            "CCI方向": cci_direction,
            "CCI數值": round(display_cci, 2),
            "RSI狀態": "金叉" if c_rsi6 > c_rsi14 else "死叉",
            "成交量比": round(c_vol / a_vol, 2),
            "綜合狀態": status
        }
    except:
        return None

# --- UI ---
st.title("🏹 台股順勢交易選股器")
st.info("本系統已自動修正 CCI 異常數值，專注於『動能突破』與『量價配合』。")

with st.sidebar:
    st.header("參數調整")
    mode = st.radio("掃描範圍", ["熱門權值股", "手動輸入"])
    vol_target = st.slider("成交量爆量倍數", 0.5, 2.0, 1.1, 0.1)
    cci_window = st.number_input("CCI 週期", 10, 40, 14)

popular_list = ["2330", "2317", "2454", "2603", "2609", "3231", "2382", "1513", "1503", "2303"]

if st.button("🚀 執行診斷"):
    tickers = popular_list if mode == "熱門權值股" else st.text_area("代碼").split(",")
    all_res = []
    
    for t in tickers:
        data = get_stock_data(t.strip())
        res = analyze_stock(data, vol_target, cci_window)
        if res:
            res["代碼"] = t.strip()
            all_res.append(res)
            
    if all_res:
        res_df = pd.DataFrame(all_res).set_index("代碼")
        
        # 顯示符合的股票
        buy_signals = res_df[res_df["綜合狀態"] == "🔥 符合買進"]
        if not buy_signals.empty:
            st.success("🎯 發現趨勢啟動個股！")
            st.table(buy_signals)
        
        st.subheader("📊 全市場掃描明細")
        st.dataframe(res_df.style.applymap(
            lambda x: 'background-color: #ffcccc' if x == "🔥 符合買進" else '',
            subset=['綜合狀態']
        ), use_container_width=True)
