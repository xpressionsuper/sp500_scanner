"""
main.py — 스캐너 실행 진입점
==============================
설정 변경은 config/settings.py 에서 합니다.
실행: python main.py
"""

import warnings
from datetime import datetime

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


def main() -> None:

    # ── 1. 설정 ───────────────────────────────────────────────────────
    cfg = Config()

    # 스캔 타임프레임: ["일봉"] / ["일봉","주봉"] / ["일봉","주봉","월봉"]
    SCAN_TIMEFRAMES = ["일봉", "주봉"]

    # 백테스트 타임프레임: (interval, period, 레이블)
    # 월봉 추가 시 ("1mo", "5y", "월봉") 를 리스트에 추가
    BACKTEST_TIMEFRAMES = [
        ("1d",  "2y", "일봉"),
        ("1wk", "3y", "주봉"),
    ]

    today = datetime.today().strftime("%Y%m%d")

    # ── 2. 의존성 주입 (DI) ───────────────────────────────────────────
    ich_analyzer    = IchimokuAnalyzer(cfg)
    cup_analyzer    = CupHandleAnalyzer(cfg)
    candle_analyzer = CandleAnalyzer(cfg)
    bt_engine       = BacktestEngine(ich_analyzer, cup_analyzer, candle_analyzer, cfg)
    scanner         = ScannerRunner(ich_analyzer, cup_analyzer, candle_analyzer, cfg)
    exporter        = ReportExporter(cfg)

    # ── 3. 티커 수집 ──────────────────────────────────────────────────
    # 수집 범위는 config/settings.py 의 UNIVERSES 로 조정
    #   ["sp500"]         → S&P 500만  (~500개)
    #   ["sp500","sp400"] → 중형주 포함 (~900개)
    tickers = DataFetcher.get_tickers(cfg)

    # ── 4. 스캔 ───────────────────────────────────────────────────────
    scan_results = scanner.run_all(tickers, timeframes=SCAN_TIMEFRAMES)
    final_ich    = scan_results["ichimoku"]
    final_cup    = scan_results["cup"]
    final_candle = scan_results["candle"]

    # ── 5. 백테스트 ───────────────────────────────────────────────────
    df_bt_ich    = pd.DataFrame()
    df_bt_cup    = pd.DataFrame()
    df_bt_candle = pd.DataFrame()

    if cfg.RUN_BACKTEST:
        bt_ich_frames    = []
        bt_cup_frames    = []
        bt_candle_frames = []

        for interval, period, tf_name in BACKTEST_TIMEFRAMES:
            print(f"\n🔍 [백테스트] 일목균형표 {tf_name}\n")
            df = bt_engine.run(tickers, period=period, interval=interval,
                               lookback_days=cfg.BACKTEST_DAYS,
                               analyze_type="ichimoku",
                               label=f"일목 {tf_name} 백테스트")
            if not df.empty: bt_ich_frames.append(df)

            print(f"\n🔍 [백테스트] 컵앤핸들 {tf_name}\n")
            df = bt_engine.run(tickers, period=period, interval=interval,
                               lookback_days=cfg.BACKTEST_DAYS,
                               analyze_type="cup",
                               label=f"컵앤핸들 {tf_name} 백테스트")
            if not df.empty: bt_cup_frames.append(df)

            print(f"\n🔍 [백테스트] 캔들 패턴 {tf_name}\n")
            df = bt_engine.run(tickers, period=period, interval=interval,
                               lookback_days=cfg.BACKTEST_DAYS,
                               analyze_type="candle",
                               label=f"캔들 {tf_name} 백테스트")
            if not df.empty: bt_candle_frames.append(df)

        df_bt_ich    = pd.concat(bt_ich_frames,    ignore_index=True) if bt_ich_frames    else pd.DataFrame()
        df_bt_cup    = pd.concat(bt_cup_frames,    ignore_index=True) if bt_cup_frames    else pd.DataFrame()
        df_bt_candle = pd.concat(bt_candle_frames, ignore_index=True) if bt_candle_frames else pd.DataFrame()

        # 백테스트 콘솔 요약
        print("\n" + "=" * 65)
        print(f"  📊  백테스트 요약 (최근 {cfg.BACKTEST_DAYS}거래일)")
        print("=" * 65)
        for name, df_bt in [("일목균형표", df_bt_ich),
                             ("컵앤핸들",   df_bt_cup),
                             ("캔들 패턴",  df_bt_candle)]:
            if not df_bt.empty and "수익률 (%)" in df_bt.columns:
                avg  = df_bt["수익률 (%)"].mean()
                pos  = (df_bt["수익률 (%)"] >= 0).sum()
                neg  = (df_bt["수익률 (%)"] < 0).sum()
                print(f"  {name}: 총 {len(df_bt)}건 | "
                      f"수익 {pos}건 / 손실 {neg}건 | 평균 {avg:+.2f}%")
            else:
                print(f"  {name}: 시그널 없음")
        print("=" * 65)

    # ── 6. 콘솔 최종 요약 ─────────────────────────────────────────────
    total = len(final_ich) + len(final_cup) + len(final_candle)
    print("\n" + "=" * 65)
    print("  📊  오늘 스캔 요약")
    print("=" * 65)
    print(f"  일목균형표 시그널: {len(final_ich)}개")
    print(f"  컵앤핸들 패턴:     {len(final_cup)}개")
    print(f"  캔들 패턴:         {len(final_candle)}개")
    print(f"  합계:              {total}개")
    print("=" * 65)

    # ── 7. 결과 저장 ──────────────────────────────────────────────────
    any_result = any([
        not final_ich.empty, not final_cup.empty, not final_candle.empty,
        not df_bt_ich.empty, not df_bt_cup.empty, not df_bt_candle.empty,
    ])

    if not any_result:
        print("\n⚠️ 검색 조건에 부합하는 종목이 없습니다.")
        return

    fname = f"Scanner_Report_{today}.xlsx"
    exporter.save_xlsx(
        fname,
        final_ich, final_cup, final_candle,
        df_bt_ich=df_bt_ich, df_bt_cup=df_bt_cup, df_bt_candle=df_bt_candle,
    )

    # 이미지 저장
    _save_images(exporter, today, cfg,
                 final_ich, final_cup, final_candle,
                 df_bt_ich, df_bt_cup, df_bt_candle)

    print(f"\n✅ 모든 분석이 완료되었습니다.")
    print(f"   📂 엑셀 리포트: {fname}")


