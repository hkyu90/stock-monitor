"""
보유 종목 심층 분석 모듈
단순 가격이 아닌 거시경제 + 기업 펀더멘털 추세 + 기술적 추세 강도를 종합하여
'언제까지 보유할 것인가'에 대한 판단을 내림
"""

import numpy as np
import pandas as pd
import ta


def analyze_hold_decision(
    stock_result: dict,
    ohlcv: pd.DataFrame,
    macro: dict,
    config: dict,
) -> dict:
    """
    보유 종목에 대한 종합 보유/매도 판단

    Returns:
        decision: 보유유지 / 부분매도 / 전량매도 / 추가매수
        reasoning: 판단 근거 리스트
        hold_horizon: 예상 보유 기간
        risk_level: 리스크 수준
        key_factors: 핵심 판단 요인
    """
    avg_price = stock_result.get("avg_price", 0)
    current_price = stock_result.get("price", 0)
    pnl_pct = ((current_price / avg_price) - 1) * 100 if avg_price > 0 else 0

    # === 1. 추세 강도 분석 (ADX) ===
    trend_analysis = _analyze_trend_strength(ohlcv)

    # === 2. 지지/저항선 분석 ===
    support_resistance = _analyze_support_resistance(ohlcv)

    # === 3. 펀더멘털 방향성 (개선 vs 악화) ===
    fund_direction = _analyze_fundamental_direction(stock_result)

    # === 4. 거시경제 환경 반영 ===
    macro_score = macro.get("macro_score", 50)
    macro_outlook = macro.get("macro_outlook", "중립")

    # === 5. 섹터 상대 강도 ===
    sector_strength = _analyze_sector_context(stock_result, macro)

    # === 종합 판단 ===
    factors = {
        "trend": trend_analysis,
        "support_resistance": support_resistance,
        "fundamental_direction": fund_direction,
        "macro": {"score": macro_score, "outlook": macro_outlook},
        "sector": sector_strength,
        "pnl_pct": round(pnl_pct, 1),
    }

    decision, reasoning, hold_horizon, risk_level = _make_decision(
        factors, stock_result, pnl_pct, config
    )

    return {
        "decision": decision,
        "reasoning": reasoning,
        "hold_horizon": hold_horizon,
        "risk_level": risk_level,
        "key_factors": factors,
        "trend": trend_analysis,
        "support_resistance": support_resistance,
    }


def _analyze_trend_strength(df: pd.DataFrame) -> dict:
    """ADX 기반 추세 강도 + 방향 분석"""
    if df.empty or len(df) < 30:
        return {"adx": 0, "strength": "분석 불가", "direction": "불명"}

    high = df["high"]
    low = df["low"]
    close = df["close"]

    adx_ind = ta.trend.ADXIndicator(high, low, close, window=14)
    adx = adx_ind.adx().iloc[-1]
    plus_di = adx_ind.adx_pos().iloc[-1]
    minus_di = adx_ind.adx_neg().iloc[-1]

    if pd.isna(adx):
        return {"adx": 0, "strength": "분석 불가", "direction": "불명"}

    # 추세 강도
    if adx >= 40:
        strength = "매우 강한 추세"
    elif adx >= 25:
        strength = "강한 추세"
    elif adx >= 20:
        strength = "약한 추세"
    else:
        strength = "추세 없음 (횡보)"

    # 추세 방향
    if plus_di > minus_di:
        direction = "상승"
    else:
        direction = "하락"

    # 추세 전환 감지 (최근 5일)
    adx_series = adx_ind.adx()
    plus_series = adx_ind.adx_pos()
    minus_series = adx_ind.adx_neg()

    turning = False
    if len(plus_series) >= 5:
        recent_plus = plus_series.iloc[-5:]
        recent_minus = minus_series.iloc[-5:]
        # 최근 5일간 +DI와 -DI가 교차했는지
        for i in range(1, len(recent_plus)):
            if not pd.isna(recent_plus.iloc[i]) and not pd.isna(recent_minus.iloc[i]):
                prev_diff = recent_plus.iloc[i-1] - recent_minus.iloc[i-1]
                curr_diff = recent_plus.iloc[i] - recent_minus.iloc[i]
                if prev_diff * curr_diff < 0:
                    turning = True
                    break

    return {
        "adx": round(adx, 1),
        "plus_di": round(plus_di, 1),
        "minus_di": round(minus_di, 1),
        "strength": strength,
        "direction": direction,
        "turning": turning,
    }


