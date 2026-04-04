"""
리포트 생성 모듈
옵시디언 마크다운 형식으로 일일/주간 리포트 출력
"""

import datetime as dt
import os
import logging

from src.scoring.engine import compute_entry_exit, load_config

logger = logging.getLogger(__name__)

OBSIDIAN_VAULT = r"C:\Users\User\iCloudDrive\iCloud~md~obsidian\hkyu_note"


def generate_daily_report(screening_result: dict, config: dict | None = None) -> str:
    """일일 리포트 마크다운 생성"""
    if config is None:
        config = load_config()

    today = dt.date.today()
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][today.weekday()]

    lines = []

    # Frontmatter
    lines.append("---")
    lines.append(f"tags: [주식모니터링, 일일리포트]")
    lines.append(f"date: {today.isoformat()}")
    lines.append(f"type: stock-daily")
    lines.append("---")
    lines.append("")

    # 헤더
    lines.append(f"# 📊 주식 모니터링 일일 리포트")
    lines.append(f"> {today.isoformat()} ({weekday_kr}) | 스캔 종목: {screening_result.get('total_screened', 0)}개")
    lines.append("")

    # --- 중기 모멘텀 스윙 ---
    lines.append("## 🔥 중기 모멘텀 스윙 (2~8주)")
    lines.append("")
    midterm = screening_result.get("midterm", [])
    if midterm:
        lines.append("| # | 종목 | 시장 | 현재가 | 점수 | 시그널 | 핵심 근거 |")
        lines.append("|---|------|------|--------|------|--------|-----------|")
        for i, stock in enumerate(midterm, 1):
            name = stock["name"]
            market = stock["market"]
            price = f"{stock['price']:,.0f}" if stock["price"] else "-"
            score = stock["midterm"]["score"]
            signal = stock["midterm"]["signal"]
            reasons = ", ".join(stock["all_signals"][:3]) if stock["all_signals"] else "-"
            emoji = _signal_emoji(signal)
            lines.append(f"| {i} | **{name}** | {market} | {price} | {score} | {emoji} {signal} | {reasons} |")
        lines.append("")

        # 상위 3개 상세
        lines.append("### 상위 종목 상세")
        lines.append("")
        for stock in midterm[:3]:
            _append_stock_detail(lines, stock, "midterm", config)
    else:
        lines.append("> 매수 시그널 발생 종목 없음")
    lines.append("")

    # --- 장기 가치성장 ---
    lines.append("## 🌱 장기 가치성장 (6개월~1년+)")
    lines.append("")
    longterm = screening_result.get("longterm", [])
    if longterm:
        lines.append("| # | 종목 | 시장 | 현재가 | 점수 | 시그널 | 핵심 근거 |")
        lines.append("|---|------|------|--------|------|--------|-----------|")
        for i, stock in enumerate(longterm, 1):
            name = stock["name"]
            market = stock["market"]
            price = f"{stock['price']:,.0f}" if stock["price"] else "-"
            score = stock["longterm"]["score"]
            signal = stock["longterm"]["signal"]
            reasons = ", ".join(stock["all_signals"][:3]) if stock["all_signals"] else "-"
            emoji = _signal_emoji(signal)
            lines.append(f"| {i} | **{name}** | {market} | {price} | {score} | {emoji} {signal} | {reasons} |")
        lines.append("")

        lines.append("### 상위 종목 상세")
        lines.append("")
        for stock in longterm[:3]:
            _append_stock_detail(lines, stock, "longterm", config)
    else:
        lines.append("> 매수 시그널 발생 종목 없음")
    lines.append("")

    # --- 시장 요약 ---
    lines.append("## 📈 시장 요약")
    lines.append("")
    lines.append(f"- 총 스캔 종목: {screening_result.get('total_screened', 0)}개")
    lines.append(f"- 중기 추천: {len(midterm)}개")
    lines.append(f"- 장기 추천: {len(longterm)}개")

    tech_mid = len([s for s in midterm if s.get("is_tech")])
    tech_long = len([s for s in longterm if s.get("is_tech")])
    lines.append(f"- 중기 기술주 비중: {tech_mid}/{len(midterm)} ({tech_mid/max(1,len(midterm))*100:.0f}%)")
    lines.append(f"- 장기 기술주 비중: {tech_long}/{len(longterm)} ({tech_long/max(1,len(longterm))*100:.0f}%)")
    lines.append("")

    lines.append("---")
    lines.append(f"*자동 생성: stock-monitor | {dt.datetime.now().strftime('%H:%M')}*")

    return "\n".join(lines)


def _append_stock_detail(lines: list, stock: dict, strategy: str, config: dict):
    """종목 상세 정보 추가"""
    name = stock["name"]
    lines.append(f"#### {name} ({stock['code']}, {stock['market']})")
    lines.append("")

    # 점수 분해
    tech = stock["technical"]
    fund = stock["fundamental"]
    mom = stock["momentum"]

    lines.append(f"- **기술적**: {tech['score']}점 | **펀더멘털**: {fund['score']}점 | **모멘텀**: {mom['score']}점")

    # 매수/매도가
    entry_exit = compute_entry_exit(stock, config, strategy)
    if entry_exit:
        entries = entry_exit.get("entries", [])
        if entries:
            entry_str = " / ".join([f"{e['차수']} {e['매수가']:,.0f}" for e in entries])
            lines.append(f"- **분할매수가**: {entry_str}")
        lines.append(f"- **목표가**: {entry_exit.get('take_profit', 0):,.0f} | **손절가**: {entry_exit.get('stop_loss', 0):,.0f}")

    # 시그널
    if stock["all_signals"]:
        signals_str = " / ".join(stock["all_signals"])
        lines.append(f"- **시그널**: {signals_str}")
    lines.append("")


