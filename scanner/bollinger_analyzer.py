"""
scanner/bollinger_analyzer.py
=============================
볼린저 밴드 (중심선 = BB_PERIOD 이동평균, ±1σ / ±2σ) 시그널 탐지.

시그널
------
- 상향 돌파: 5이평(BB_FAST_MA)이 +1σ 선을 아래에서 위로 돌파
             (전봉 5이평 ≤ +1σ, 당봉 5이평 > +1σ)
"""

import pandas as pd

from config.settings import Config
from scanner.data_fetcher import DataFetcher
from scanner.ichimoku_analyzer import IchimokuAnalyzer


class BollingerAnalyzer:

    def __init__(self, cfg: Config = None):
        self.cfg = cfg or Config()

    # ── 지표 계산 ───────────────────────────────────────────────────────
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """bb_mid · bb_up1/2 · bb_dn1/2 · ma_fast 컬럼을 추가하여 반환합니다."""
        c   = df["Close"]
        df  = df.copy()
        mid = c.rolling(self.cfg.BB_PERIOD).mean()
        sd  = c.rolling(self.cfg.BB_PERIOD).std(ddof=0)   # 볼린저 표준: 모표준편차
        df["bb_mid"] = mid
        df["bb_up1"], df["bb_up2"] = mid + sd, mid + 2 * sd
        df["bb_dn1"], df["bb_dn2"] = mid - sd, mid - 2 * sd
        df["ma_fast"] = c.rolling(self.cfg.BB_FAST_MA).mean()
        return df

    def _detect(self, df: pd.DataFrame) -> str | None:
        if len(df) < self.cfg.BB_PERIOD + 1:
            return None
        d = self.compute(df)
        ma, up = d["ma_fast"], d["bb_up1"]
        if ma.iloc[-2] <= up.iloc[-2] and ma.iloc[-1] > up.iloc[-1]:   # NaN 이면 False
            return "상향 돌파"
        return None

    # ── 외부 호출용 분석 ────────────────────────────────────────────────
    def analyze(self, ticker: str, period: str, interval: str) -> dict | None:
        raw = DataFetcher.fetch_with_cfg(ticker, period, interval, self.cfg)
        sig = self._detect(raw) if not raw.empty else None
        if not sig:
            return None
        return {
            "티커":       ticker,
            "타임프레임":  IchimokuAnalyzer._tf_label(interval),
            "시그널 유형": sig,
            "종가 ($)":   round(float(raw["Close"].iloc[-1]), 2),
        }

    def analyze_at(self, df_full: pd.DataFrame,
                   current_close: float, target_idx: int) -> dict | None:
        """백테스트용: target_idx 시점 기준 시그널 탐지 + 수익률 계산."""
        df  = df_full.iloc[:target_idx + 1]
        sig = self._detect(df)
        if not sig:
            return None
        close_val = float(df["Close"].iloc[-1])
        return {
            "시그널 유형": sig,
            "진입가 ($)": round(close_val, 2),
            "수익률 (%)": round((current_close - close_val) / close_val * 100, 2),
        }
