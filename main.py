"""
Stock Monitor — 메인 진입점
주식 매수추천 & 관심종목 모니터링 CLI

Usage:
    python main.py daily          # 일일 리포트 생성 + 옵시디언 저장
    python main.py watchlist      # 관심종목 모니터링
    python main.py backtest TICKER MARKET [--strategy midterm|longterm]
    python main.py score TICKER MARKET   # 단일 종목 스코어링
"""

import sys
import logging
import argparse
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("stock-monitor")


def cmd_daily(args):
    """일일 스크리닝 리포트"""
    from src.scoring.engine import load_config
    from src.signals.screener import run_screening
    from src.report.generator import generate_daily_report, save_to_obsidian

    config = load_config()
    logger.info("=== 일일 스크리닝 시작 ===")

    result = run_screening(config)

    report = generate_daily_report(result, config)
    filepath = save_to_obsidian(report, config)

    logger.info(f"=== 리포트 저장 완료: {filepath} ===")
    print(f"\n리포트 저장: {filepath}")
    print(f"중기 추천: {len(result['midterm'])}개 | 장기 추천: {len(result['longterm'])}개")


def cmd_watchlist(args):
    """관심종목 모니터링"""
    from src.scoring.engine import load_config, score_stock
    from src.data.fetcher import DataFetcher
    from src.report.generator import generate_watchlist_report, save_to_obsidian

    config = load_config()
    fetcher = DataFetcher()

    with open("config/watchlist.yaml", "r", encoding="utf-8") as f:
        watchlist = yaml.safe_load(f)

    results = []

    # 한국 종목
    for stock in (watchlist.get("krx") or []):
        code = stock["code"]
        name = stock["name"]
        market = "KOSPI"  # 기본값, pykrx가 자동 판별
        result = score_stock(code, name, market, fetcher, config)
        if result:
            results.append(result)

    # 미국 종목
    for stock in (watchlist.get("us") or []):
        ticker = stock["ticker"]
        name = stock["name"]
        result = score_stock(ticker, name, "NASDAQ", fetcher, config)
        if result:
            results.append(result)

    report = generate_watchlist_report(results, config)

    # 옵시디언 저장
    import os, datetime as dt
    vault = r"C:\Users\User\iCloudDrive\iCloud~md~obsidian\hkyu_note"
    folder = config["report"]["obsidian_folder"]
    target_dir = os.path.join(vault, folder)
    os.makedirs(target_dir, exist_ok=True)
    filepath = os.path.join(target_dir, f"{dt.date.today().isoformat()} 관심종목 모니터링.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n관심종목 리포트 저장: {filepath}")
    print(f"모니터링 종목: {len(results)}개")


def cmd_backtest(args):
    """백테스팅"""
    from src.backtest.backtester import Backtester

    bt = Backtester()
    result = bt.run(
        code=args.ticker,
        name=args.ticker,
        market=args.market,
        strategy=args.strategy,
    )

    if "error" in result:
        print(f"Error: {result['error']}")
        return

    print(f"\n=== 백테스트 결과: {result['name']} ({result['market']}) ===")
    print(f"전략: {result['strategy']}")
    print(f"기간: {result['period_months']}개월")
    print(f"초기자본: {result['initial_capital']:,.0f}원")
    print(f"최종자산: {result['final_equity']:,.0f}원")
    print(f"수익률: {result['total_return_pct']:+.2f}%")
    print(f"샤프비율: {result['sharpe_ratio']:.2f}")
    print(f"최대낙폭: -{result['max_drawdown_pct']:.2f}%")
    print(f"총 거래: {result['total_trades']}회")
    print(f"승률: {result['win_rate']:.1f}%")

    if result["trades"]:
        print(f"\n--- 거래 내역 ---")
        for t in result["trades"]:
            if t["action"] == "BUY":
                print(f"  {t['date']} BUY  {t['price']:>10,.0f} x {t['shares']}주 (점수: {t['score']})")
            else:
                print(f"  {t['date']} SELL {t['price']:>10,.0f} x {t['shares']}주 ({t['reason']}, {t['pnl_pct']:+.1f}%)")


def cmd_score(args):
    """단일 종목 스코어링"""
    from src.scoring.engine import load_config, score_stock, compute_entry_exit
    from src.data.fetcher import DataFetcher

    config = load_config()
    fetcher = DataFetcher()

    result = score_stock(args.ticker, args.ticker, args.market, fetcher, config)
    if not result:
        print(f"Failed to score {args.ticker}")
        return

    print(f"\n=== {result['name']} ({result['code']}, {result['market']}) ===")
    print(f"현재가: {result['price']:,.0f}")
    print(f"\n[중기 모멘텀 스윙]  점수: {result['midterm']['score']}  시그널: {result['midterm']['signal']}")
    print(f"[장기 가치성장]    점수: {result['longterm']['score']}  시그널: {result['longterm']['signal']}")
    print(f"\n기술적: {result['technical']['score']}  펀더멘털: {result['fundamental']['score']}  모멘텀: {result['momentum']['score']}")

    if result["all_signals"]:
        print(f"\n시그널: {' / '.join(result['all_signals'])}")

    # 매수/매도가
    for strategy in ["midterm", "longterm"]:
        ee = compute_entry_exit(result, config, strategy)
        if ee and ee.get("entries"):
            print(f"\n[{strategy}] 매매 전략:")
            for e in ee["entries"]:
                print(f"  {e['차수']} ({e['비중']}): {e['매수가']:,.0f}")
            print(f"  목표가: {ee['take_profit']:,.0f} | 손절가: {ee['stop_loss']:,.0f}")


def main():
    parser = argparse.ArgumentParser(description="Stock Monitor - 주식 매수추천 & 모니터링")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("daily", help="일일 스크리닝 리포트 생성")
    sub.add_parser("watchlist", help="관심종목 모니터링")

    bt_parser = sub.add_parser("backtest", help="백테스팅")
    bt_parser.add_argument("ticker", help="종목코드 또는 티커")
    bt_parser.add_argument("market", choices=["KOSPI", "KOSDAQ", "NASDAQ", "SP500"])
    bt_parser.add_argument("--strategy", default="midterm", choices=["midterm", "longterm"])

    sc_parser = sub.add_parser("score", help="단일 종목 스코어링")
    sc_parser.add_argument("ticker", help="종목코드 또는 티커")
    sc_parser.add_argument("market", choices=["KOSPI", "KOSDAQ", "NASDAQ", "SP500"])

    args = parser.parse_args()

    if args.command == "daily":
        cmd_daily(args)
    elif args.command == "watchlist":
        cmd_watchlist(args)
    elif args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "score":
        cmd_score(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
