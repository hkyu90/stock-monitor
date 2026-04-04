"""
백테스팅 엔진
과거 데이터로 전략 수익률 검증
"""

import datetime as dt
import logging

import pandas as pd
import numpy as np

from src.data.fetcher import DataFetcher
from src.indicators import technical, fundamental, momentum as mom_module
from src.scoring.engine import load_config

logger = logging.getLogger(__name__)


class Backtester:
    def __init__(self, config: dict | None = None):
        self.config = config or load_config()
        self.bt_cfg = self.config["backtest"]
        self.initial_capital = self.bt_cfg["initial_capital"]
        self.commission = self.bt_cfg["commission_rate"]

    def run(
        self,
        code: str,
        name: str,
        market: str,
        strategy: str = "midterm",
        period_months: int | None = None,
    ) -> dict:
        """단일 종목 백테스트"""
        period = period_months or self.bt_cfg["period_months"]
        days = period * 30 + 60  # 지표 계산 여유분

        fetcher = DataFetcher()
        ohlcv = fetcher.fetch_ohlcv(code, market, days=days)
        if ohlcv.empty or len(ohlcv) < 60:
            return {"error": f"Insufficient data for {name}"}

        # 전략 가중치
        if strategy == "midterm":
            weights = self.config["midterm_scoring"]
            trading = self.config["trading"]["midterm"]
        else:
            weights = self.config["longterm_scoring"]
            trading = self.config["trading"]["longterm"]

        # 시뮬레이션
        capital = self.initial_capital
        position = 0
        entry_price = 0
        trades = []
        equity_curve = []

        # 60일부터 시작 (지표 안정화)
        for i in range(60, len(ohlcv)):
            window = ohlcv.iloc[:i+1]
            current_price = window["close"].iloc[-1]
            date = window.index[i]

            # 기술적 점수 계산
            tech_score = technical.compute_all(window, self.config["technical"])["score"]

            # 간략화된 모멘텀 점수
            mom_result = mom_module.compute_week52_position(window)
            mom_score = mom_result["score"]

            # 종합 점수 (백테스트에서는 펀더멘털 고정)
            total_score = (
                tech_score * weights["technical_weight"]
                + 50 * weights["fundamental_weight"]  # 펀더멘털은 백테스트 중 고정
                + mom_score * weights["momentum_weight"]
            )

            equity = capital + position * current_price
            equity_curve.append({"date": date, "equity": equity})

            # 매매 로직
            if position == 0:
                # 매수 시그널
                if total_score >= self.config["signals"]["buy"]:
                    shares = int(capital * 0.95 / current_price)
                    if shares > 0:
                        cost = shares * current_price * (1 + self.commission)
                        capital -= cost
                        position = shares
                        entry_price = current_price
                        trades.append({
                            "date": str(date)[:10],
                            "action": "BUY",
                            "price": round(current_price, 0),
                            "shares": shares,
                            "score": round(total_score, 1),
                        })
            else:
                # 매도 시그널
                pnl_pct = (current_price / entry_price - 1) * 100
                sell = False

                if pnl_pct >= trading["exit"]["take_profit_pct"]:
                    sell = True
                    reason = "익절"
                elif pnl_pct <= -trading["exit"]["max_loss_pct"]:
                    sell = True
                    reason = "손절"
                elif total_score <= self.config["signals"]["sell"]:
                    sell = True
                    reason = "매도시그널"

                if sell:
                    revenue = position * current_price * (1 - self.commission)
                    tax = 0
                    if market in ("KOSPI", "KOSDAQ"):
                        tax = position * current_price * self.bt_cfg["tax_rate_kr"]
                    capital += revenue - tax
                    trades.append({
                        "date": str(date)[:10],
                        "action": "SELL",
                        "price": round(current_price, 0),
                        "shares": position,
                        "pnl_pct": round(pnl_pct, 2),
                        "reason": reason,
                    })
                    position = 0
                    entry_price = 0

        # 최종 청산
        final_equity = capital + position * ohlcv["close"].iloc[-1]
        total_return = (final_equity / self.initial_capital - 1) * 100

        # 성과 지표
        eq_df = pd.DataFrame(equity_curve)
        if not eq_df.empty:
            eq_df["return"] = eq_df["equity"].pct_change()
            sharpe = 0
            if eq_df["return"].std() > 0:
                sharpe = eq_df["return"].mean() / eq_df["return"].std() * np.sqrt(252)
            max_dd = self._max_drawdown(eq_df["equity"])
        else:
            sharpe = 0
            max_dd = 0

        win_trades = [t for t in trades if t["action"] == "SELL" and t.get("pnl_pct", 0) > 0]
        lose_trades = [t for t in trades if t["action"] == "SELL" and t.get("pnl_pct", 0) <= 0]

        return {
            "code": code,
            "name": name,
            "market": market,
            "strategy": strategy,
            "period_months": period,
            "initial_capital": self.initial_capital,
            "final_equity": round(final_equity, 0),
            "total_return_pct": round(total_return, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "total_trades": len([t for t in trades if t["action"] == "SELL"]),
            "win_rate": round(len(win_trades) / max(1, len(win_trades) + len(lose_trades)) * 100, 1),
            "trades": trades,
        }

    def _max_drawdown(self, equity: pd.Series) -> float:
        peak = equity.expanding().max()
        dd = (equity - peak) / peak * 100
        return abs(dd.min()) if len(dd) > 0 else 0
