"""
볼린저 상향 돌파 검증: python test_bollinger_signals.py
80봉 동안 99/101 을 오가는 횡보(중심 100, +1σ ≈ 101) 뒤 급등 봉으로 5이평이 +1σ 를 넘는 경우.
"""

import pandas as pd

from config.settings import Config
from scanner.bollinger_analyzer import BollingerAnalyzer

a = BollingerAnalyzer(Config())
flat = [99.0, 101.0] * 50


def sig(closes):
    return a._detect(pd.DataFrame({"Close": closes}))


assert sig(flat) is None                       # 횡보: 5이평 ≈ 중심선 → 없음
assert sig(flat + [120]) == "상향 돌파"         # 5이평이 이번 봉에 +1σ 돌파
assert sig(flat + [120, 125]) is None          # 이미 전봉에 돌파 → 재발생 없음
assert sig(flat[:50] + [120]) is None          # 80봉 미만 → 없음

d = a.compute(pd.DataFrame({"Close": flat}))
assert abs(d["bb_mid"].iloc[-1] - 100) < 1e-9 and abs(d["bb_up1"].iloc[-1] - 101) < 1e-9
assert abs(d["bb_up2"].iloc[-1] - 102) < 1e-9 and abs(d["bb_dn2"].iloc[-1] - 98) < 1e-9

print("ok")
