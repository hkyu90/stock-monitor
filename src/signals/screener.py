"""
종목 스크리너
4개 시장 전체 스캔 → 스코어 기반 상위 종목 필터링
기술주 60~70% 비중 자동 조절
"""

import logging
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yaml

from src.data.fetcher import DataFetcher
from src.scoring.engine import score_stock, load_config

logger = logging.getLogger(__name__)


def load_sectors(path: str = "config/sectors.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_tech_stock(sector: str, market: str, sector_config: dict) -> bool:
    """기술주 여부 판단"""
    if market in ("KOSPI", "KOSDAQ"):
        krx = sector_config.get("krx_sectors", {})
        entry = krx.get(sector, {})
        return entry.get("is_tech", False) if isinstance(entry, dict) else False
    else:
        tech_sectors = sector_config.get("gics_tech_sectors", [])
        tech_industries = sector_config.get("gics_tech_industries", [])
        return sector in tech_sectors or sector in tech_industries


def get_universe_sample(fetcher: DataFetcher, market: str, config: dict, max_per_market: int = 100) -> list[dict]:
    """시장별 유니버스 샘플링 (시총 상위)"""
    try:
        if market in ("KOSPI", "KOSDAQ"):
            date = dt.date.today().strftime("%Y%m%d")
            df = fetcher.krx.get_universe(market, date)
            # 시총 기준 필터링은 실행 시 수행
            stocks = df.head(max_per_market).to_dict("records")
        else:
            df = fetcher.us.get_universe(market)
            if "sector" in df.columns:
                stocks = df.head(max_per_market).to_dict("records")
            else:
                stocks = df.head(max_per_market).to_dict("records")
        return stocks
    except Exception as e:
        logger.error(f"Universe fetch failed for {market}: {e}")
        return []


def screen_market(
    market: str,
    fetcher: DataFetcher,
    config: dict,
    sector_config: dict,
    max_stocks: int = 80,
) -> list[dict]:
    """단일 시장 스크리닝"""
    logger.info(f"Screening {market}...")
    stocks = get_universe_sample(fetcher, market, config, max_per_market=max_stocks)
    results = []

    for stock in stocks:
        code = stock.get("code", "")
        name = stock.get("name", "")
        if not code or not name:
            continue

        try:
            result = score_stock(code, name, market, fetcher, config)
            if result:
                # 섹터 정보 추가
                sector = stock.get("sector", "")
                result["sector"] = sector
                result["is_tech"] = is_tech_stock(sector, market, sector_config)
                results.append(result)
        except Exception as e:
            logger.debug(f"Score failed for {name} ({code}): {e}")
            continue

    logger.info(f"{market}: {len(results)} stocks scored")
    return results


def run_screening(config: dict | None = None) -> dict:
    """전체 시장 스크리닝 실행"""
    if config is None:
        config = load_config()
    sector_config = load_sectors()
    fetcher = DataFetcher()

    all_results = []
    for market in config["universe"]["markets"]:
        results = screen_market(market, fetcher, config, sector_config)
        all_results.extend(results)

    if not all_results:
        return {"midterm": [], "longterm": [], "watchlist": []}

    # --- 중기 전략 상위 종목 ---
    sorted_mid = sorted(all_results, key=lambda x: x["midterm"]["score"], reverse=True)
    top_n = config["report"]["top_picks_midterm"]
    tech_target = config["tech_weight"]

    midterm_picks = _apply_tech_balance(sorted_mid, top_n, tech_target)

    # --- 장기 전략 상위 종목 ---
    sorted_long = sorted(all_results, key=lambda x: x["longterm"]["score"], reverse=True)
    top_n_long = config["report"]["top_picks_longterm"]
    longterm_picks = _apply_tech_balance(sorted_long, top_n_long, tech_target)

    return {
        "midterm": midterm_picks,
        "longterm": longterm_picks,
        "total_screened": len(all_results),
        "date": dt.date.today().isoformat(),
    }


def _apply_tech_balance(sorted_stocks: list, top_n: int, tech_target: float) -> list:
    """기술주 비중 목표에 맞춰 종목 선별"""
    tech_count_target = int(top_n * tech_target)
    non_tech_target = top_n - tech_count_target

    tech_picks = []
    non_tech_picks = []

    for stock in sorted_stocks:
        if stock.get("is_tech") and len(tech_picks) < tech_count_target:
            tech_picks.append(stock)
        elif not stock.get("is_tech") and len(non_tech_picks) < non_tech_target:
            non_tech_picks.append(stock)

        if len(tech_picks) >= tech_count_target and len(non_tech_picks) >= non_tech_target:
            break

    # 부족분은 나머지에서 채움
    result = tech_picks + non_tech_picks
    if len(result) < top_n:
        existing_codes = {s["code"] for s in result}
        for stock in sorted_stocks:
            if stock["code"] not in existing_codes:
                result.append(stock)
                if len(result) >= top_n:
                    break

    return result
