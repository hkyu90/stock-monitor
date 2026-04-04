"""
데이터 수집 모듈
한국: pykrx, FinanceDataReader / 미국: yfinance
모든 소스 무료, API 키 불필요
"""

import datetime as dt
import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class KRXFetcher:
    """KOSPI / KOSDAQ 데이터 수집"""

    def __init__(self):
        from pykrx import stock as pykrx_stock
        self.pykrx = pykrx_stock

    def get_universe(self, market: str, date: str | None = None) -> pd.DataFrame:
        """시장 전체 종목 리스트 + 기본 정보"""
        if date is None:
            date = dt.date.today().strftime("%Y%m%d")

        tickers = self.pykrx.get_market_ticker_list(date, market=market)
        rows = []
        for ticker in tickers:
            name = self.pykrx.get_market_ticker_name(ticker)
            rows.append({"code": ticker, "name": name, "market": market})

        return pd.DataFrame(rows)

    def get_ohlcv(self, code: str, start: str, end: str) -> pd.DataFrame:
        """일봉 OHLCV 데이터"""
        df = self.pykrx.get_market_ohlcv_by_date(start, end, code)
        # pykrx 컬럼: 시가, 고가, 저가, 종가, 거래량, (등락률)
        cols = df.columns.tolist()
        rename_map = {cols[0]: "open", cols[1]: "high", cols[2]: "low", cols[3]: "close", cols[4]: "volume"}
        df = df.rename(columns=rename_map)
        df.index.name = "date"
        return df[["open", "high", "low", "close", "volume"]]

    def get_market_cap(self, code: str, date: str) -> dict:
        """시가총액 및 주식수"""
        df = self.pykrx.get_market_cap_by_date(date, date, code)
        if df.empty:
            return {}
        row = df.iloc[-1]
        return {
            "market_cap": row.get("시가총액", 0),
            "shares": row.get("상장주식수", 0),
        }

    def get_fundamental(self, code: str, date: str) -> dict:
        """PER, PBR, EPS, BPS 등"""
        df = self.pykrx.get_market_fundamental_by_date(date, date, code)
        if df.empty:
            return {}
        row = df.iloc[-1]
        return {
            "per": row.get("PER", None),
            "pbr": row.get("PBR", None),
            "eps": row.get("EPS", None),
            "bps": row.get("BPS", None),
            "div_yield": row.get("DIV", None),
        }

    def get_investor_trading(self, code: str, start: str, end: str) -> pd.DataFrame:
        """외국인/기관 순매수 추이"""
        df = self.pykrx.get_market_trading_value_by_date(
            start, end, code, detail=True
        )
        return df

    def get_sector(self, code: str, date: str) -> str:
        """KRX 업종 분류"""
        try:
            sector_df = self.pykrx.get_market_sector_classifications(date, "KOSPI")
            if code in sector_df.index:
                return sector_df.loc[code, "업종"]
        except Exception:
            pass
        return "기타"


class USFetcher:
    """NASDAQ / S&P500 데이터 수집"""

    def __init__(self):
        import yfinance as yf
        self.yf = yf

    def get_universe(self, market: str) -> pd.DataFrame:
        """S&P500 또는 NASDAQ 종목 리스트"""
        import FinanceDataReader as fdr

        if market == "SP500":
            df = fdr.StockListing("S&P500")
        elif market == "NASDAQ":
            df = fdr.StockListing("NASDAQ")
        else:
            return pd.DataFrame()

        result = df.rename(columns={
            "Symbol": "code",
            "Name": "name",
            "IndustryCode": "industry_code",
            "Industry": "industry",
            "Sector": "sector",
        })
        result["market"] = market
        return result

    def get_ohlcv(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """일봉 OHLCV 데이터"""
        stock = self.yf.Ticker(ticker)
        df = stock.history(start=start, end=end)
        if df.empty:
            return df
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        df.index.name = "date"
        return df[["open", "high", "low", "close", "volume"]]

    def get_info(self, ticker: str) -> dict:
        """종목 기본 정보 (시총, PER, 섹터 등)"""
        stock = self.yf.Ticker(ticker)
        info = stock.info
        return {
            "market_cap": info.get("marketCap", 0),
            "per": info.get("trailingPE", None),
            "forward_per": info.get("forwardPE", None),
            "pbr": info.get("priceToBook", None),
            "roe": info.get("returnOnEquity", None),
            "revenue_growth": info.get("revenueGrowth", None),
            "earnings_growth": info.get("earningsGrowth", None),
            "operating_margin": info.get("operatingMargins", None),
            "debt_to_equity": info.get("debtToEquity", None),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "eps": info.get("trailingEps", None),
            "dividend_yield": info.get("dividendYield", None),
        }

    def get_financials(self, ticker: str) -> dict:
        """재무제표 요약"""
        stock = self.yf.Ticker(ticker)
        try:
            income = stock.income_stmt
            if income is not None and not income.empty:
                latest = income.iloc[:, 0]
                return {
                    "total_revenue": latest.get("Total Revenue", None),
                    "operating_income": latest.get("Operating Income", None),
                    "net_income": latest.get("Net Income", None),
                }
        except Exception:
            pass
        return {}


class DataFetcher:
    """통합 데이터 수집기"""

    def __init__(self):
        self.krx = KRXFetcher()
        self.us = USFetcher()

    def fetch_ohlcv(self, code: str, market: str, days: int = 250) -> pd.DataFrame:
        """시장에 맞는 OHLCV 가져오기"""
        end = dt.date.today()
        start = end - dt.timedelta(days=days)
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        try:
            if market in ("KOSPI", "KOSDAQ"):
                return self.krx.get_ohlcv(code, start_str, end_str)
            else:
                start_fmt = start.strftime("%Y-%m-%d")
                end_fmt = end.strftime("%Y-%m-%d")
                return self.us.get_ohlcv(code, start_fmt, end_fmt)
        except Exception as e:
            logger.warning(f"OHLCV fetch failed for {code}: {e}")
            return pd.DataFrame()

    def fetch_fundamental(self, code: str, market: str) -> dict:
        """시장에 맞는 펀더멘털 가져오기"""
        try:
            if market in ("KOSPI", "KOSDAQ"):
                date = dt.date.today().strftime("%Y%m%d")
                fund = self.krx.get_fundamental(code, date)
                cap = self.krx.get_market_cap(code, date)
                return {**fund, **cap}
            else:
                return self.us.get_info(code)
        except Exception as e:
            logger.warning(f"Fundamental fetch failed for {code}: {e}")
            return {}
