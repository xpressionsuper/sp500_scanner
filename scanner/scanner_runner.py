"""
scanner/scanner_runner.py
=========================
IchimokuAnalyzer / CupHandleAnalyzer / CandleAnalyzer 의
병렬 스캔 실행을 총괄합니다.

주봉 스캔 정책
--------------
주봉은 해당 주의 마지막 거래일(보통 금요일)에 봉이 완성됩니다.
미완성 주봉 기준으로 시그널을 탐지하면 오신호가 발생할 수 있으므로
주봉 스캔은 오늘이 그 주의 마지막 거래일일 때만 실행합니다.
"""

import sys
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from config.settings import Config
from scanner.ichimoku_analyzer import IchimokuAnalyzer
from scanner.cup_handle_analyzer import CupHandleAnalyzer
from scanner.candle_analyzer import CandleAnalyzer
from scanner.bollinger_analyzer import BollingerAnalyzer


class ScannerRunner:
    """
    3개 분석기(일목·컵핸들·캔들)의 병렬 스캔 실행을 총괄합니다.
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
                 cfg: Config = None,
                 bollinger: BollingerAnalyzer = None):
        self.ich    = ichimoku
        self.cup    = cup
        self.candle = candle
        self.cfg    = cfg or Config()
        self.bb     = bollinger or BollingerAnalyzer(self.cfg)

    # ── 주봉 완성일 여부 판단 ───────────────────────────────────────────
    @staticmethod
    def _is_last_trading_day_of_week() -> bool:
        """
        오늘이 이번 주의 마지막 거래일(미국 증시 기준)인지 확인합니다.

        판단 로직
        ---------
        1. 오늘이 금요일(weekday=4)이면 True
        2. 오늘이 목요일이고 내일(금요일)이 미국 공휴일이면 True
           → 간단 구현: 금요일 기준으로만 체크 (공휴일 예외는 드묾)
        3. 월~목요일이면 False → 주봉 스캔 건너뜀
        """
        today = datetime.date.today()
        weekday = today.weekday()   # 월=0, 화=1, 수=2, 목=3, 금=4, 토=5, 일=6

        # 금요일: 주봉 완성일
        if weekday == 4:
            print("  📅 오늘은 금요일 — 주봉 스캔 실행")
            return True

        # 목요일: 다음날(금요일) 미국 주요 공휴일 여부 간단 체크
        if weekday == 3:
            tomorrow = today + datetime.timedelta(days=1)
            # 미국 주요 고정 공휴일 (월/일 기준)
            us_fixed_holidays = {
                (1, 1),   # 신정
                (7, 4),   # 독립기념일
                (12, 25), # 크리스마스
            }
            if (tomorrow.month, tomorrow.day) in us_fixed_holidays:
                print(f"  📅 내일({tomorrow}) 미국 공휴일 — 오늘 목요일에 주봉 스캔 실행")
                return True

        print(f"  📅 오늘은 {['월','화','수','목','금','토','일'][weekday]}요일 — 주봉은 금요일에만 스캔")
        return False

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

        주봉 스캔 정책
        --------------
        주봉이 요청됐더라도 오늘이 주봉 완성일(금요일)이 아니면
        주봉 스캔을 건너뜁니다.

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
        bb_frames     = []

        # 주봉 완성일 여부 사전 판단 (1회만)
        is_weekly_day = self._is_last_trading_day_of_week()

        for tf_name in timeframes:
            interval, period = self.TIMEFRAMES[tf_name]

            # ── 주봉: 금요일(완성일)에만 실행 ──────────────────────────
            if tf_name == "주봉" and not is_weekly_day:
                print(f"  ⏭  주봉 스캔 건너뜀 (오늘은 주봉 완성일 아님)\n")
                continue

            # ── 월봉: 월말 마지막 거래일에만 실행 ──────────────────────
            if tf_name == "월봉" and not self._is_last_trading_day_of_month():
                print(f"  ⏭  월봉 스캔 건너뜀 (오늘은 월봉 완성일 아님)\n")
                continue

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

            print(f"🔍 [볼린저 밴드] {tf_name} 스캔 ({len(tickers)}개 종목)\n")
            df = self._scan_one(tickers, self.bb.analyze,
                                period, interval, f"볼린저 {tf_name}")
            if not df.empty:
                bb_frames.append(df)

        final_ich    = self._sort_ichimoku(
            pd.concat(ich_frames,    ignore_index=True) if ich_frames    else pd.DataFrame()
        )
        final_cup    = self._sort_cup(
            pd.concat(cup_frames,    ignore_index=True) if cup_frames    else pd.DataFrame()
        )
        final_candle = (
            pd.concat(candle_frames, ignore_index=True) if candle_frames else pd.DataFrame()
        )

        final_bb = pd.concat(bb_frames, ignore_index=True) if bb_frames else pd.DataFrame()

        return {"ichimoku": final_ich, "cup": final_cup, "candle": final_candle, "bollinger": final_bb}

    # ── 월봉 완성일 여부 판단 ───────────────────────────────────────────
    @staticmethod
    def _is_last_trading_day_of_month() -> bool:
        """이번 달 마지막 거래일인지 확인합니다."""
        today    = datetime.date.today()
        # 다음 거래일이 다음 달이면 오늘이 이번 달 마지막 거래일
        next_day = today + datetime.timedelta(days=1)
        while next_day.weekday() >= 5:   # 토/일 건너뜀
            next_day += datetime.timedelta(days=1)
        return next_day.month != today.month

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
