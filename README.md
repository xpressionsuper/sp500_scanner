# 📈 US Mid-Large Cap Stock Scanner

S&P 500 (대형주) + S&P 400 MidCap (중형주) 약 900개 종목을 대상으로
**일목균형표 / 컵앤핸들 / 캔들 패턴** 매수 시그널을 자동으로 스캔하고
백테스트 결과까지 Excel 리포트로 출력하는 Python 모듈입니다.

---

## 📁 폴더 구조

```
sp500_scanner/
├── main.py                        ← 실행 진입점
├── requirements.txt
├── .gitignore
│
├── config/
│   └── settings.py                ← 전역 설정값 (여기서만 수정)
│
├── scanner/
│   ├── data_fetcher.py            ← 티커 수집 & yfinance 데이터 로드
│   ├── ichimoku_analyzer.py       ← 일목균형표 계산 + 시그널 탐지
│   ├── cup_handle_analyzer.py     ← 컵앤핸들 패턴 탐지
│   ├── candle_analyzer.py         ← 캔들 패턴 탐지 (샛별형 도지 / 관통형)
│   └── scanner_runner.py          ← 병렬 스캔 총괄
│
├── backtest/
│   └── backtest_engine.py         ← 과거 시그널 → 현재 수익률 백테스트
│
└── report/
    └── report_exporter.py         ← xlsx 다중 시트 + PNG 이미지 저장
```

---

## ⚡ 빠른 시작

```bash
# 1. 저장소 클론
git clone https://github.com/YOUR_ID/sp500_scanner.git
cd sp500_scanner

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 실행
python main.py
```

실행이 완료되면 현재 디렉터리에 아래 파일이 생성됩니다.

| 파일 | 설명 |
|------|------|
| `Scanner_Report_YYYYMMDD.xlsx` | 전체 결과 (7개 시트) |
| `Result_Ichimoku_*.png` | 일목균형표 시그널 이미지 |
| `Result_CupHandle_*.png` | 컵앤핸들 시그널 이미지 |
| `Result_Candle_*.png` | 캔들 패턴 시그널 이미지 |
| `Result_BT_*.png` | 백테스트 결과 이미지 |

---

## ⚙️ 설정 변경 (`config/settings.py`)

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `UNIVERSES` | `["sp500","sp400"]` | 스캔 대상 지수. `["sp500"]` 으로 변경하면 S&P 500만 |
| `BACKTEST_DAYS` | `14` | 백테스트 소급 거래일 수 |
| `RUN_BACKTEST` | `True` | `False` 로 설정 시 백테스트 건너뜀 |
| `MAX_WORKERS` | `15` | 병렬 처리 스레드 수 |

### 타임프레임 변경 (`main.py`)

```python
# 일봉만
SCAN_TIMEFRAMES = ["일봉"]

# 일봉 + 주봉 (기본값)
SCAN_TIMEFRAMES = ["일봉", "주봉"]

# 일봉 + 주봉 + 월봉
SCAN_TIMEFRAMES = ["일봉", "주봉", "월봉"]
```

---

## 📊 스캔 패턴 설명

### 일목균형표
| 시그널 | 조건 |
|--------|------|
| 구름 돌파 | 전봉 종가 ≤ 구름 상단 → 당봉 종가 > 구름 상단 × 1.005 (적색 구름) |
| 지지 반등 | 녹색 구름 상단 근처 눌림 후 반등 + 전환>기준 + 기울기 양수 |

공통 필터: 구름 거리 ≤ 10% / 52주 위치 ≥ 20%(지지반등) / 기준선 기울기 양수(지지반등)

### 컵앤핸들
윌리엄 오닐 기준: 컵 깊이 12~35% / 핸들 조정폭 < 컵 깊이 × 50% / 현재가 ≥ 핸들 고점 × 98%

### 캔들 패턴
| 패턴 | 조건 |
|------|------|
| 샛별형 도지 | 장대음봉(5일선 아래) → 갭하락 도지 → 양봉 반등 |
| 관통형 | 장대음봉(5일선 아래) → 갭하락 후 전봉 몸통 50% 이상 돌파 |

---

## 🗂️ Excel 리포트 시트 구성

| 시트 | 내용 |
|------|------|
| 일목균형표 | 일목균형표 매수 시그널 종목 |
| 컵앤핸들 | 컵앤핸들 패턴 종목 |
| 캔들패턴 | 캔들 패턴 종목 |
| 백테스트_일목 | 과거 N일 일목 시그널 → 현재 수익률 |
| 백테스트_컵핸들 | 과거 N일 컵핸들 시그널 → 현재 수익률 |
| 백테스트_캔들 | 과거 N일 캔들 시그널 → 현재 수익률 |
| 분석요약 | 전체 시그널 수 요약 |

---

## ⚠️ 주의사항

- 본 도구는 **기술적 분석 참고용**이며 투자 권유가 아닙니다.
- 실제 매매 시 거래량, 섹터 모멘텀, 재무 지표를 반드시 확인하세요.
- yfinance 데이터는 당일 기준으로 1 거래일 지연될 수 있습니다.
