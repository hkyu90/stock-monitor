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
    macro_data: dict | None = None,
    hold_analyses: list[dict] | None = None,
) -> str:
    """관심종목 + 보유종목 심층 모니터링 리포트"""
    if config is None:
        config = load_config()

    today = dt.date.today()
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][today.weekday()]
    lines = []

    lines.append("---")
    lines.append(f"tags: [주식모니터링, 포트폴리오]")
    lines.append(f"date: {today.isoformat()}")
    lines.append(f"type: stock-watchlist")
    lines.append("---")
    lines.append("")
    lines.append(f"# 📋 주식 포트폴리오 & 관심종목 모니터링")
    lines.append(f"> {today.isoformat()} ({weekday_kr}) 업데이트")
    lines.append("")

    # === 거시경제 환경 ===
    if macro_data:
        lines.append("## 🌍 거시경제 환경")
        lines.append("")
        macro_score = macro_data.get("macro_score", 50)
        macro_outlook = macro_data.get("macro_outlook", "중립")
        macro_action = macro_data.get("macro_action", "")
        macro_emoji = "🟢" if macro_score >= 60 else ("🟡" if macro_score >= 40 else "🔴")

        lines.append(f"**{macro_emoji} 종합: {macro_outlook} ({macro_score}점) — {macro_action}**")
        lines.append("")

        lines.append("| 지표 | 현황 | 추세 |")
        lines.append("|------|------|------|")

        for key, label in [("us_market", "S&P500"), ("kr_market", "KOSPI"), ("nasdaq", "NASDAQ")]:
            d = macro_data.get(key, {})
            val = f"{d.get('current', 0):,.0f}"
            ret = d.get("return_1m", 0)
            trend = d.get("trend", "-")
            ret_str = f"+{ret:.1f}%" if ret > 0 else f"{ret:.1f}%"
            lines.append(f"| {label} | {val} (1M {ret_str}) | {trend} |")

        vix = macro_data.get("vix", {})
        lines.append(f"| VIX (공포지수) | {vix.get('current', 0):.1f} | {vix.get('level', '-')} |")

        usd = macro_data.get("usd_krw", {})
        lines.append(f"| USD/KRW | {usd.get('current', 0):,.0f} | {usd.get('trend', '-')} |")

        treasury = macro_data.get("us_10y", {})
        lines.append(f"| 미국 10년물 금리 | {treasury.get('current', 0):.2f}% | {treasury.get('trend', '-')} |")
        lines.append("")

    # === 보유종목 심층 분석 ===
    if portfolio_results:
        lines.append("## 💼 보유종목 심층 분석")
        lines.append("")

        # 요약 테이블
        lines.append("| 종목 | 수익률 | 판단 | 리스크 | 보유 전략 |")
        lines.append("|------|--------|------|--------|-----------|")

        total_invested = 0
        total_current = 0

        for i, stock in enumerate(portfolio_results):
            avg_price = stock.get("avg_price", 0)
            shares = stock.get("shares", 0)
            current_price = stock["price"]
            pnl_pct = ((current_price / avg_price) - 1) * 100 if avg_price > 0 else 0

            invested = avg_price * shares
            current_val = current_price * shares
            total_invested += invested
            total_current += current_val

            pnl_emoji = "📈" if pnl_pct > 0 else "📉"

            # hold_analyses에서 해당 종목 분석 결과 가져오기
            ha = hold_analyses[i] if hold_analyses and i < len(hold_analyses) else None
            if ha:
                decision = ha["decision"]
                risk = ha["risk_level"]
                horizon = ha["hold_horizon"]
                decision_emoji = _decision_emoji(decision)
                risk_emoji = _risk_emoji(risk)
            else:
                decision = "-"
                risk = "-"
                horizon = "-"
                decision_emoji = "⚪"
                risk_emoji = ""

            lines.append(
                f"| **{stock['name']}** | {pnl_emoji} {pnl_pct:+.1f}% | "
                f"{decision_emoji} {decision} | {risk_emoji} {risk} | {horizon} |"
            )

        lines.append("")
        total_pnl = total_current - total_invested
        total_pnl_pct = (total_current / total_invested - 1) * 100 if total_invested > 0 else 0
        lines.append(f"> **포트폴리오**: 투자원금 {total_invested:,.0f} → 평가액 {total_current:,.0f} (**{total_pnl_pct:+.1f}%**, {total_pnl:+,.0f})")
        lines.append("")

        # 종목별 상세 분석
        lines.append("### 종목별 상세 분석")
        lines.append("")

        for i, stock in enumerate(portfolio_results):
            avg_price = stock.get("avg_price", 0)
            current_price = stock["price"]
            shares = stock.get("shares", 0)
            pnl_pct = ((current_price / avg_price) - 1) * 100 if avg_price > 0 else 0

            ha = hold_analyses[i] if hold_analyses and i < len(hold_analyses) else None

            lines.append(f"#### {stock['name']} ({stock['code']}, {stock['market']})")
            lines.append("")
            lines.append(f"- **현재가**: {current_price:,.0f} | **매수가**: {avg_price:,.0f} | **수량**: {shares} | **수익률**: {pnl_pct:+.1f}%")
            lines.append(f"- **스코어**: 기술적 {stock['technical']['score']} / 펀더멘털 {stock['fundamental']['score']} / 모멘텀 {stock['momentum']['score']}")

            if ha:
                decision_emoji = _decision_emoji(ha["decision"])
                lines.append(f"- **{decision_emoji} 판단: {ha['decision']}** — {ha['hold_horizon']}")

                # 판단 근거
                lines.append(f"- **판단 근거**:")
                for reason in ha["reasoning"]:
                    lines.append(f"  - {reason}")

                # 지지/저항선
                sr = ha.get("support_resistance", {})
                if sr.get("support"):
                    lines.append(f"- **지지선**: {sr['support']:,.0f} | **저항선**: {sr['resistance']:,.0f} | MA20: {sr.get('ma20', 0):,.0f} | MA60: {sr.get('ma60', 0):,.0f}")

                # 추세 정보
                trend = ha.get("trend", {})
                if trend.get("adx"):
                    lines.append(f"- **추세**: {trend['direction']} / ADX {trend['adx']} ({trend['strength']}){' / 전환 신호' if trend.get('turning') else ''}")

            lines.append("")

    # === 관심종목 ===
    lines.append("## 👀 관심종목 매수 타이밍 모니터링")
    lines.append("")

    if not watchlist_results:
        lines.append("> 등록된 관심종목이 없습니다. `config/watchlist.yaml`에 종목을 추가하세요.")
    else:
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


def _decision_emoji(decision: str) -> str:
    return {
        "적극 보유": "🟢",
        "보유 유지": "🔵",
        "관망": "🟡",
        "부분 매도": "🟠",
        "전량 매도": "🔴",
    }.get(decision, "⚪")


def _risk_emoji(risk: str) -> str:
    return {
        "낮음": "🟢",
        "보통": "🔵",
        "주의": "🟡",
        "높음": "🟠",
        "매우 높음": "🔴",
    }.get(risk, "")
