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

## 보유 포트폴리오 (2026-04-04 기준)

**한국 12종목**

| 종목 | 코드 | 수량 | 매수가 |
|------|------|------|--------|
| TIGER 미국S&P500(H) | 448290 | 10 | 13,245 |
| TIGER 미국나스닥100(H) | 448300 | 10 | 15,803 |
| 삼성전자 | 005930 | 2 | 172,550 |
| 에코프로비엠 | 247540 | 7 | 472,929 |
| 토모큐브 | 475960 | 5 | 52,660 |
| 나라스페이스테크놀로지 | 478340 | 14 | 54,396 |
| 프로티나 | 468530 | 1 | 80,300 |
| 코난테크놀로지 | 402030 | 10 | 24,375 |
| 본느 | 226340 | 60 | 937 |
| 신송홀딩스 | 006880 | 137 | 7,989 |
| 화신 | 010690 | 6 | 21,366 |
| 풍산 | 103140 | 2 | 112,050 |

**미국 11종목**

| 종목 | 티커 | 수량 | 매수가(USD) |
|------|------|------|-------------|
| 네비우스 그룹 | NBIS | 12 | 62.72 |
| 테슬라 | TSLA | 3 | 232.39 |
| 팔란티어 | PLTR | 6 | 139.61 |
| 코어위브 | CRWV | 9 | 128.88 |
| 엔비디아 | NVDA | 3 | 112.60 |
| 애플 | AAPL | 2 | 208.21 |
| 알파벳A | GOOGL | 1 | 172.34 |
| 인텔 | INTC | 4 | 22.45 |
| 아이온큐 | IONQ | 6 | 48.79 |
| 써클 인터넷 그룹 | CRCL | 1 | 145.56 |
| 리게티 컴퓨팅 | RGTI | 2 | 28.39 |

## 사용법

```bash
# 의존성 설치
pip install -r requirements.txt

# 일일 스크리닝 리포트 (옵시디언 자동 저장)
python main.py daily

# 보유종목 매도 시그널 + 관심종목 매수 시그널
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

## 리포트 출력

- 옵시디언 볼트: `06_개인/주식모니터링/`
- 매일 오전 8시(KST) Windows Task Scheduler 자동 실행
- 보유종목별 수익률 + 매도 시그널 (익절/손절/기술적 시그널)
- 포트폴리오 요약 (총 투자원금, 평가액, 수익률)

## 프로젝트 구조

```
stock-monitor/
├── config/
│   ├── strategy.yaml     # 전략 설정 (가중치, 임계값)
│   ├── watchlist.yaml    # 보유종목 + 관심종목 리스트
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
├── run_daily.bat             # 자동 실행 배치
├── setup_schedule.bat        # Task Scheduler 등록
└── requirements.txt
```