def _signal_emoji(signal: str) -> str:
    return {
        "강력매수": "🟢",
        "매수관심": "🔵",
        "중립": "⚪",
        "매도관심": "🟡",
        "강력매도": "🔴",
    }.get(signal, "⚪")


def save_to_obsidian(content: str, config: dict | None = None):
    """옵시디언 볼트에 리포트 저장"""
    if config is None:
        config = load_config()

    folder = config["report"]["obsidian_folder"]
    target_dir = os.path.join(OBSIDIAN_VAULT, folder)
    os.makedirs(target_dir, exist_ok=True)

    today = dt.date.today().isoformat()
    filename = f"{today} 주식 모니터링 일일리포트.md"
    filepath = os.path.join(target_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Report saved: {filepath}")
    return filepath


def generate_watchlist_report(
    watchlist_results: list[dict],
    config: dict | None = None,
    portfolio_results: list[dict] | None = None,
) -> str:
    """관심종목 + 보유종목 모니터링 리포트"""
    if config is None:
        config = load_config()

    today = dt.date.today()
    lines = []

    lines.append("---")
    lines.append(f"tags: [주식모니터링, 포트폴리오]")
    lines.append(f"date: {today.isoformat()}")
    lines.append(f"type: stock-watchlist")
    lines.append("---")
    lines.append("")
    lines.append(f"# 📋 주식 포트폴리오 & 관심종목 모니터링")
    lines.append(f"> {today.isoformat()} 업데이트")
    lines.append("")

    # --- 보유종목 매도 시그널 ---
    if portfolio_results:
        lines.append("## 💼 보유종목 매도 타이밍 모니터링")
        lines.append("")
        lines.append("| 종목 | 시장 | 매수가 | 현재가 | 수익률 | 평가액 | 중기 | 장기 | 매도 시그널 |")
        lines.append("|------|------|--------|--------|--------|--------|------|------|-------------|")

        total_invested = 0
        total_current = 0

        for stock in portfolio_results:
            name = stock["name"]
            market = stock["market"]
            avg_price = stock.get("avg_price", 0)
            shares = stock.get("shares", 0)
            current_price = stock["price"]

            pnl_pct = ((current_price / avg_price) - 1) * 100 if avg_price > 0 else 0
            invested = avg_price * shares
            current_val = current_price * shares
            total_invested += invested
            total_current += current_val

            pnl_emoji = "📈" if pnl_pct > 0 else "📉"
            mid_signal = stock["midterm"]["signal"]
            long_signal = stock["longterm"]["signal"]

            # 매도 판단
            sell_signals = []
            if stock["midterm"]["score"] <= 35:
                sell_signals.append("중기 매도시그널")
            if stock["longterm"]["score"] <= 35:
                sell_signals.append("장기 매도시그널")
            if pnl_pct >= 20:
                sell_signals.append(f"익절 검토 (+{pnl_pct:.0f}%)")
            if pnl_pct <= -10:
                sell_signals.append(f"손절 검토 ({pnl_pct:.0f}%)")

            # 기술적 시그널에서 매도 관련 추출
            for sig in stock.get("all_signals", []):
                if any(kw in sig for kw in ["데드크로스", "역배열", "과매수"]):
                    sell_signals.append(sig)

            sell_str = " / ".join(sell_signals) if sell_signals else "보유 유지"
            sell_emoji = "🔴" if sell_signals else "🟢"

            lines.append(
                f"| **{name}** | {market} | {avg_price:,.0f} | {current_price:,.0f} | "
                f"{pnl_emoji} {pnl_pct:+.1f}% | {current_val:,.0f} | "
                f"{_signal_emoji(mid_signal)} {stock['midterm']['score']} | "
                f"{_signal_emoji(long_signal)} {stock['longterm']['score']} | "
                f"{sell_emoji} {sell_str} |"
            )

        lines.append("")
        total_pnl = total_current - total_invested
        total_pnl_pct = (total_current / total_invested - 1) * 100 if total_invested > 0 else 0
        lines.append(f"> **포트폴리오 요약**: 투자원금 {total_invested:,.0f} → 평가액 {total_current:,.0f} ({total_pnl_pct:+.1f}%, {total_pnl:+,.0f})")
        lines.append("")

    # --- 관심종목 ---
    lines.append("## 👀 관심종목 매수 타이밍 모니터링")
    lines.append("")

    if not watchlist_results:
        lines.append("> 등록된 관심종목이 없습니다. `config/watchlist.yaml`에 종목을 추가하세요.")
        return "\n".join(lines)

    lines.append("| 종목 | 시장 | 현재가 | 중기점수 | 장기점수 | 변동 시그널 |")
    lines.append("|------|------|--------|----------|----------|------------|")

    for stock in watchlist_results:
        name = stock["name"]
        market = stock["market"]
        price = f"{stock['price']:,.0f}" if stock["price"] else "-"
        mid_score = stock["midterm"]["score"]
        long_score = stock["longterm"]["score"]
        signals = ", ".join(stock["all_signals"][:2]) if stock["all_signals"] else "-"
        lines.append(f"| **{name}** | {market} | {price} | {mid_score} | {long_score} | {signals} |")

    lines.append("")
    lines.append("---")
    lines.append(f"*자동 생성: stock-monitor | {dt.datetime.now().strftime('%H:%M')}*")

    return "\n".join(lines)
