import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# 設定頁面標題與圖示
st.set_page_config(page_title="台股動能選股器", layout="wide")

def get_stock_data(ticker):
    pure_ticker = ticker.split('.')[0].strip()
    # 嘗試上市代碼
    df = yf.download(f"{pure_ticker}.TW", period="6mo", interval="1d", progress=False)
    # 若無數據試上櫃
    if df.empty or len(df) < 40:
        df = yf.download(f"{pure_ticker}.TWO", period="6mo", interval="1d", progress=False)
    return df

def analyze_stock(df, vol_multiplier, cci_len):
    if df.empty or len(df) < 40: 
        return None
    
    try:
        # 處理 yfinance 多重索引
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df['Close'].astype(float).squeeze()
        high = df['High'].astype(float).squeeze()
        low = df['Low'].astype(float).squeeze()
        volume = df['Volume'].astype(float).squeeze()

        # 計算指標：使用動態傳入的 cci_len
        cci = ta.cci(high, low, close, length=cci_len)
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
        cond_cci = p_cci < 0 and c_cci > 0  # CCI 低檔向上突破 0
        cond_rsi = p_rsi6 < p_rsi14 and c_rsi6 > c_rsi14 # RSI 短期上穿長期
        cond_vol = c_vol > (a_vol * vol_multiplier) # 成交量大於均量

        status = "🔥 符合" if (cond_cci and cond_rsi and cond_vol) else "未達標"
        
        return {
            "收盤價": round(close.iloc[-1], 2),
            "CCI": round(c_cci, 2),
            "RSI(6)": round(c_rsi6, 2),
            "RSI(14)": round(c_rsi14, 2),
            "成交量比": round(c_vol / a_vol, 2),
            "狀態": status
        }
    except:
        return None

# --- UI 介面 ---
st.title("📈 台股量價策略選股系統")
st.markdown("策略邏輯：`CCI 突破 0` + `RSI 黃金交叉` + `成交量爆量` ")

# 常用熱門股清單 (包含半導體、航運、AI、重電)
popular_stocks = [
    "2330", "2317", "2454", "2303", "2603", "2609", "2618", "3231", "2382", 
    "1513", "1503", "2376", "2353", "2408", "3037", "3711", "2324", "2610", "2615", "6235"
]

with st.sidebar:
    st.header("⚙️ 參數設定")
    mode = st.radio("掃描模式", ["自動掃描熱門股", "手動輸入代碼"])
    
    if mode == "手動輸入代碼":
        stock_input = st.text_area("輸入代碼 (逗號隔開)", "2330, 2317, 2454")
    
    st.divider()
    cci_length = st.number_input("CCI 週期 (建議 14 或 20)", value=14)
    vol_ratio = st.slider("成交量爆量倍數", 0.5, 3.0, 1.1, 0.1)

if st.button("🚀 開始掃描市場"):
    if mode == "自動掃描熱門股":
        tickers = popular_stocks
    else:
        tickers = [s.strip() for s in stock_input.replace("\n", ",").split(",") if s.strip()]
    
    all_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, t in enumerate(tickers):
        status_text.text(f"正在分析: {t}...")
        df = get_stock_data(t)
        result = analyze_stock(df, vol_ratio, cci_length)
        if result:
            result["代碼"] = t
            all_data.append(result)
        progress_bar.progress((i + 1) / len(tickers))
    
    status_text.text("掃描完成！")
    
    if all_data:
        res_df = pd.DataFrame(all_data).set_index("代碼")
        
        # 過濾符合的股票
        matches = res_df[res_df["狀態"] == "🔥 符合"]
        
        if not matches.empty:
            st.balloons()
            st.success(f"找到 {len(matches)} 檔符合策略的股票！")
            st.table(matches)
        else:
            st.warning("目前沒有股票同時符合所有條件。")
            
        st.subheader("🔍 詳細診斷清單 (所有掃描股票)")
        st.dataframe(res_df, use_container_width=True)
    else:
        st.error("無法取得任何數據，請檢查網路或代碼格式。")