def _save_images(exporter: ReportExporter, today: str, cfg: Config,
                 final_ich, final_cup, final_candle,
                 df_bt_ich, df_bt_cup, df_bt_candle) -> None:
    """결과 이미지를 저장합니다."""
    ich_cols    = ["티커","타임프레임","시그널 유형","종가 ($)",
                   "구름 거리 (%)","52주 위치 (%)","기준선 기울기 (%)","구름 색","전환>기준"]
    cup_cols    = ["티커","타임프레임","시그널 유형","종가 ($)",
                   "돌파선까지 (%)","컵 깊이 (%)","52주 위치 (%)","컵 왼쪽 고점","컵 바닥","돌파 기준선"]
    candle_cols = ["티커","타임프레임","시그널 유형","종가 ($)","52주 위치 (%)","시가","고가","저가"]

    if not final_ich.empty:
        exporter.save_image(
            final_ich[[c for c in ich_cols if c in final_ich.columns]],
            f"Result_Ichimoku_{today}.png", "일목균형표 매수 시그널"
        )
    if not final_cup.empty:
        exporter.save_image(
            final_cup[[c for c in cup_cols if c in final_cup.columns]],
            f"Result_CupHandle_{today}.png", "컵앤핸들 패턴 스캔 결과"
        )
    if not final_candle.empty:
        exporter.save_image(
            final_candle[[c for c in candle_cols if c in final_candle.columns]],
            f"Result_Candle_{today}.png", "캔들 패턴 스캔 결과"
        )

    bt_ich_cols    = ["티커","시그널 날짜","시그널 유형","진입가 ($)","현재가 ($)","수익률 (%)","구름 거리(%)"]
    bt_cup_cols    = ["티커","시그널 날짜","시그널 유형","진입가 ($)","현재가 ($)","수익률 (%)","돌파선까지(%)"]
    bt_candle_cols = ["티커","시그널 날짜","시그널 유형","진입가 ($)","현재가 ($)","수익률 (%)","시가","고가","저가"]

    exporter.save_image(
        df_bt_ich[[c for c in bt_ich_cols if c in df_bt_ich.columns]] if not df_bt_ich.empty else pd.DataFrame(),
        f"Result_BT_Ichimoku_{today}.png",
        f"일목균형표 백테스트 (최근 {cfg.BACKTEST_DAYS}거래일)"
    )
    exporter.save_image(
        df_bt_cup[[c for c in bt_cup_cols if c in df_bt_cup.columns]] if not df_bt_cup.empty else pd.DataFrame(),
        f"Result_BT_CupHandle_{today}.png",
        f"컵앤핸들 백테스트 (최근 {cfg.BACKTEST_DAYS}거래일)"
    )
    exporter.save_image(
        df_bt_candle[[c for c in bt_candle_cols if c in df_bt_candle.columns]] if not df_bt_candle.empty else pd.DataFrame(),
        f"Result_BT_Candle_{today}.png",
        f"캔들 패턴 백테스트 (최근 {cfg.BACKTEST_DAYS}거래일)"
    )


if __name__ == "__main__":
    main()