def _analyze_support_resistance(df: pd.DataFrame) -> dict:
    """지지/저항선 분석"""
    if df.empty or len(df) < 20:
        return {"support": 0, "resistance": 0}

    close = df["close"]
    current = close.iloc[-1]

    # 최근 60일 기준 피봇 포인트
    lookback = min(60, len(df))
    recent = df.tail(lookback)

    high_max = recent["high"].max()
    low_min = recent["low"].min()
    pivot = (high_max + low_min + current) / 3

    support1 = 2 * pivot - high_max
    resistance1 = 2 * pivot - low_min

    # 이동평균선 지지/저항
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(min(60, len(close))).mean().iloc[-1]

    # 현재가 대비 위치
    if current > ma20:
        nearest_support = max(support1, ma20)
        position = "지지선 위"
    else:
        nearest_support = support1
        position = "지지선 아래"

    distance_to_support = ((current - nearest_support) / current) * 100

    return {
        "support": round(nearest_support, 0),
        "resistance": round(resistance1, 0),
        "ma20": round(ma20, 0),
        "ma60": round(ma60, 0),
        "position": position,
        "distance_to_support_pct": round(distance_to_support, 1),
    }


def _analyze_fundamental_direction(stock_result: dict) -> dict:
    """펀더멘털 방향성 분석 (개선 / 유지 / 악화)"""
    fund = stock_result.get("fundamental", {})
    fund_details = fund.get("details", {})

    signals = []
    direction_score = 50  # 중립

    # ROE
    roe_data = fund_details.get("roe", {})
    roe_val = roe_data.get("value")
    if roe_val is not None:
        if roe_val >= 15:
            direction_score += 10
            signals.append(f"ROE {roe_val:.1f}% 양호")
        elif roe_val < 5:
            direction_score -= 10
            signals.append(f"ROE {roe_val:.1f}% 저조")

    # 매출 성장률
    rev_data = fund_details.get("revenue_growth", {})
    rev_val = rev_data.get("value")
    if rev_val is not None:
        if rev_val >= 20:
            direction_score += 15
            signals.append(f"매출 YoY +{rev_val:.0f}% 고성장")
        elif rev_val >= 10:
            direction_score += 5
            signals.append(f"매출 YoY +{rev_val:.0f}% 성장")
        elif rev_val < 0:
            direction_score -= 15
            signals.append(f"매출 YoY {rev_val:.0f}% 역성장")

    # EPS 성장률
    eps_data = fund_details.get("eps_growth", {})
    eps_val = eps_data.get("value")
    if eps_val is not None:
        if eps_val >= 20:
            direction_score += 10
            signals.append(f"EPS YoY +{eps_val:.0f}% 이익 모멘텀")
        elif eps_val < 0:
            direction_score -= 10
            signals.append(f"EPS YoY {eps_val:.0f}% 이익 감소")

    # 영업이익률
    op_data = fund_details.get("operating_margin", {})
    op_val = op_data.get("value")
    if op_val is not None:
        if op_val >= 15:
            direction_score += 5
            signals.append(f"영업이익률 {op_val:.1f}% 우수")
        elif op_val < 0:
            direction_score -= 10
            signals.append(f"영업적자")

    # PER 밸류에이션
    per_data = fund_details.get("per", {})
    per_val = per_data.get("value")
    if per_val is not None and per_val > 0:
        if per_val < 10:
            direction_score += 5
            signals.append(f"PER {per_val:.1f}x 저평가")
        elif per_val > 40:
            direction_score -= 5
            signals.append(f"PER {per_val:.1f}x 고평가")

    direction_score = np.clip(direction_score, 0, 100)

    if direction_score >= 65:
        direction = "개선"
    elif direction_score >= 45:
        direction = "유지"
    else:
        direction = "악화"

    # 폭발적 성장 플래그 (매출 성장률 40%+ 또는 30% + 흑자)
    explosive_growth = False
    if rev_val is not None and rev_val >= 40:
        explosive_growth = True
    elif rev_val is not None and rev_val >= 30 and (op_val is None or op_val >= 0):
        explosive_growth = True

    return {
        "direction": direction,
        "score": round(direction_score, 1),
        "signals": signals,
        "explosive_growth": explosive_growth,
    }


