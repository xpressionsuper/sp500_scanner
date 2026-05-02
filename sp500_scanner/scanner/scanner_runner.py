"""
scanner/scanner_runner.py
=========================
IchimokuAnalyzer / CupHandleAnalyzer / CandleAnalyzer 의
병렬 스캔 실행을 총괄합니다.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from config.settings import Config
from scanner.ichimoku_analyzer import IchimokuAnalyzer
from scanner.cup_handle_analyzer import CupHandleAnalyzer
from scanner.candle_analyzer import CandleAnalyzer


class ScannerRunner:
    """
    3개 분석기(일목·컵핸들·캔들)의 병렬 스캔 실행을 총괄합니다.

    타임프레임 설정
    ---------------
    TIMEFRAMES 딕셔너리로 (interval, period) 를 관리하며,
    run_all() 의 timeframes 파라미터로 원하는 조합을 선택합니다.
    """

    TIMEFRAMES: dict[str, tuple[str, str]] = {
        "일봉": ("1d",  "2y"),
        "주봉": ("1wk", "3y"),
        "월봉": ("1mo", "5y"),
    }

    def __init__(self,
                 ichimoku: IchimokuAnalyzer,
                 cup: CupHandleAnalyzer,
                 candle: CandleAnalyzer,
                 cfg: Config = None):
        self.ich    = ichimoku
        self.cup    = cup
        self.candle = candle
        self.cfg    = cfg or Config()

    # ── 단일 분석기 × 단일 타임프레임 병렬 스캔 ──────────────────────
    def _scan_one(self, tickers: list[str], analyze_fn,
                  period: str, interval: str, label: str) -> pd.DataFrame:
        results = []
        total   = len(tickers)
        done    = 0
        start   = time.time()

        with ThreadPoolExecutor(max_workers=self.cfg.MAX_WORKERS) as executor:
            future_map = {
                executor.submit(analyze_fn, t, period, interval): t
                for t in tickers
            }
            for future in as_completed(future_map):
                ticker = future_map[future]
                done  += 1
                try:
                    res = future.result()
                    if res:
                        results.append(res)
                        tag = f"✅ {ticker:<6} {res['시그널 유형']}"
                    else:
                        tag = f"   {ticker:<6}"
                except Exception:
                    tag = f"❌ {ticker:<6}"

                self._print_progress(done, total, start, tag)

        elapsed = time.time() - start
        print(f"\n\n  ⏱  {label} 완료: {elapsed:.1f}초 | 시그널: {len(results)}개\n")
        return pd.DataFrame(results) if results else pd.DataFrame()

    # ── 전체 스캔 실행 ─────────────────────────────────────────────────
    def run_all(self, tickers: list[str],
                timeframes: list[str] = ("일봉", "주봉")) -> dict[str, pd.DataFrame]:
        """
        지정한 타임프레임 목록으로 3개 패턴 스캔을 모두 실행합니다.

        Parameters
        ----------
        tickers    : 스캔할 티커 리스트
        timeframes : ["일봉"] / ["일봉","주봉"] / ["일봉","주봉","월봉"] 등

        Returns
        -------
        dict:
            "ichimoku" : 일목균형표 결과 DataFrame
            "cup"      : 컵앤핸들   결과 DataFrame
            "candle"   : 캔들 패턴  결과 DataFrame
        """
        ich_frames    = []
        cup_frames    = []
        candle_frames = []

        for tf_name in timeframes:
            interval, period = self.TIMEFRAMES[tf_name]

            print(f"🔍 [일목균형표] {tf_name} 스캔 ({len(tickers)}개 종목)\n")
            df = self._scan_one(tickers, self.ich.analyze,
                                period, interval, f"일목 {tf_name}")
            if not df.empty:
                ich_frames.append(df)

            print(f"🔍 [컵앤핸들] {tf_name} 스캔 ({len(tickers)}개 종목)\n")
            df = self._scan_one(tickers, self.cup.analyze,
                                period, interval, f"컵앤핸들 {tf_name}")
            if not df.empty:
                cup_frames.append(df)

            print(f"🔍 [캔들 패턴] {tf_name} 스캔 ({len(tickers)}개 종목)\n")
            df = self._scan_one(tickers, self.candle.analyze,
                                period, interval, f"캔들 {tf_name}")
            if not df.empty:
                candle_frames.append(df)

        final_ich    = self._sort_ichimoku(
            pd.concat(ich_frames,    ignore_index=True) if ich_frames    else pd.DataFrame()
        )
        final_cup    = self._sort_cup(
            pd.concat(cup_frames,    ignore_index=True) if cup_frames    else pd.DataFrame()
        )
        final_candle = (
            pd.concat(candle_frames, ignore_index=True) if candle_frames else pd.DataFrame()
        )

        return {"ichimoku": final_ich, "cup": final_cup, "candle": final_candle}

    # ── 정렬 헬퍼 ─────────────────────────────────────────────────────
    @staticmethod
    def _sort_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        try:
            df = df.copy()
            df["_dist"] = df["구름 거리 (%)"].str.replace("%", "").astype(float)
            df["_tf"]   = (df["타임프레임"] == "주봉").astype(int)
            df["_sig"]  = (df["시그널 유형"] == "지지 반등").astype(int)
            df = df.sort_values(["_tf", "_sig", "_dist"])
            df = df.drop(columns=["_dist", "_tf", "_sig"])
        except Exception:
            pass
        return df.reset_index(drop=True)

    @staticmethod
    def _sort_cup(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        try:
            df = df.copy()
            df["_dist"] = df["돌파선까지 (%)"].str.replace("%", "").astype(float)
            df["_tf"]   = (df["타임프레임"] == "주봉").astype(int)
            df = df.sort_values(["_tf", "_dist"])
            df = df.drop(columns=["_dist", "_tf"])
        except Exception:
            pass
        return df.reset_index(drop=True)

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
