"""
모멘텀 & 센티먼트 지표 모듈
52주 포지션, 섹터 상대강도, 외국인/기관 수급
"""

import numpy as np
import pandas as pd


def compute_week52_position(df: pd.DataFrame) -> dict:
    """52주 신고가/신저가 대비 현재 위치"""
    if df.empty or len(df) < 20:
        return {"position": 0.5, "score": 50, "signals": []}

    close = df["close"]
    high_52 = close.rolling(min(252, len(close))).max().iloc[-1]
    low_52 = close.rolling(min(252, len(close))).min().iloc[-1]
    current = close.iloc[-1]

    if high_52 == low_52:
        return {"position": 0.5, "score": 50, "signals": []}

    position = (current - low_52) / (high_52 - low_52)
    signals = []

    if position <= 0.3:
        score = 80
        signals.append(f"52주 저점 근처 ({position:.0%})")
    elif position <= 0.5:
        score = 65
    elif position <= 0.7:
        score = 50
    elif position <= 0.9:
        score = 35
    else:
        score = 20
        signals.append(f"52주 고점 근처 ({position:.0%})")

    return {
        "position": round(position, 3),
        "high_52w": round(high_52, 2),
        "low_52w": round(low_52, 2),
        "score": score,
        "signals": signals,
    }


def compute_price_momentum(df: pd.DataFrame) -> dict:
    """다기간 수익률 모멘텀"""
    if df.empty or len(df) < 5:
        return {"score": 50, "signals": []}

    close = df["close"]
    current = close.iloc[-1]
    signals = []

    returns = {}
    for label, days in [("1w", 5), ("1m", 20), ("3m", 60), ("6m", 120)]:
        if len(close) > days:
            ret = (current / close.iloc[-days - 1] - 1) * 100
            returns[label] = round(ret, 2)

    # 중기 모멘텀: 1~3개월 수익률 중시
    scores = []
    if "1m" in returns:
        r = returns["1m"]
        s = 50 + min(30, max(-30, r * 2))
        scores.append(s)
    if "3m" in returns:
        r = returns["3m"]
        s = 50 + min(30, max(-30, r * 1))
        scores.append(s)

    if not scores:
        return {"score": 50, "returns": returns, "signals": signals}

    avg_score = np.mean(scores)

    if returns.get("1m", 0) > 10:
        signals.append(f"1개월 +{returns['1m']:.1f}% 강세")
    elif returns.get("1m", 0) < -10:
        signals.append(f"1개월 {returns['1m']:.1f}% 약세")

    return {
        "score": round(np.clip(avg_score, 0, 100), 1),
        "returns": returns,
        "signals": signals,
    }


def compute_all(df: pd.DataFrame, investor_data: pd.DataFrame | None, config: dict) -> dict:
    """모멘텀 종합 점수"""
    w52 = compute_week52_position(df)
    price_mom = compute_price_momentum(df)

    signals = w52.get("signals", []) + price_mom.get("signals", [])

    # 외국인/기관 수급 (한국 시장만)
    inst_score = 50
    if investor_data is not None and not investor_data.empty:
        try:
            recent = investor_data.tail(config["institutional_flow"]["lookback_days"])
            if "기관합계" in recent.columns:
                inst_net = recent["기관합계"].sum()
                foreign_net = recent.get("외국인합계", pd.Series([0])).sum()
                total_flow = inst_net + foreign_net
                if total_flow > 0:
                    inst_score = 65 + min(25, abs(total_flow) / 1e9)
                    signals.append("기관/외국인 순매수")
                else:
                    inst_score = 35 - min(25, abs(total_flow) / 1e9)
                    signals.append("기관/외국인 순매도")
                inst_score = np.clip(inst_score, 0, 100)
        except Exception:
            pass

    weights = config["week52_position"]["weight"]
    weights_sector = config["sector_relative_strength"]["weight"]
    weights_inst = config["institutional_flow"]["weight"]

    # 섹터 상대강도는 price momentum으로 대체
    total = (
        w52["score"] * weights
        + price_mom["score"] * weights_sector
        + inst_score * weights_inst
    )

    return {
        "score": round(total, 1),
        "week52": w52,
        "price_momentum": price_mom,
        "institutional_score": round(inst_score, 1),
        "signals": signals,
    }
