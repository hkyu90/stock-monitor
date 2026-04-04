"""
기술적 지표 계산 모듈
ta 라이브러리 기반 — RSI, MACD, 볼린저밴드, 이동평균, 스토캐스틱
"""

import pandas as pd
import numpy as np
import ta


def compute_all(df: pd.DataFrame, config: dict) -> dict:
    """OHLCV DataFrame으로부터 모든 기술적 지표 계산 → 점수 딕셔너리 반환"""
    if df.empty or len(df) < 30:
        return {"score": 0, "details": {}, "signals": []}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    details = {}
    signals = []

    # --- RSI ---
    cfg_rsi = config["rsi"]
    rsi_val = ta.momentum.RSIIndicator(close, window=cfg_rsi["period"]).rsi().iloc[-1]
    if pd.isna(rsi_val):
        rsi_score = 50
    elif rsi_val <= cfg_rsi["oversold"]:
        rsi_score = 90 + (cfg_rsi["oversold"] - rsi_val)  # 과매도일수록 높은 점수
        signals.append(f"RSI 과매도 ({rsi_val:.1f})")
    elif rsi_val >= cfg_rsi["overbought"]:
        rsi_score = max(0, 30 - (rsi_val - cfg_rsi["overbought"]))
        signals.append(f"RSI 과매수 ({rsi_val:.1f})")
    else:
        rsi_score = 50 + (50 - rsi_val) * 0.5  # 중립 구간
    rsi_score = np.clip(rsi_score, 0, 100)
    details["rsi"] = {"value": round(rsi_val, 2), "score": round(rsi_score, 1)}

    # --- MACD ---
    cfg_macd = config["macd"]
    macd_ind = ta.trend.MACD(
        close, window_slow=cfg_macd["slow"],
        window_fast=cfg_macd["fast"], window_sign=cfg_macd["signal"]
    )
    macd_line = macd_ind.macd().iloc[-1]
    macd_signal = macd_ind.macd_signal().iloc[-1]
    macd_hist = macd_ind.macd_diff().iloc[-1]
    macd_hist_prev = macd_ind.macd_diff().iloc[-2] if len(macd_ind.macd_diff()) > 1 else 0

    if pd.isna(macd_line):
        macd_score = 50
    else:
        macd_score = 50
        if macd_hist > 0 and macd_hist_prev <= 0:
            macd_score = 85
            signals.append("MACD 골든크로스")
        elif macd_hist < 0 and macd_hist_prev >= 0:
            macd_score = 15
            signals.append("MACD 데드크로스")
        elif macd_hist > 0:
            macd_score = 60 + min(25, abs(macd_hist) * 10)
        else:
            macd_score = 40 - min(25, abs(macd_hist) * 10)
    macd_score = np.clip(macd_score, 0, 100)
    details["macd"] = {"value": round(macd_line, 4) if not pd.isna(macd_line) else 0, "score": round(macd_score, 1)}

    # --- 볼린저 밴드 ---
    cfg_bb = config["bollinger"]
    bb = ta.volatility.BollingerBands(close, window=cfg_bb["period"], window_dev=cfg_bb["std_dev"])
    bb_high = bb.bollinger_hband().iloc[-1]
    bb_low = bb.bollinger_lband().iloc[-1]
    bb_mid = bb.bollinger_mavg().iloc[-1]
    current_price = close.iloc[-1]

    if pd.isna(bb_low) or bb_high == bb_low:
        bb_score = 50
    else:
        bb_position = (current_price - bb_low) / (bb_high - bb_low)
        if bb_position <= 0.1:
            bb_score = 85
            signals.append("볼린저 하단 이탈/근접")
        elif bb_position >= 0.9:
            bb_score = 20
            signals.append("볼린저 상단 근접")
        else:
            bb_score = 70 - (bb_position * 50)
    bb_score = np.clip(bb_score, 0, 100)
    details["bollinger"] = {"position": round(bb_position if not pd.isna(bb_low) else 0.5, 3), "score": round(bb_score, 1)}

    # --- 이동평균선 ---
    cfg_ma = config["moving_avg"]
    ma_short = close.rolling(cfg_ma["short"]).mean().iloc[-1]
    ma_mid = close.rolling(cfg_ma["mid"]).mean().iloc[-1]
    ma_long = close.rolling(cfg_ma["long"]).mean().iloc[-1] if len(close) >= cfg_ma["long"] else None

    ma_score = 50
    if not pd.isna(ma_short) and not pd.isna(ma_mid):
        if current_price > ma_short > ma_mid:
            ma_score = 75
            if ma_long and ma_mid > ma_long:
                ma_score = 90
                signals.append("정배열 (단기>중기>장기)")
        elif current_price < ma_short < ma_mid:
            ma_score = 25
            if ma_long and ma_mid < ma_long:
                ma_score = 10
                signals.append("역배열 (장기>중기>단기)")

        # 골든크로스 / 데드크로스 확인
        ma_short_prev = close.rolling(cfg_ma["short"]).mean().iloc[-2]
        ma_mid_prev = close.rolling(cfg_ma["mid"]).mean().iloc[-2]
        if not pd.isna(ma_short_prev) and not pd.isna(ma_mid_prev):
            if ma_short > ma_mid and ma_short_prev <= ma_mid_prev:
                ma_score = min(ma_score + 15, 100)
                signals.append(f"MA 골든크로스 ({cfg_ma['short']}/{cfg_ma['mid']})")
            elif ma_short < ma_mid and ma_short_prev >= ma_mid_prev:
                ma_score = max(ma_score - 15, 0)
                signals.append(f"MA 데드크로스 ({cfg_ma['short']}/{cfg_ma['mid']})")

    details["moving_avg"] = {"score": round(ma_score, 1)}

    # --- 거래량 ---
    cfg_vol = config["volume"]
    vol_avg_20 = volume.rolling(20).mean().iloc[-1]
    vol_current = volume.iloc[-1]

    if pd.isna(vol_avg_20) or vol_avg_20 == 0:
        vol_score = 50
    else:
        vol_ratio = vol_current / vol_avg_20
        price_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] if len(close) > 1 else 0

        if vol_ratio >= cfg_vol["surge_threshold"] and price_change > 0:
            vol_score = 85
            signals.append(f"거래량 급증 ({vol_ratio:.1f}배) + 양봉")
        elif vol_ratio >= cfg_vol["surge_threshold"] and price_change < 0:
            vol_score = 25
            signals.append(f"거래량 급증 ({vol_ratio:.1f}배) + 음봉")
        else:
            vol_score = 50 + (vol_ratio - 1) * 15
    vol_score = np.clip(vol_score, 0, 100)
    details["volume"] = {"ratio": round(vol_ratio if not pd.isna(vol_avg_20) and vol_avg_20 > 0 else 1, 2), "score": round(vol_score, 1)}

    # --- 스토캐스틱 ---
    cfg_stoch = config["stochastic"]
    stoch = ta.momentum.StochasticOscillator(
        high, low, close,
        window=cfg_stoch["k_period"], smooth_window=cfg_stoch["d_period"]
    )
    k_val = stoch.stoch().iloc[-1]
    d_val = stoch.stoch_signal().iloc[-1]

    if pd.isna(k_val):
        stoch_score = 50
    elif k_val <= cfg_stoch["oversold"]:
        stoch_score = 80
        signals.append(f"스토캐스틱 과매도 (%K={k_val:.1f})")
    elif k_val >= cfg_stoch["overbought"]:
        stoch_score = 20
    else:
        stoch_score = 50 + (50 - k_val) * 0.6
    stoch_score = np.clip(stoch_score, 0, 100)
    details["stochastic"] = {"k": round(k_val, 2) if not pd.isna(k_val) else 0, "score": round(stoch_score, 1)}

    # --- 가중 합산 ---
    weights = {
        "rsi": cfg_rsi["weight"],
        "macd": cfg_macd["weight"],
        "bollinger": cfg_bb["weight"],
        "moving_avg": cfg_ma["weight"],
        "volume": cfg_vol["weight"],
        "stochastic": cfg_stoch["weight"],
    }
    total = sum(details[k]["score"] * weights[k] for k in weights)

    return {
        "score": round(total, 1),
        "details": details,
        "signals": signals,
        "price": round(current_price, 2),
    }
