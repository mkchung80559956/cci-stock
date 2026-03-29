import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime

# 頁面基本設定
st.set_page_config(page_title="台股量價策略選股器", layout="wide")

def get_stock_data(ticker):
    """抓取台股數據，自動嘗試上市(.TW)與上櫃(.TWO)格式"""
    pure_ticker = ticker.split('.')[0].strip()
    try:
        # 抓取 6 個月日線數據
        df = yf.download(f"{pure_ticker}.TW", period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 40:
            df = yf.download(f"{pure_ticker}.TWO", period="6mo", interval="1d", progress=False)
        return df
    except:
        return pd.DataFrame()

def analyze_stock(df, vol_multiplier, cci_len):
    """執行策略核心邏輯"""
    if df.empty or len(df) < 40: 
        return None
    
    try:
        # 排除 yfinance 新版可能產生的 MultiIndex 問題
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df['Close'].astype(float).squeeze()
        high = df['High'].astype(float).squeeze()
        low = df['Low'].astype(float).squeeze()
        volume = df['Volume'].astype(float).squeeze()

        # 計算指標
        cci = ta.cci(high, low, close, length=cci_len)
        rsi6 = ta.rsi(close, length=6)
        rsi14 = ta.rsi(close, length=14)
        vol_ma5 = volume.rolling(window=5).mean()

        # 取得最新兩日數據以判斷交叉與突破
        c_cci, p_cci = cci.iloc[-1], cci.iloc[-2]
        c_rsi6, p_rsi6 = rsi6.iloc[-1], rsi6.iloc[-2]
        c_rsi14, p_rsi14 = rsi14.iloc[-1], rsi14.iloc[-2]
        c_vol, a_vol = volume.iloc[-1], vol_ma5.iloc[-1]
        
        last_date = df.index[-1].strftime('%Y-%m-%d')

        # --- 策略條件判定 ---
        # 1. CCI 突破 0 (由負轉正)
        cond_cci = p_cci < 0 and c_cci > 0
        # 2. RSI 黃金交叉 (6日穿過14日)
        cond_rsi = p_rsi6 < p_rsi14 and c_rsi6 > c_rsi14
        # 3. 成交量爆量 (當日量 > 5日均量 * 倍數)
        cond_vol = c_vol > (a_vol * vol_multiplier)

        status = "🔥 符合" if (cond_cci and cond_rsi and cond_vol) else "未達標"
        
        return {
            "數據日期": last_date,
            "收盤價": round(close.iloc[-1], 2),
            "CCI": round(c_cci, 2),
            "RSI(6)": round(c_rsi6, 2),
            "RSI(14)": round(c_rsi14, 2),
            "成交量比": round(c_vol / a_vol, 2),
            "狀態": status
        }
    except Exception as e:
        return None

# --- Streamlit 介面設計 ---
st.title("🚀 台股買進策略自動選股器")
st.markdown(f"**目前系統時間：** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}` (台北)")

# 熱門權值股清單
popular_list = ["2330", "2317", "2454", "2303", "2603", "2609", "2618", "3231", "2382", "1513", "1503", "2376", "2408", "3711", "3037", "2610", "2615"]

with st.sidebar:
    st.header("⚙️ 核心參數")
    mode = st.radio("掃描模式", ["自動掃描熱門股", "手動輸入代碼"])
    if mode == "手動輸入代碼":
        stock_input = st.text_area("請輸入股票代碼 (逗號隔開)", "2330, 2317, 2454, 2603")
    
    st.divider()
    cci_len = st.number_input("CCI 週期設定 (建議 14-20)", value=14, step=1)
    vol_ratio = st.slider("成交量爆量門檻 (倍)", 0.5, 3.0, 1.1, 0.1)

if st.button("🔍 執行全市場掃描"):
    tickers = popular_list if mode == "自動掃描熱門股" else [s.strip() for s in stock_input.replace("\n", ",").split(",") if s.strip()]
    
    results = []
    progress_bar = st.progress(0)
    msg_slot = st.empty()
    
    for i, t in enumerate(tickers):
        msg_slot.text(f"正在分析 {t}...")
        df_data = get_stock_data(t)
        res = analyze_stock(df_data, vol_ratio, cci_len)
        if res:
            res["代碼"] = t
            results.append(res)
        progress_bar.progress((i + 1) / len(tickers))
    
    msg_slot.empty()
    
    if results:
        res_df = pd.DataFrame(results).set_index("代碼")
        
        # 分類顯示
        matches = res_df[res_df["狀態"] == "🔥 符合"]
        
        if not matches.empty:
            st.balloons()
            st.success(f"🎊 發現 {len(matches)} 檔完全符合訊號的股票！")
            st.table(matches)
        else:
            st.info("💡 目前清單中無完全符合條件的股票，可嘗試降低「成交量倍數」或「CCI週期」。")
        
        st.subheader("📋 所有掃描個股診斷表")
        st.dataframe(res_df.sort_values("CCI", ascending=False), use_container_width=True)
    else:
        st.error("掃描失敗，請確認代碼輸入是否正確。")
