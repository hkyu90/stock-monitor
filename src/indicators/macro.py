"""
거시경제 지표 분석 모듈
시장 전체 환경 + 섹터 동향 → 보유/매도 판단에 반영
"""

import datetime as dt
import logging

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def get_macro_environment() -> dict:
    """거시경제 환경 종합 분석"""
    end = dt.date.today()
    start = end - dt.timedelta(days=120)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    result = {
        "us_market": _analyze_index("^GSPC", "S&P500", start_str, end_str),
        "kr_market": _analyze_index("^KS11", "KOSPI", start_str, end_str),
        "nasdaq": _analyze_index("^IXIC", "NASDAQ", start_str, end_str),
        "vix": _analyze_vix(start_str, end_str),
        "usd_krw": _analyze_currency("KRW=X", start_str, end_str),
        "us_10y": _analyze_treasury(start_str, end_str),
    }

    # 종합 판단
    scores = []
    for key in ["us_market", "kr_market", "nasdaq"]:
        if result[key].get("trend_score") is not None:
            scores.append(result[key]["trend_score"])

    vix_score = result["vix"].get("score", 50)
    treasury_score = result["us_10y"].get("score", 50)

    if scores:
        market_avg = np.mean(scores)
    else:
        market_avg = 50

    # 거시환경 종합점수 (0~100, 높을수록 주식시장에 우호적)
    macro_score = market_avg * 0.50 + vix_score * 0.30 + treasury_score * 0.20
    macro_score = np.clip(macro_score, 0, 100)

    if macro_score >= 65:
        macro_outlook = "우호적"
        macro_action = "보유 유지 / 추가 매수 검토"
    elif macro_score >= 45:
        macro_outlook = "중립"
        macro_action = "선별적 보유, 약한 종목 정리"
    else:
        macro_outlook = "비우호적"
        macro_action = "현금 비중 확대, 방어적 운용"

    result["macro_score"] = round(macro_score, 1)
    result["macro_outlook"] = macro_outlook
    result["macro_action"] = macro_action

    return result


def _analyze_index(ticker: str, name: str, start: str, end: str) -> dict:
    """주요 지수 추세 분석"""
    try:
        data = yf.Ticker(ticker).history(start=start, end=end)
        if data.empty or len(data) < 20:
            return {"name": name, "trend_score": 50, "trend": "데이터 부족"}

        close = data["Close"]
        current = close.iloc[-1]

        # 이동평균선 배열
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else ma20

        # 추세 판단
        ret_1m = (current / close.iloc[-min(20, len(close))] - 1) * 100
        ret_3m = (current / close.iloc[0] - 1) * 100 if len(close) > 20 else ret_1m

        score = 50
        trend = "횡보"

        if current > ma20 > ma60:
            score = 70 + min(20, ret_1m)
            trend = "상승추세"
        elif current < ma20 < ma60:
            score = 30 - min(20, abs(ret_1m))
            trend = "하락추세"
        elif current > ma20:
            score = 60
            trend = "단기 반등"
        else:
            score = 40
            trend = "단기 조정"

        score = np.clip(score, 0, 100)

        return {
            "name": name,
            "current": round(current, 2),
            "return_1m": round(ret_1m, 2),
            "return_3m": round(ret_3m, 2),
            "trend": trend,
            "trend_score": round(score, 1),
        }
    except Exception as e:
        logger.warning(f"Index analysis failed for {name}: {e}")
        return {"name": name, "trend_score": 50, "trend": "분석 불가"}


def _analyze_vix(start: str, end: str) -> dict:
    """VIX (공포지수) 분석"""
    try:
        data = yf.Ticker("^VIX").history(start=start, end=end)
        if data.empty:
            return {"score": 50, "level": "분석 불가"}

        current = data["Close"].iloc[-1]
        avg_20d = data["Close"].rolling(20).mean().iloc[-1]

        # VIX가 낮을수록 주식시장에 우호적
        if current < 15:
            score = 80
            level = "안정 (낮은 변동성)"
        elif current < 20:
            score = 65
            level = "정상"
        elif current < 25:
            score = 45
            level = "경계"
        elif current < 30:
            score = 30
            level = "공포"
        else:
            score = 15
            level = "극단적 공포"

        return {
            "current": round(current, 2),
            "avg_20d": round(avg_20d, 2),
            "level": level,
            "score": round(score, 1),
        }
    except Exception as e:
        logger.warning(f"VIX analysis failed: {e}")
        return {"score": 50, "level": "분석 불가"}


def _analyze_currency(ticker: str, start: str, end: str) -> dict:
    """환율 분석 (USD/KRW)"""
    try:
        data = yf.Ticker(ticker).history(start=start, end=end)
        if data.empty:
            return {"trend": "분석 불가"}

        close = data["Close"]
        current = close.iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ret_1m = (current / close.iloc[-min(20, len(close))] - 1) * 100

        if current > ma20:
            trend = "원화 약세 (달러 강세)"
        else:
            trend = "원화 강세 (달러 약세)"

        return {
            "current": round(current, 2),
            "return_1m": round(ret_1m, 2),
            "trend": trend,
        }
    except Exception as e:
        return {"trend": "분석 불가"}


def _analyze_treasury(start: str, end: str) -> dict:
    """미국 10년 국채 금리 분석"""
    try:
        data = yf.Ticker("^TNX").history(start=start, end=end)
        if data.empty:
            return {"score": 50, "trend": "분석 불가"}

        current = data["Close"].iloc[-1]
        ma20 = data["Close"].rolling(20).mean().iloc[-1]
        ret_1m = (current / data["Close"].iloc[-min(20, len(data))] - 1) * 100

        # 금리 하락 → 주식 우호, 금리 상승 → 주식 비우호
        if current < ma20 and ret_1m < 0:
            score = 70
            trend = "금리 하락세 (주식 우호)"
        elif current > ma20 and ret_1m > 0:
            score = 30
            trend = "금리 상승세 (주식 비우호)"
        else:
            score = 50
            trend = "금리 횡보"

        return {
            "current": round(current, 2),
            "return_1m": round(ret_1m, 2),
            "trend": trend,
            "score": round(score, 1),
        }
    except Exception as e:
        return {"score": 50, "trend": "분석 불가"}
