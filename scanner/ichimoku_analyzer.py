"""
scanner/ichimoku_analyzer.py
============================
일목균형표(Ichimoku Kinko Hyo) 지표 계산 및 매수 시그널 탐지를 담당합니다.

시그널 종류
-----------
- 구름 돌파 : 적색 구름을 위로 돌파
- 지지 반등 : 녹색 구름 상단에서 눌림 후 반등
"""

import pandas as pd

from config.settings import Config
from scanner.data_fetcher import DataFetcher


class IchimokuAnalyzer:

    def __init__(self, cfg: Config = None):
        self.cfg = cfg or Config()

    # ── 지표 계산 ───────────────────────────────────────────────────────
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """전환선·기준선·선행스팬A/B·구름 컬럼을 추가하여 반환합니다."""
        c    = self.cfg
        high = df["High"]
        low  = df["Low"]
        df   = df.copy()

        df["tenkan"] = (
            high.rolling(c.TENKAN).max() + low.rolling(c.TENKAN).min()
        ) / 2
        df["kijun"] = (
            high.rolling(c.KIJUN).max() + low.rolling(c.KIJUN).min()
        ) / 2

        sa_raw = (df["tenkan"] + df["kijun"]) / 2
        sb_raw = (
            high.rolling(c.SENKOU_B).max() + low.rolling(c.SENKOU_B).min()
        ) / 2

        df["senkou_a"]      = sa_raw.shift(c.DISPLACEMENT)
        df["senkou_b"]      = sb_raw.shift(c.DISPLACEMENT)
        df["cloud_top"]     = df[["senkou_a", "senkou_b"]].max(axis=1)
        df["cloud_bottom"]  = df[["senkou_a", "senkou_b"]].min(axis=1)
        df["cloud_bullish"] = df["senkou_a"] > df["senkou_b"]
        return df

    # ── 시그널 탐지 ─────────────────────────────────────────────────────
    def detect_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """signal_breakout / signal_pullback 컬럼을 추가하여 반환합니다."""
        df     = df.copy()
        close  = df["Close"]
        low    = df["Low"]
        ct     = df["cloud_top"]
        cb     = df["cloud_bottom"]
        bull   = df["cloud_bullish"]
        tenkan = df["tenkan"]
        buf    = self.cfg.BREAKOUT_BUFFER
        L      = self.cfg.PULLBACK_BARS

        s1 = pd.Series(False, index=df.index)
        s2 = pd.Series(False, index=df.index)

        for i in range(2 * L, len(df)):
            if pd.isna(ct.iloc[i]):
                continue

            # 지지 반등: 구름 위에 있던 주가가 (녹색) 구름 상단까지 눌렸다가 반등
            #   - 눌림 전 L봉(i-2L ~ i-L)은 종가가 모두 구름 위
            #   - 눌림 L봉(i-L ~ i) 동안 종가가 구름 하단 아래로 빠지지 않음
            if (bull.iloc[i]
                    and close.iloc[i] > ct.iloc[i] * buf
                    and close.iloc[i - 1] <= ct.iloc[i - 1] * 1.01
                    and (low.iloc[i - L:i] <= ct.iloc[i - L:i]).any()
                    and (close.iloc[i - 2 * L:i - L] > ct.iloc[i - 2 * L:i - L]).all()
                    and (close.iloc[i - L:i] >= cb.iloc[i - L:i]).all()
                    and tenkan.iloc[i] >= tenkan.iloc[i - 1]):
                s2.iloc[i] = True

            # 구름 돌파: 구름 상단 아래(안/밑)에서 상단을 상향 돌파 — 구름 색 무관
            #   지지 반등으로 잡힌 봉은 제외 (두 시그널 배타)
            elif (close.iloc[i - 1] <= ct.iloc[i - 1]
                    and close.iloc[i] > ct.iloc[i] * buf):
                s1.iloc[i] = True

        df["signal_breakout"] = s1
        df["signal_pullback"] = s2
        return df

    # ── 외부 호출용 분석 ────────────────────────────────────────────────
    def analyze(self, ticker: str, period: str, interval: str) -> dict | None:
        """
        단일 티커 분석 진입점.
        시그널 없거나 필터 탈락 시 None 반환.
        """
        raw = DataFetcher.fetch_with_cfg(ticker, period, interval, self.cfg)
        if raw.empty or len(raw) < 100:
            return None

        df     = self.detect_signals(self.compute(raw))
        latest = df.iloc[-1]

        if not (latest["signal_breakout"] or latest["signal_pullback"]):
            return None

        return self._build_result(ticker, interval, df, raw)

    def analyze_at(self, df_full: pd.DataFrame,
                   current_close: float, target_idx: int) -> dict | None:
        """
        백테스트용: df_full 의 target_idx 시점까지 잘라 시그널 체크.
        수익률(현재가 기준) 포함한 dict 반환.
        """
        df = df_full.iloc[:target_idx + 1].copy()
        if len(df) < 100:
            return None

        df     = self.detect_signals(self.compute(df))
        latest = df.iloc[-1]

        if not (latest["signal_breakout"] or latest["signal_pullback"]):
            return None

        close_val   = float(latest["Close"])
        ct_val      = float(latest["cloud_top"])
        is_breakout = bool(latest["signal_breakout"])
        is_pullback = bool(latest["signal_pullback"])

        if pd.isna(ct_val):
            return None

        dist_pct = (close_val - ct_val) / ct_val * 100
        if dist_pct > 10.0:
            return None

        kijun_now   = float(df["kijun"].iloc[-1])
        kijun_prev  = float(df["kijun"].iloc[-6]) if len(df) > 6 else kijun_now
        kijun_slope = (kijun_now - kijun_prev) / kijun_prev * 100 if kijun_prev else 0
        if is_pullback and kijun_slope < 0:
            return None

        tenkan_above = float(latest["tenkan"]) > float(latest["kijun"])
        if is_pullback and not tenkan_above:
            return None

        return {
            "시그널 유형":  "구름 돌파" if is_breakout else "지지 반등",
            "진입가 ($)":  round(close_val, 2),
            "구름 거리(%)": f"{round(dist_pct, 2)}%",
            "구름 색":      "상승(녹)" if latest["cloud_bullish"] else "하락(적)",
            "전환>기준":    "O" if tenkan_above else "X",
            "수익률 (%)":   round((current_close - close_val) / close_val * 100, 2),
        }

    # ── 내부 헬퍼 ───────────────────────────────────────────────────────
    def _build_result(self, ticker: str, interval: str,
                      df: pd.DataFrame, raw: pd.DataFrame) -> dict | None:
        """필터 적용 후 결과 dict를 생성합니다."""
        latest      = df.iloc[-1]
        close_val   = float(latest["Close"])
        ct_val      = float(latest["cloud_top"])
        is_breakout = bool(latest["signal_breakout"])
        is_pullback = bool(latest["signal_pullback"])
        dist_pct    = (close_val - ct_val) / ct_val * 100

        # 필터 1: 구름 거리 상한 10%
        if dist_pct > 10.0:
            return None

        # 필터 2: 기준선 기울기 (지지 반등 전용)
        kijun_now   = float(df["kijun"].iloc[-1])
        kijun_prev  = float(df["kijun"].iloc[-6]) if len(df) > 6 else kijun_now
        kijun_slope = (kijun_now - kijun_prev) / kijun_prev * 100 if kijun_prev else 0
        if is_pullback and kijun_slope < 0:
            return None

        # 필터 3: 52주 위치 (지지 반등 전용)
        high52 = float(raw["High"].iloc[-252:].max())
        low52  = float(raw["Low"].iloc[-252:].min())
        pos52  = round((close_val - low52) / (high52 - low52) * 100, 1) if high52 != low52 else 50
        if is_pullback and pos52 < 20:
            return None

        # 필터 4: 전환 > 기준 (지지 반등 전용)
        tenkan_above = float(latest["tenkan"]) > float(latest["kijun"])
        if is_pullback and not tenkan_above:
            return None

        return {
            "티커":             ticker,
            "타임프레임":        self._tf_label(interval),
            "시그널 유형":       "구름 돌파" if is_breakout else "지지 반등",
            "종가 ($)":         round(close_val, 2),
            "구름 거리 (%)":     f"{round(dist_pct, 2)}%",
            "52주 위치 (%)":     pos52,
            "기준선 기울기 (%)":  round(kijun_slope, 3),
            "구름 색":           "상승(녹)" if latest["cloud_bullish"] else "하락(적)",
            "전환>기준":         "O" if tenkan_above else "X",
        }

    @staticmethod
    def _tf_label(interval: str) -> str:
        return {"1d": "일봉", "1wk": "주봉", "1mo": "월봉"}.get(interval, interval)
