import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from ta.trend import EMAIndicator, ADXIndicator
from ta.volatility import AverageTrueRange
import datetime
from streamlit_autorefresh import st_autorefresh

# ─────────────────────────────────────────────
# CONFIG TELEGRAM
# ─────────────────────────────────────────────
TOKEN_TELEGRAM = "8150058407:AAFg44ySihFKBO1UW69QZqi07otqeB2IK5s"
CHAT_ID = "1148025596"

def send_telegram_msg(message):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage",
            params={"chat_id": CHAT_ID, "text": message},
            timeout=10
        )
    except:
        pass

# ─────────────────────────────────────────────
# CONFIG INTERFACE
# ─────────────────────────────────────────────
st.set_page_config(page_title="Sniper V16.3 — Swing Forex PRO", layout="wide")
st_autorefresh(interval=180000, key="refresh")  # 3 minutes

if "previous_signals" not in st.session_state:
    st.session_state["previous_signals"] = {}

# ─────────────────────────────────────────────
# ACTIFS
# ─────────────────────────────────────────────
ASSETS = {
    "FOREX": [
        "EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","USDCHF=X","NZDUSD=X",
        "EURGBP=X","EURJPY=X","GBPJPY=X","EURAUD=X","EURCAD=X","EURCHF=X","EURNZD=X",
        "GBPAUD=X","GBPCAD=X","GBPCHF=X","GBPNZD=X",
        "AUDJPY=X","AUDCAD=X","AUDCHF=X","AUDNZD=X",
        "CADJPY=X","CADCHF=X","CHFJPY=X",
        "NZDJPY=X","NZDCAD=X","NZDCHF=X"
    ],
    "MATIÈRES PREMIÈRES": ["GC=F","SI=F","CL=F","HG=F"]
}

# ─────────────────────────────────────────────
# MOTEUR PRINCIPAL
# ─────────────────────────────────────────────
@st.cache_data(ttl=170)
def run_engine():
    results = []
    tickers = [t for cat in ASSETS.values() for t in cat]

    try:
        data_m15 = yf.download(tickers, period="5d", interval="15m", group_by="ticker", progress=False)
        data_h1  = yf.download(tickers, period="21d", interval="1h", group_by="ticker", progress=False)
        data_h4  = yf.download(tickers, period="60d", interval="4h", group_by="ticker", progress=False)
        data_d1  = yf.download(tickers, period="200d", interval="1d", group_by="ticker", progress=False)
    except:
        return []

    new_signals = {}

    for category, symbols in ASSETS.items():
        for ticker in symbols:
            try:
                if ticker not in data_m15.columns.levels[0]:
                    continue

                df_m15 = data_m15[ticker].dropna()
                df_h1  = data_h1[ticker].dropna()
                df_h4  = data_h4[ticker].dropna()
                df_d1  = data_d1[ticker].dropna()

                if len(df_h1) < 50 or len(df_h4) < 50 or len(df_d1) < 200:
                    continue

                # ───── PRIX & VOLATILITÉ ─────
                close = float(df_m15["Close"].iloc[-1])
                atr_m = AverageTrueRange(
                    df_m15["High"], df_m15["Low"], df_m15["Close"], 14
                ).average_true_range().iloc[-1]

                ema200_d = EMAIndicator(df_d1["Close"], 200).ema_indicator().iloc[-1]
                ema50_h1 = EMAIndicator(df_h1["Close"], 50).ema_indicator().iloc[-1]

                # ───── BOX 15M (CLÔTURE OBLIGATOIRE) ─────
                box_high = df_m15["High"].iloc[-21:-1].max()
                box_low  = df_m15["Low"].iloc[-21:-1].min()
                buffer = atr_m * 0.15

                breakout_up = close > (box_high + buffer)
                breakout_dn = close < (box_low  - buffer)

                # ───── ADX MULTI-TF ─────
                adx_d = ADXIndicator(
                    df_d1["High"], df_d1["Low"], df_d1["Close"], 14
                ).adx().iloc[-1]

                adx_h4 = ADXIndicator(
                    df_h4["High"], df_h4["Low"], df_h4["Close"], 14
                ).adx().iloc[-1]

                adx_m = ADXIndicator(
                    df_m15["High"], df_m15["Low"], df_m15["Close"], 14
                )
                adx_val = adx_m.adx().iloc[-1]
                p_di = adx_m.adx_pos().iloc[-1]
                m_di = adx_m.adx_neg().iloc[-1]

                # ───── FILTRE RANGE CRITIQUE ─────
                if adx_d < 18 or adx_h4 < 20:
                    continue

                # ───── CONFIRMATION H1 OBLIGATOIRE ─────
                h1_bull_ok = close > ema50_h1
                h1_bear_ok = close < ema50_h1

                trend_up = close > ema200_d

                score = 0
                signal, sl, tp, note = "ATTENDRE", 0, 0, ""

                # ───── SCORE ASYMÉTRIQUE ─────
                if adx_val > 25:
                    score += 45
                elif adx_val > 20:
                    score += 25

                if trend_up and p_di > m_di and abs(p_di - m_di) > 10:
                    score += 35
                elif not trend_up and m_di > p_di and abs(m_di - p_di) > 10:
                    score += 35

                score += 20 if trend_up == (close > ema200_d) else 0

                # ───── SIGNAL FINAL ─────
                if score >= 70:
                    if trend_up and breakout_up and h1_bull_ok:
                        signal = "ACHAT 🚀"
                        sl = close - (atr_m * 1.6)
                        tp = close + (close - sl) * 2.1

                    elif not trend_up and breakout_dn and h1_bear_ok:
                        signal = "VENTE 🔻"
                        sl = close + (atr_m * 1.6)
                        tp = close - (sl - close) * 2.1
                    else:
                        note = "⏳ Conflit structure H1"

                name = ticker.replace("=X","").replace("=F","").replace("^","")
                new_signals[name] = signal

                # ───── TELEGRAM (CONFIRMATION 2 SCANS) ─────
                if signal != "ATTENDRE":
                    if st.session_state["previous_signals"].get(name) == signal:
                        send_telegram_msg(
                            f"🦅 SIGNAL CONFIRMÉ\n"
                            f"━━━━━━━━━━━━\n"
                            f"{name}\n{signal}\n"
                            f"Prix : {close:.5f}\n"
                            f"SL : {sl:.5f}\nTP : {tp:.5f}"
                        )

                def f(x): return round(x,5) if x < 2 else round(x,2)

                results.append({
                    "Catégorie": category,
                    "Actif": name,
                    "Signal": signal,
                    "Score": f"{score}%",
                    "Prix": f(close),
                    "SL": f(sl) if sl else "-",
                    "TP": f(tp) if tp else "-",
                    "Note": note
                })

            except:
                continue

    st.session_state["previous_signals"] = new_signals
    return results

# ─────────────────────────────────────────────
# AFFICHAGE
# ─────────────────────────────────────────────
st.title("🦅 Sniper V16.3 — Swing Forex PRO")
st.info("Breakout 15m • Confirmation H1 • Filtre Range H4 • Direction Daily")

data = run_engine()

if data:
    df = pd.DataFrame(data)
    st.dataframe(
        df.style.apply(
            lambda x: [
                "background-color:#1e8449;color:white" if "ACHAT" in x.Signal
                else "background-color:#942d22;color:white" if "VENTE" in x.Signal
                else ""
                for _ in x
            ],
            axis=1
        )
    )
else:
    st.warning("Aucun setup valide dans les conditions actuelles.")
