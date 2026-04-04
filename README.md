# 📊 Stock Monitor

주식 매수추천 & 관심종목 모니터링 — 데이터 기반 스코어링 + 매수/매도 타이밍 시그널

## 전략

**듀얼 전략 운용**

| | 중기 모멘텀 스윙 | 장기 가치성장 |
|---|---|---|
| 보유기간 | 2~8주 | 6개월~1년+ |
| 포트폴리오 비중 | 40% | 60% |
| 핵심 분석 | 기술적 분석 50% | 펀더멘털 55% |
| 리밸런싱 | 주간 | 월간 |

- 대상 시장: KOSPI, KOSDAQ, NASDAQ, S&P500
- 기술주 비중: 60~70% 자동 조절
- 3층 스코어링: 기술적 + 펀더멘털 + 모멘텀

## 사용법

```bash
# 의존성 설치
pip install -r requirements.txt

# 일일 스크리닝 리포트 (옵시디언 자동 저장)
python main.py daily

# 관심종목 모니터링
python main.py watchlist

# 단일 종목 스코어링
python main.py score NVDA NASDAQ
python main.py score 005930 KOSPI

# 백테스팅
python main.py backtest NVDA NASDAQ --strategy midterm
python main.py backtest 005930 KOSPI --strategy longterm
```

## 데이터 소스

| 시장 | 소스 | API 키 |
|------|------|--------|
| KOSPI/KOSDAQ | pykrx, FinanceDataReader | 불필요 |
| NASDAQ/S&P500 | yfinance | 불필요 |

## 스코어링 체계

| 점수 | 시그널 | 액션 |
|------|--------|------|
| 80~100 | 강력매수 | 즉시 매수 검토 |
| 65~79 | 매수관심 | 관심종목 등록, 진입점 대기 |
| 50~64 | 중립 | 보유 유지 |
| 35~49 | 매도관심 | 손절/익절 검토 |
| 0~34 | 강력매도 | 즉시 매도 검토 |

## 자동 실행

매일 오전 8시(KST) Windows Task Scheduler로 자동 실행 → 옵시디언 볼트에 리포트 저장

## 프로젝트 구조

```
stock-monitor/
├── config/
│   ├── strategy.yaml     # 전략 설정 (가중치, 임계값)
│   ├── watchlist.yaml    # 관심종목 리스트
│   └── sectors.yaml      # 기술주 섹터 분류
├── src/
│   ├── data/fetcher.py       # 데이터 수집 (pykrx, yfinance)
│   ├── indicators/
│   │   ├── technical.py      # 기술적 지표 (RSI, MACD, BB, MA, Vol, Stoch)
│   │   ├── fundamental.py    # 펀더멘털 (PER, PBR, ROE, 성장률)
│   │   └── momentum.py       # 모멘텀 (52주, 수급, 상대강도)
│   ├── scoring/engine.py     # 종합 스코어링 엔진
│   ├── signals/screener.py   # 종목 스크리너
│   ├── backtest/backtester.py # 백테스팅 엔진
│   └── report/generator.py   # 옵시디언 리포트 생성
├── main.py                   # CLI 진입점
└── requirements.txt
```
