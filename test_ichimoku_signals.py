"""
일목 시그널 분류 검증: python test_ichimoku_signals.py
구름은 상단 100 / 하단 90 고정, 마지막 봉(i=-1)의 분류를 확인합니다.
"""

import pandas as pd

from config.settings import Config
from scanner.ichimoku_analyzer import IchimokuAnalyzer


def last_signal(closes, bullish=True, lows=None):
    n  = len(closes)
    df = pd.DataFrame({
        "Close": closes,
        "Low": lows or [c - 1 for c in closes],
        "cloud_top": [100.0] * n, "cloud_bottom": [90.0] * n,
        "cloud_bullish": [bullish] * n,
        "tenkan": list(range(n)),          # 전환선 상승
    })
    r = IchimokuAnalyzer(Config()).detect_signals(df).iloc[-1]
    return "돌파" if r.signal_breakout else "반등" if r.signal_pullback else None


# 녹색 구름 아래에 있다가 돌파 (MRSH 사례) → 구름 돌파
assert last_signal([85] * 12 + [103]) == "돌파"
# 구름 안에 있다가 돌파 (BLK 사례) → 구름 돌파
assert last_signal([95] * 12 + [103]) == "돌파"
# 적색 구름 돌파 → 구름 돌파 (기존과 동일)
assert last_signal([85] * 12 + [103], bullish=False) == "돌파"
# 구름 위 → 상단까지 눌림(하단 위 유지) → 반등 → 지지 반등
assert last_signal([110] * 7 + [104, 102, 100, 99, 100, 103]) == "반등"
# 눌림 중 구름 하단 아래로 빠졌다가 회복 → 지지 반등 아님, 돌파로 분류
assert last_signal([110] * 7 + [104, 95, 88, 92, 99, 103]) == "돌파"
# 구름 위에서 계속 상승 → 시그널 없음
assert last_signal([110] * 13) is None

print("ok")
