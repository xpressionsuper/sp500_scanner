"""
main.py — 스캐너 실행 진입점
==============================
설정 변경은 config/settings.py 에서 합니다.
실행: python main.py  →  index.html (GitHub Pages 로 배포)
"""

import warnings

import pandas as pd

warnings.filterwarnings("ignore")

from config.settings import Config
from scanner.data_fetcher import DataFetcher
from scanner.ichimoku_analyzer import IchimokuAnalyzer
from scanner.cup_handle_analyzer import CupHandleAnalyzer
from scanner.candle_analyzer import CandleAnalyzer
from scanner.scanner_runner import ScannerRunner
from backtest.backtest_engine import BacktestEngine
from report.report_exporter import ReportExporter

# 표시 순서: 볼린저 → 일목 → 캔들 → 컵앤핸들
# (결과 키, 이름, 백테스트 analyze_type, 차트 종류)
SIGNALS = [
    ("bollinger", "볼린저 밴드", "bollinger", "bollinger"),
    ("ichimoku",  "일목균형표",  "ichimoku",  "ichimoku"),
    ("candle",    "캔들 패턴",   "candle",    "ichimoku"),
    ("cup",       "컵앤핸들",    "cup",       "ichimoku"),
]


def main() -> None:

    # ── 1. 설정
    cfg = Config()
    SCAN_TIMEFRAMES = ["일봉", "주봉"]
    BACKTEST_TIMEFRAMES = [
        ("1d",  "2y", "일봉"),
        ("1wk", "3y", "주봉"),
    ]
    if cfg.SCAN_END_DATE:
        print(f"  📅 스캔 기준 날짜: {cfg.SCAN_END_DATE} (과거 재현 모드)")

    # ── 2. 의존성 주입
    ich_analyzer    = IchimokuAnalyzer(cfg)
    cup_analyzer    = CupHandleAnalyzer(cfg)
    candle_analyzer = CandleAnalyzer(cfg)
    bt_engine       = BacktestEngine(ich_analyzer, cup_analyzer, candle_analyzer, cfg)
    scanner         = ScannerRunner(ich_analyzer, cup_analyzer, candle_analyzer, cfg)
    exporter        = ReportExporter(cfg)

    # ── 3. 티커 수집
    tickers = DataFetcher.get_tickers(cfg)

    # ── 4. 스캔
    scan = scanner.run_all(tickers, timeframes=SCAN_TIMEFRAMES)

    # ── 5. 백테스트
    bt = {key: pd.DataFrame() for key, *_ in SIGNALS}
    if cfg.RUN_BACKTEST:
        for key, name, bt_type, _ in SIGNALS:
            frames = []
            for interval, period, tf_name in BACKTEST_TIMEFRAMES:
                print(f"\n🔍 [백테스트] {name} {tf_name}\n")
                df = bt_engine.run(tickers, period=period, interval=interval,
                                   lookback_days=cfg.BACKTEST_DAYS, analyze_type=bt_type,
                                   label=f"{name} {tf_name} 백테스트")
                if not df.empty:
                    frames.append(df)
            bt[key] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        print("\n" + "=" * 65)
        print(f"  📊  백테스트 요약 (최근 {cfg.BACKTEST_DAYS}거래일)")
        print("=" * 65)
        for key, name, *_ in SIGNALS:
            r = bt[key].get("수익률 (%)")
            if r is None or r.empty:
                print(f"  {name}: 시그널 없음")
            else:
                print(f"  {name}: 총 {len(r)}건 | 수익 {int((r >= 0).sum())}건 / "
                      f"손실 {int((r < 0).sum())}건 | 평균 {r.mean():+.2f}%")
        print("=" * 65)

    # ── 6. 콘솔 요약
    print("\n" + "=" * 65)
    print("  📊  오늘 스캔 요약")
    print("=" * 65)
    print("  " + "  |  ".join(f"{name}: {len(scan[key])}개" for key, name, *_ in SIGNALS)
          + f"  |  합계: {sum(len(scan[key]) for key, *_ in SIGNALS)}개")
    print("=" * 65)

    # ── 7. HTML (결과가 없어도 항상 생성 → Pages 배포)
    exporter.save_html("index.html",
        [(name, scan[key], chart) for key, name, _, chart in SIGNALS] +
        [(f"백테스트·{name}", bt[key], None) for key, name, *_ in SIGNALS])


if __name__ == "__main__":
    main()
