"""
종합 스코어링 엔진
기술적 + 펀더멘털 + 모멘텀 → 듀얼 전략별 점수 산출
"""

import logging
import pandas as pd
import yaml

from src.data.fetcher import DataFetcher
from src.indicators import technical, fundamental, momentum

logger = logging.getLogger(__name__)


def load_config(path: str = "config/strategy.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def score_stock(
    code: str,
    name: str,
    market: str,
    fetcher: DataFetcher,
    config: dict,
) -> dict:
    """개별 종목 듀얼 스코어링"""
    # 데이터 수집
    ohlcv = fetcher.fetch_ohlcv(code, market)
    if ohlcv.empty:
        return None

    fund_data = fetcher.fetch_fundamental(code, market)

    # 투자자 수급 (한국 시장만)
    investor_data = None
    if market in ("KOSPI", "KOSDAQ"):
        try:
            import datetime as dt
            end = dt.date.today().strftime("%Y%m%d")
            start = (dt.date.today() - dt.timedelta(days=30)).strftime("%Y%m%d")
            investor_data = fetcher.krx.get_investor_trading(code, start, end)
        except Exception:
            pass

    # 지표 계산
    tech_result = technical.compute_all(ohlcv, config["technical"])
    fund_result = fundamental.compute_all(fund_data, config["fundamental"])
    mom_result = momentum.compute_all(ohlcv, investor_data, config["momentum"])

    # 중기 스코어
    mid_w = config["midterm_scoring"]
    midterm_score = (
        tech_result["score"] * mid_w["technical_weight"]
        + fund_result["score"] * mid_w["fundamental_weight"]
        + mom_result["score"] * mid_w["momentum_weight"]
    )

    # 장기 스코어
    long_w = config["longterm_scoring"]
    longterm_score = (
        tech_result["score"] * long_w["technical_weight"]
        + fund_result["score"] * long_w["fundamental_weight"]
        + mom_result["score"] * long_w["momentum_weight"]
    )

    # 시그널 판정
    sig_cfg = config["signals"]
    all_signals = tech_result["signals"] + fund_result["signals"] + mom_result["signals"]

    def classify(score):
        if score >= sig_cfg["strong_buy"]:
            return "강력매수"
        elif score >= sig_cfg["buy"]:
            return "매수관심"
        elif score >= sig_cfg["neutral"]:
            return "중립"
        elif score >= sig_cfg["sell"]:
            return "매도관심"
        else:
            return "강력매도"

    return {
        "code": code,
        "name": name,
        "market": market,
        "price": tech_result.get("price", 0),
        "midterm": {
            "score": round(midterm_score, 1),
            "signal": classify(midterm_score),
        },
        "longterm": {
            "score": round(longterm_score, 1),
            "signal": classify(longterm_score),
        },
        "technical": tech_result,
        "fundamental": fund_result,
        "momentum": mom_result,
        "all_signals": all_signals,
    }


def compute_entry_exit(result: dict, config: dict, strategy: str = "midterm") -> dict:
    """매수/매도가 산출"""
    price = result["price"]
    if price <= 0:
        return {}

    trading = config["trading"][strategy]
    entry_cfg = trading["entry"]
    exit_cfg = trading["exit"]

    entries = []
    for i, ratio in enumerate(entry_cfg["split_ratio"]):
        discount = (i + 1) * 2  # 1차: -2%, 2차: -4%, 3차: -6%
        entry_price = price * (1 - discount / 100)
        entries.append({
            "차수": f"{i+1}차",
            "비중": f"{ratio*100:.0f}%",
            "매수가": round(entry_price, 0),
        })

    return {
        "entries": entries,
        "take_profit": round(price * (1 + exit_cfg["take_profit_pct"] / 100), 0),
        "stop_loss": round(price * (1 - exit_cfg["max_loss_pct"] / 100), 0),
        "trailing_stop_pct": exit_cfg["trailing_stop_pct"],
    }
