"""
scanner/candle_analyzer.py
==========================
캔들 패턴 탐지를 담당합니다.

지원 패턴
---------
- Morning Doji Star (샛별형 도지)
- Piercing Pattern  (관통형)

공통 추가 조건
-------------
첫 번째 캔들(장대음봉)의 종가가 5일 이동평균선 아래에 있어야 합니다.
→ 하락 추세 중 눌림이 충분히 진행된 시점에서만 반전 시그널로 인정.
"""

import pandas as pd

from config.settings import Config
from scanner.data_fetcher import DataFetcher
from scanner.ichimoku_analyzer import IchimokuAnalyzer


class CandleAnalyzer:

    def __init__(self, cfg: Config = None):
        self.cfg = cfg or Config()

    # ── 패턴 탐지 (내부) ────────────────────────────────────────────────
    def _detect(self, df: pd.DataFrame) -> str | None:
        """
        패턴명 반환, 없으면 None.

        [조건 상세]
        Morning Doji Star:
          ① 전전봉(iloc[-3]): 장대음봉, 종가 < 5일선
          ② 전봉(iloc[-2])  : 갭 하락 도지 (몸통 ≤ 전체 길이 × 20%)
          ③ 당봉(iloc[-1])  : 양봉, 전전봉 몸통 중간 이상까지 상승

        Piercing Pattern:
          ① 전봉(iloc[-2]): 장대음봉, 종가 < 5일선
          ② 당봉(iloc[-1]): 전봉 저가 아래 갭 하락 시작,
                            전봉 몸통 중간 이상 & 전봉 시가 미만 종가
        """
        # 5일선 계산을 위해 최소 15봉 필요
        if len(df) < 15:
            return None

        o = df["Open"]
        h = df["High"]
        l = df["Low"]
        c = df["Close"]

        body     = abs(c - o)
        avg_body = body.rolling(10).mean()
        ma5      = c.rolling(5).mean()

        # Morning Doji Star
        is_morning_doji = (
            (c.iloc[-3] < ma5.iloc[-3])                                       # ★ 5일선 아래
            and (c.iloc[-3] < o.iloc[-3])                                     # 음봉
            and (body.iloc[-3] > avg_body.iloc[-3])                           # 장대음봉
            and (max(o.iloc[-2], c.iloc[-2]) < min(o.iloc[-3], c.iloc[-3]))  # 갭 하락
            and (body.iloc[-2] <= (h.iloc[-2] - l.iloc[-2]) * 0.2)           # 도지
            and (c.iloc[-1] > o.iloc[-1])                                     # 양봉
            and (c.iloc[-1] > (o.iloc[-3] + c.iloc[-3]) / 2)                 # 전전봉 중간 돌파
        )

        # Piercing Pattern
        is_piercing = (
            (c.iloc[-2] < ma5.iloc[-2])                                       # ★ 5일선 아래
            and (c.iloc[-2] < o.iloc[-2])                                     # 음봉
            and (body.iloc[-2] > avg_body.iloc[-2])                           # 장대음봉
            and (o.iloc[-1] < l.iloc[-2])                                     # 당봉 갭 하락 시작
            and (c.iloc[-1] > (o.iloc[-2] + c.iloc[-2]) / 2)                 # 전봉 몸통 중간 이상
            and (c.iloc[-1] < o.iloc[-2])                                     # 전봉 시가 미만
        )

        if is_morning_doji:
            return "샛별형 도지"
        if is_piercing:
            return "관통형"
        return None

    # ── 외부 호출용 분석 ────────────────────────────────────────────────
    def analyze(self, ticker: str, period: str, interval: str) -> dict | None:
        raw = DataFetcher.fetch(ticker, period, interval)
        if raw.empty or len(raw) < 20:
            return None

        pattern_name = self._detect(raw)
        if not pattern_name:
            return None

        return self._build_result(ticker, interval, raw, pattern_name)

    def analyze_at(self, df_full: pd.DataFrame,
                   current_close: float, target_idx: int) -> dict | None:
        """백테스트용: target_idx 시점 기준 패턴 탐지 + 수익률 계산."""
        df = df_full.iloc[:target_idx + 1].copy()
        if len(df) < 20:
            return None

        pattern_name = self._detect(df)
        if not pattern_name:
            return None

        latest    = df.iloc[-1]
        close_val = float(latest["Close"])

        return {
            "시그널 유형": pattern_name,
            "진입가 ($)": round(close_val, 2),
            "시가":        round(float(latest["Open"]), 2),
            "고가":        round(float(latest["High"]), 2),
            "저가":        round(float(latest["Low"]), 2),
            "수익률 (%)":  round((current_close - close_val) / close_val * 100, 2),
        }

    # ── 내부 헬퍼 ───────────────────────────────────────────────────────
    def _build_result(self, ticker: str, interval: str,
                      raw: pd.DataFrame, pattern_name: str) -> dict:
        latest    = raw.iloc[-1]
        close_val = float(latest["Close"])
        high52    = float(raw["High"].iloc[-252:].max())
        low52     = float(raw["Low"].iloc[-252:].min())
        pos52     = round((close_val - low52) / (high52 - low52) * 100, 1) if high52 != low52 else 50

        return {
            "티커":         ticker,
            "타임프레임":    IchimokuAnalyzer._tf_label(interval),
            "시그널 유형":   pattern_name,
            "종가 ($)":     round(close_val, 2),
            "52주 위치 (%)": pos52,
            "시가":          round(float(latest["Open"]), 2),
            "고가":          round(float(latest["High"]), 2),
            "저가":          round(float(latest["Low"]), 2),
        }
