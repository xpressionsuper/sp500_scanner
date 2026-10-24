"""
HTML 표 변환 검증: python test_html_table.py  (네트워크 불필요)
빈 값(NaN)이 섞인 표 — 여러 백테스트 결과를 합치면 생김 — 도 깨지지 않아야 함.
pandas 3.1 에서 astype(str) 후 NaN 이 float 로 남아 html.escape 가 실패했던 회귀 방지.
"""

import numpy as np
import pandas as pd

from report.report_exporter import ReportExporter
from scanner.data_fetcher import DataFetcher

DataFetcher._YIELD.update({"AAA": 1.234, "<B>": None})   # 배당률 조회 생략
DataFetcher.NAMES.update({"AAA": "Alpha & Co"})
DataFetcher.SECTORS.update({"AAA": "Financials"})

df = pd.DataFrame({
    "티커":       ["AAA", "<B>"],
    "타임프레임":  ["일봉", np.nan],
    "시그널 유형": ["구름 돌파", "상향 돌파"],
    "시그널 날짜": ["2026-10-20", np.nan],
    "수익률 (%)": [-1.5, np.nan],
})
s = ReportExporter._html_table(df)

assert "nan" not in s.lower()                       # 빈 값은 빈 칸
assert 'class="dn">-1.5' in s                       # 수익률 색상
assert "&lt;B&gt;" in s and "<B>" not in s          # 이스케이프
assert "Alpha &amp; Co" in s and "금융" in s and "1.23%" in s
print("ok", pd.__version__)
