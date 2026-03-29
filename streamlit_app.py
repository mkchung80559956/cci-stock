import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 頁面配置
st.set_page_config(page_title="台股趨勢分析系統", layout="wide")

# 標題
st.title("🏹 台股順勢交易選股器 (中文強化版)")

# --- 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    mode = st.radio("掃描模式", ["熱門權值股", "自訂代碼"])
    vol_ratio = st.slider("成交量倍數", 0.5, 2.0, 1.1)
    cci_p = st.number_input("CCI 週期", 10, 40, 14)

# 初始股票清單
popular_list = ["2330", "2317", "2454", "2603", "2609", "3231", "2382", "1513", "1503", "2303", "2618", "2610"]
if mode == "自訂代碼":
    user_input = st.text_area("輸入代碼 (逗號隔開)", "2330, 2317, 2454")
    stocks_to_scan = [s.strip() for s in user_input.split(",") if s.strip()]
else:
    stocks_to_scan = popular_list

# --- 執行按鈕 ---
if st.button("🚀 執行全市場掃描"):
    all_results = []
    progress_bar = st.progress(0)
    
    for i, t in enumerate(stocks_to_scan):
        try:
            pure_t = t.split('.')[0].strip()
            # 同時嘗試上市與上櫃
            ticker_obj = yf.Ticker(f"{pure_t}.TW")
            df = ticker_obj.history(period="7mo", interval="1d")
            
            if df.empty or len(df) < 40:
                ticker_obj = yf.Ticker(f"{pure_t}.TWO")
                df = ticker_obj.history(period="7mo", interval="1d")
            
            if not df.empty and len(df) >= cci_p + 5:
                # 數據清理
                df.columns = [c.capitalize() for c in df.columns] # 統一欄位名稱
                close = df['Close'].ffill().astype(float)
                high = df['High'].ffill().astype(float)
                low = df['Low'].ffill().astype(float)
                volume = df['Volume'].ffill().astype(float)

                # 指標計算
                cci = ta.cci(high, low, close, length=cci_p)
                vol_ma5 = volume.rolling(window=5).mean()
                
                c_cci, p_cci = cci.iloc[-1], cci.iloc[-2]
                c_vol, a_vol = volume.iloc[-1], vol_ma5.iloc[-1]

                # 趨勢天數
                curr_sign = 1 if c_cci >= 0 else -1
                duration = 0
                for j in range(len(cci)-1, -1, -1):
                    if (1 if cci.iloc[j] >= 0 else -1) == curr_sign:
                        duration += 1
                    else:
                        break
                
                # 抓取中文名稱 (從 Metadata 或 yf 獲取)
                stock_name = ticker_obj.info.get('shortName', pure_t)

                all_results.append({
                    "代碼": pure_t,
                    "名稱": stock_name,
                    "收盤價": round(close.iloc[-1], 2),
                    "CCI方向": "⬆️ 轉強" if c_cci > p_cci else "⬇️ 轉弱",
                    "CCI數值": round(np.clip(c_cci, -250, 250), 2),
                    "趨勢": f"{'多頭' if curr_sign==1 else '空頭'}({duration}天)",
                    "成交量比": round(c_vol / a_vol, 2),
                    "符合買進": (p_cci < 0 and c_cci > 0 and c_vol > a_vol * vol_ratio),
                    "raw_df": df,
                    "raw_cci": cci
                })
        except Exception as e:
            continue
        progress_bar.progress((i + 1) / len(stocks_to_scan))
    
    if all_results:
        st.session_state['results'] = all_results
    else:
        st.warning("目前沒有符合條件的數據，請檢查代碼。")

# --- 顯示結果與圖表 ---
if 'results' in st.session_state:
    data_list = st.session_state['results']
    # 建立顯示用 DataFrame
    df_display = pd.DataFrame(data_list).drop(columns=['raw_df', 'raw_cci'])
    
    # 樣式定義
    def style_df(v):
        if v == "⬆️ 轉強": return 'color: red; font-weight: bold'
        if v == True: return 'background-color: #FF4B4B; color: white'
        return ''

    st.subheader("📊 掃描清單 (點選下方下拉選單查看圖表)")
    st.dataframe(df_display.style.applymap(style_df), use_container_width=True)

    st.divider()
    
    # 圖表選單 (代碼 + 名稱)
    options = [f"{d['代碼']} - {d['名稱']}" for d in data_list]
    selected_option = st.selectbox("🎯 選擇欲查看的技術圖表", options)
    
    # 找出對應資料
    target_code = selected_option.split(" - ")[0]
    selected = next(item for item in data_list if item["代碼"] == target_code)
    
    df_p = selected['raw_df'].tail(60)
    cci_p = selected['raw_cci'].tail(60)

    # 圖表強化
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                       vertical_spacing=0.1, row_heights=[0.6, 0.4],
                       subplot_titles=(f"{selected_option} K線圖", "CCI 指標 (0軸為強弱關鍵)"))

    fig.add_trace(go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], 
                               low=df_p['Low'], close=df_p['Close'], name="K線"), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df_p.index, y=cci_p, name="CCI", line=dict(color='orange', width=2.5)), row=2, col=1)
    
    # 方向強化輔助線
    fig.add_hline(y=0, line_dash="dash", line_color="red", line_width=2, row=2, col=1)
    fig.add_hline(y=100, line_dash="dot", line_color="rgba(255, 255, 255, 0.3)", row=2, col=1)
    fig.add_hline(y=-100, line_dash="dot", line_color="rgba(255, 255, 255, 0.3)", row=2, col=1)

    fig.update_layout(height=750, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