def _analyze_sector_context(stock_result: dict, macro: dict) -> dict:
    """섹터 맥락 분석"""
    market = stock_result.get("market", "")

    if market in ("KOSPI", "KOSDAQ"):
        market_trend = macro.get("kr_market", {})
    else:
        market_trend = macro.get("us_market", {})

    market_score = market_trend.get("trend_score", 50)
    market_direction = market_trend.get("trend", "불명")

    return {
        "market_trend": market_direction,
        "market_score": market_score,
    }


def _make_decision(
    factors: dict,
    stock_result: dict,
    pnl_pct: float,
    config: dict,
) -> tuple:
    """
    종합 보유/매도 판단 (약세장 축적 철학 반영)

    가중치 원칙:
    - 펀더멘털 방향이 최우선 (±4)
    - 추세는 매우 강할 때만 (±3, ADX 30+)
    - 매크로는 보조 (±1, 펀더멘털 강건 시 면제)
    - 지지선 이탈 시 펀더멘털 강건 종목은 '축적 구간'으로 해석
    """
    reasoning = []
    risk_points = 0
    hold_points = 0

    trend = factors["trend"]
    sr = factors["support_resistance"]
    fund_dir = factors["fundamental_direction"]
    macro = factors["macro"]
    sector = factors["sector"]

    fund_score = fund_dir.get("score", 50)
    explosive_growth = fund_dir.get("explosive_growth", False)
    # 펀더멘털 강건 = 방향 스코어 65+ OR 폭발적 성장
    is_strong_fund = fund_score >= 65 or explosive_growth
    dist_support = sr.get("distance_to_support_pct", 0)

    # --- 1. 기업 펀더멘털 방향 (최우선, ±4) ---
    if fund_dir["direction"] == "개선":
        hold_points += 4
        reasoning.append("펀더멘털 개선 중 — " + ", ".join(fund_dir["signals"][:2]))
    elif fund_dir["direction"] == "악화":
        risk_points += 4
        reasoning.append("펀더멘털 악화 — " + ", ".join(fund_dir["signals"][:2]))
    else:
        if fund_dir["signals"]:
            reasoning.append("펀더멘털 유지 — " + ", ".join(fund_dir["signals"][:2]))

    # 폭발적 성장 프리미엄
    if explosive_growth and fund_dir["direction"] != "개선":
        hold_points += 2
        reasoning.append("폭발적 매출성장 → 고성장 프리미엄 적용")

    # --- 2. 거시경제 (±1, 펀더멘털 강건 시 면제) ---
    macro_score = macro["score"]
    if is_strong_fund:
        reasoning.append(f"거시경제 {macro['outlook']} (펀더멘털 강건 → 매크로 영향 제한)")
    elif macro_score >= 60:
        hold_points += 1
        reasoning.append(f"거시경제 {macro['outlook']} — 시장 양호")
    elif macro_score < 40:
        risk_points += 1
        reasoning.append(f"거시경제 {macro['outlook']} — 방어적 운용")
    else:
        reasoning.append(f"거시경제 {macro['outlook']}")

    # --- 3. 추세 강도 & 방향 (±3, ADX 30+에서만 강한 페널티) ---
    if trend["direction"] == "상승" and trend["adx"] >= 25:
        hold_points += 3
        reasoning.append(f"강한 상승추세 지속 (ADX {trend['adx']}) — 추세 따라 보유")
    elif trend["direction"] == "하락" and trend["adx"] >= 30:
        risk_points += 3
        reasoning.append(f"매우 강한 하락추세 (ADX {trend['adx']}) — 추세 전환 전 리스크")
    elif trend["direction"] == "하락" and trend["adx"] >= 25:
        # 강한 하락이지만 "매우 강한"은 아님. 펀더멘털 강건 종목은 완화
        if is_strong_fund:
            risk_points += 1
            reasoning.append(f"강한 하락추세 (ADX {trend['adx']}) — 펀더멘털 강건, 축적 구간 후보")
        else:
            risk_points += 2
            reasoning.append(f"강한 하락추세 (ADX {trend['adx']})")
    elif trend["turning"]:
        reasoning.append("추세 전환 신호 감지 — 주의 관찰")
        risk_points += 1
    else:
        reasoning.append(f"추세 {trend['strength']} ({trend['direction']})")

    # --- 4. 지지/저항선 (±2, 펀더멘털 강건 시 완화) ---
    if sr["position"] == "지지선 아래":
        if is_strong_fund:
            risk_points += 1
            reasoning.append(f"지지선({sr['support']:,.0f}) 이탈 — 펀더멘털 강건 → 축적 구간")
        else:
            risk_points += 2
            reasoning.append(f"지지선({sr['support']:,.0f}) 이탈 — 추가 하락 리스크")
    elif dist_support < 3:
        if is_strong_fund:
            hold_points += 1
            reasoning.append(f"지지선({sr['support']:,.0f}) 근접 — 반등/축적 기회")
        else:
            reasoning.append(f"지지선({sr['support']:,.0f}) 근접 — 반등 가능성")
    else:
        reasoning.append(f"지지선 {sr['support']:,.0f} / 저항선 {sr['resistance']:,.0f}")

    # --- 5. 시장 환경 (±1, 펀더멘털 강건 시 면제) ---
    if sector["market_score"] >= 60:
        hold_points += 1
        reasoning.append(f"시장 {sector['market_trend']}")
    elif sector["market_score"] < 40 and not is_strong_fund:
        risk_points += 1
        reasoning.append(f"시장 {sector['market_trend']} — 전반적 약세")

    # --- 6. 수익률 기반 추가 판단 ---
    if pnl_pct >= 50:
        if trend["direction"] == "상승" and trend["adx"] >= 20:
            hold_points += 1
            reasoning.append(f"수익률 +{pnl_pct:.0f}% + 상승추세 → 트레일링 스탑 권장")
        else:
            risk_points += 2
            reasoning.append(f"수익률 +{pnl_pct:.0f}% 고수익, 추세 약화 → 부분 익절 검토")
    elif pnl_pct >= 20:
        if fund_dir["direction"] == "개선":
            hold_points += 1
            reasoning.append(f"수익률 +{pnl_pct:.0f}% + 펀더멘털 개선 → 보유")
        else:
            reasoning.append(f"수익률 +{pnl_pct:.0f}% — 트레일링 스탑 권장")
    elif pnl_pct <= -30:
        if is_strong_fund:
            hold_points += 2
            reasoning.append(f"손실 {pnl_pct:.0f}%이나 펀더멘털 강건 → 회복 대기/축적")
        elif fund_dir["direction"] == "악화":
            risk_points += 3
            reasoning.append(f"손실 {pnl_pct:.0f}% + 펀더멘털 악화 → 손절 권고")
        else:
            risk_points += 1
            reasoning.append(f"손실 {pnl_pct:.0f}% — 추세 확인 후 판단")
    elif pnl_pct <= -10:
        if is_strong_fund:
            reasoning.append(f"손실 {pnl_pct:.0f}% — 펀더멘털 강건, 축적 구간 후보")
        elif trend["direction"] == "하락" and trend["adx"] >= 25:
            risk_points += 2
            reasoning.append(f"손실 {pnl_pct:.0f}% + 하락추세 → 매도 검토")

    # === 최종 판단 ===
    net_score = hold_points - risk_points

    # 추가매수 구간 조건
    is_accumulation_zone = (
        is_strong_fund
        and (pnl_pct < 0 or dist_support < 5 or sr["position"] == "지지선 아래")
        and not (trend["direction"] == "하락" and trend["adx"] >= 30)
    )

    if net_score >= 5:
        if is_accumulation_zone:
            decision = "추가 매수"
            hold_horizon = "지지선 분할 매수, 12개월+ 보유"
            risk_level = "낮음"
        else:
            decision = "적극 보유"
            hold_horizon = "중장기 보유 (6개월+)"
            risk_level = "낮음"
    elif net_score >= 2:
        if is_accumulation_zone:
            decision = "추가 매수"
            hold_horizon = "지지선 근접 분할 매수 (12개월+)"
            risk_level = "보통"
        else:
            decision = "보유 유지"
            hold_horizon = "2~4주 관찰, 추세 확인"
            risk_level = "보통"
    elif net_score >= -1:
        decision = "관망"
        hold_horizon = "1~2주 내 추세 확인 필요"
        risk_level = "주의"
    elif net_score >= -4:
        decision = "부분 매도"
        hold_horizon = "보유 물량 30~50% 정리 검토"
        risk_level = "높음"
    else:
        decision = "전량 매도"
        hold_horizon = "가능한 빠른 시일 내 정리 권고"
        risk_level = "매우 높음"

    return decision, reasoning, hold_horizon, risk_level
