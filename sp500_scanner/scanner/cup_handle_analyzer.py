"""
scanner/cup_handle_analyzer.py
===============================
윌리엄 오닐의 컵앤핸들(Cup & Handle) 패턴 탐지를 담당합니다.
"""

import pandas as pd

from config.settings import Config
from scanner.data_fetcher import DataFetcher
from scanner.ichimoku_analyzer import IchimokuAnalyzer


class CupHandleAnalyzer:

    def __init__(self, cfg: Config = None):
        self.cfg = cfg or Config()

    # ── 패턴 탐지 (내부) ────────────────────────────────────────────────
    def _detect(self, df: pd.DataFrame) -> dict | None:
        """
        컵앤핸들 패턴 탐지.
        발견 시 세부 정보 dict 반환, 미발견 시 None 반환.
        """
        lookback = self.cfg.CUP_LOOKBACK
        if len(df) < lookback:
            return None

        data   = df.iloc[-lookback:].copy()
        highs  = data["High"]
        lows   = data["Low"]
        closes = data["Close"]

        try:
            # 1. 전기 상승 추세 확인 (최소 20%)
            prior_low  = lows.iloc[:60].min()
            prior_high = highs.iloc[:60].max()
            if (prior_high - prior_low) / prior_low < 0.20:
                return None

            # 2. 컵 왼쪽 고점
            left_high_idx = highs.iloc[:-20].idxmax()
            left_high_val = highs.loc[left_high_idx]

            # 3. 컵 바닥 & 깊이 (12~35%)
            cup_area = data.loc[left_high_idx:]
            if len(cup_area) < 20:
                return None
            cup_bottom_val = cup_area["Low"].min()
            depth          = (left_high_val - cup_bottom_val) / left_high_val
            if not (0.12 <= depth <= 0.35):
                return None

            # 4. 핸들 검증 (컵 깊이의 50% 이내, 상단 1/2 위 유지)
            handle_area        = data.iloc[-15:]
            handle_high        = handle_area["High"].max()
            handle_low         = handle_area["Low"].min()
            handle_retracement = (handle_high - handle_low) / handle_high
            if (handle_retracement > depth * 0.5
                    or handle_low < cup_bottom_val
                    + (left_high_val - cup_bottom_val) * 0.5):
                return None

            # 5. 돌파 임박: 현재가 ≥ 핸들 고점 × 98%
            current_price = closes.iloc[-1]
            if current_price >= handle_high * 0.98:
                return {
                    "cup_left":   left_high_val,
                    "cup_bottom": cup_bottom_val,
                    "right_high": handle_high,
                    "depth":      depth,
                    "cur_price":  current_price,
                }

        except Exception:
            pass

        return None

    # ── 외부 호출용 분석 ────────────────────────────────────────────────
    def analyze(self, ticker: str, period: str, interval: str) -> dict | None:
        raw = DataFetcher.fetch(ticker, period, interval)
        if raw.empty or len(raw) < 120:
            return None

        result = self._detect(raw)
        if not result:
            return None

        return self._build_result(ticker, interval, raw, result)

    def analyze_at(self, df_full: pd.DataFrame,
                   current_close: float, target_idx: int) -> dict | None:
        """백테스트용: target_idx 시점 기준 패턴 탐지 + 수익률 계산."""
        df = df_full.iloc[:target_idx + 1].copy()
        if len(df) < 120:
            return None

        result = self._detect(df)
        if not result:
            return None

        close_val  = float(df.iloc[-1]["Close"])
        depth_pct  = round(result["depth"] * 100, 1)
        right_high = result["right_high"]
        dist_to    = round((right_high - close_val) / right_high * 100, 2)

        return {
            "시그널 유형":   "컵앤핸들",
            "진입가 ($)":   round(close_val, 2),
            "돌파선까지(%)": f"{dist_to}%",
            "컵 깊이(%)":   f"{depth_pct}%",
            "수익률 (%)":   round((current_close - close_val) / close_val * 100, 2),
        }

    # ── 내부 헬퍼 ───────────────────────────────────────────────────────
    def _build_result(self, ticker: str, interval: str,
                      raw: pd.DataFrame, result: dict) -> dict:
        close_val  = float(raw.iloc[-1]["Close"])
        high52     = float(raw["High"].iloc[-252:].max())
        low52      = float(raw["Low"].iloc[-252:].min())
        pos52      = round((close_val - low52) / (high52 - low52) * 100, 1) if high52 != low52 else 50
        depth_pct  = round(result["depth"] * 100, 1)
        right_high = result["right_high"]
        dist_to    = round((right_high - close_val) / right_high * 100, 2)

        return {
            "티커":          ticker,
            "타임프레임":     IchimokuAnalyzer._tf_label(interval),
            "시그널 유형":    "컵앤핸들",
            "종가 ($)":      round(close_val, 2),
            "돌파선까지 (%)": f"{dist_to}%",
            "컵 깊이 (%)":   f"{depth_pct}%",
            "52주 위치 (%)":  pos52,
            "컵 왼쪽 고점":   round(result["cup_left"], 2),
            "컵 바닥":        round(result["cup_bottom"], 2),
            "돌파 기준선":    round(right_high, 2),
        }
