"""
backtest/backtest_engine.py
============================
과거 N봉 각 시점에서 시그널을 재탐지하여
현재가 기준 수익률을 계산하는 백테스트 엔진입니다.

IchimokuAnalyzer / CupHandleAnalyzer / CandleAnalyzer 를
의존성 주입(DI) 방식으로 받아 사용합니다.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from config.settings import Config
from scanner.data_fetcher import DataFetcher
from scanner.ichimoku_analyzer import IchimokuAnalyzer
from scanner.cup_handle_analyzer import CupHandleAnalyzer
from scanner.candle_analyzer import CandleAnalyzer


class BacktestEngine:

    def __init__(self,
                 ichimoku: IchimokuAnalyzer,
                 cup: CupHandleAnalyzer,
                 candle: CandleAnalyzer,
                 cfg: Config = None):
        self.ich    = ichimoku
        self.cup    = cup
        self.candle = candle
        self.cfg    = cfg or Config()

    # ── 단일 티커 백테스트 ─────────────────────────────────────────────
    def backtest_ticker(self, ticker: str, period: str, interval: str,
                        lookback_days: int, analyze_type: str) -> list[dict]:
        """
        단일 티커의 최근 lookback_days 봉 각 시점에서 시그널 탐지 후
        수익률을 계산한 결과 리스트를 반환합니다.

        Parameters
        ----------
        ticker        : 티커 심볼
        period        : 데이터 수집 기간
        interval      : 봉 단위 ("1d", "1wk", "1mo")
        lookback_days : 소급 봉 수
        analyze_type  : "ichimoku" | "cup" | "candle"
        """
        raw = DataFetcher.fetch(ticker, period, interval)
        if raw.empty or len(raw) < 120:
            return []

        current_close = float(raw["Close"].iloc[-1])
        total_bars    = len(raw)
        results       = []

        for offset in range(1, lookback_days + 1):
            target_idx = total_bars - 1 - offset
            if target_idx < 100:
                continue

            signal_date = raw.index[target_idx].strftime("%Y-%m-%d")

            if analyze_type == "ichimoku":
                res = self.ich.analyze_at(raw, current_close, target_idx)
            elif analyze_type == "cup":
                res = self.cup.analyze_at(raw, current_close, target_idx)
            else:  # candle
                res = self.candle.analyze_at(raw, current_close, target_idx)

            if res:
                row = {
                    "티커":       ticker,
                    "시그널 날짜": signal_date,
                    "타임프레임":  IchimokuAnalyzer._tf_label(interval),
                    "현재가 ($)": round(current_close, 2),
                }
                row.update(res)
                results.append(row)

        return results

    # ── 전체 티커 병렬 백테스트 ───────────────────────────────────────
    def run(self, tickers: list[str], period: str, interval: str,
            lookback_days: int, analyze_type: str,
            label: str = "백테스트") -> pd.DataFrame:
        """
        전체 티커에 대한 병렬 백테스트를 실행합니다.

        Returns
        -------
        pd.DataFrame : 날짜 내림차순 → 수익률 내림차순 정렬
        """
        all_results = []
        total = len(tickers)
        done  = 0
        start = time.time()

        with ThreadPoolExecutor(max_workers=self.cfg.MAX_WORKERS) as executor:
            future_map = {
                executor.submit(
                    self.backtest_ticker, t, period, interval,
                    lookback_days, analyze_type
                ): t for t in tickers
            }
            for future in as_completed(future_map):
                ticker = future_map[future]
                done  += 1
                try:
                    rows = future.result()
                    if rows:
                        all_results.extend(rows)
                        tag = f"✅ {ticker:<6} {len(rows)}건"
                    else:
                        tag = f"   {ticker:<6}"
                except Exception:
                    tag = f"❌ {ticker:<6}"

                self._print_progress(done, total, start, tag)

        elapsed = time.time() - start
        print(f"\n\n  ⏱  {label} 완료: {elapsed:.1f}초 | {len(all_results)}건\n")

        if not all_results:
            return pd.DataFrame()

        df = pd.DataFrame(all_results)
        df = df.sort_values(
            ["시그널 날짜", "수익률 (%)"], ascending=[False, False]
        ).reset_index(drop=True)
        return df

    # ── 진행률 출력 ────────────────────────────────────────────────────
    @staticmethod
    def _print_progress(done: int, total: int, start: float, tag: str) -> None:
        elapsed = time.time() - start
        eta     = (elapsed / done) * (total - done) if done else 0
        pct     = done / total * 100
        bar     = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
        sys.stdout.write(
            f"\r  [{bar}] {pct:5.1f}%  {done}/{total}  "
            f"ETA {eta:4.0f}s  {tag:<35}"
        )
        sys.stdout.flush()
