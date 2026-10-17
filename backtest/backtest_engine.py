"""
backtest/backtest_engine.py
============================
과거 N봉 각 시점에서 시그널을 재탐지하여
현재가 기준 수익률을 계산하는 백테스트 엔진입니다.

당일 미완성 봉 처리
-------------------
yfinance는 장 중에 당일의 미완성 봉을 포함해서 반환합니다.
미완성 봉이 포함되면 offset 계산이 밀려서
"어제 시그널"이 backtest에서 누락되는 문제가 발생합니다.

→ 데이터 로드 후 오늘 날짜의 봉이 있으면 자동으로 제거합니다.
  이렇게 하면 offset=1 이 항상 "가장 최근 완성 봉(어제)"을 가리킵니다.
"""

import sys
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from config.settings import Config
from scanner.data_fetcher import DataFetcher
from scanner.ichimoku_analyzer import IchimokuAnalyzer
from scanner.cup_handle_analyzer import CupHandleAnalyzer
from scanner.candle_analyzer import CandleAnalyzer
from scanner.bollinger_analyzer import BollingerAnalyzer


class BacktestEngine:

    def __init__(self,
                 ichimoku: IchimokuAnalyzer,
                 cup: CupHandleAnalyzer,
                 candle: CandleAnalyzer,
                 cfg: Config = None,
                 bollinger: BollingerAnalyzer = None):
        self.ich    = ichimoku
        self.cup    = cup
        self.candle = candle
        self.cfg    = cfg or Config()
        self.bb     = bollinger or BollingerAnalyzer(self.cfg)

    # ── 당일 미완성 봉 제거 ────────────────────────────────────────────
    @staticmethod
    def _strip_incomplete_bar(raw: pd.DataFrame) -> pd.DataFrame:
        """
        yfinance가 당일 미완성 봉을 포함한 경우 제거합니다.

        예) 장 중 실행 시 오늘 봉이 마지막에 포함되어 있으면 삭제.
        완성된 봉(어제)이 가장 최근 봉이 되어 offset 계산이 정확해집니다.
        """
        if raw.empty:
            return raw
        today = pd.Timestamp(datetime.date.today())
        last_bar_date = raw.index[-1].normalize() if raw.index.tz is None \
            else raw.index[-1].tz_localize(None).normalize()

        if last_bar_date >= today:
            raw = raw.iloc[:-1].copy()
        return raw

    # ── 단일 티커 백테스트 ─────────────────────────────────────────────
    def backtest_ticker(self, ticker: str, period: str, interval: str,
                        lookback_days: int, analyze_type: str) -> list[dict]:
        """
        단일 티커의 최근 lookback_days 봉 각 시점에서 시그널 탐지 후
        수익률을 계산한 결과 리스트를 반환합니다.

        offset 구조
        -----------
        offset=1 → 가장 최근 완성 봉 (어제)
        offset=2 → 2거래일 전
        ...
        offset=N → N거래일 전
        """
        raw = DataFetcher.fetch_with_cfg(ticker, period, interval, self.cfg)
        if raw.empty or len(raw) < 120:
            return []

        # ★ 당일 미완성 봉 제거
        raw = self._strip_incomplete_bar(raw)
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
            elif analyze_type == "bollinger":
                res = self.bb.analyze_at(raw, current_close, target_idx)
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
