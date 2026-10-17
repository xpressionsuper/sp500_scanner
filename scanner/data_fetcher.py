"""
scanner/data_fetcher.py
=======================
스캔 대상 티커 목록 수집 및 yfinance 히스토리 데이터 로드를 담당합니다.

SCAN_END_DATE 동작
------------------
Config.SCAN_END_DATE 가 None 이면 오늘까지의 최신 데이터를 반환합니다.
날짜가 지정되면 해당 날짜까지의 데이터만 반환하여 과거 시점을 재현합니다.

yfinance end 파라미터는 exclusive(해당 날짜 미포함)이므로
지정 날짜의 다음날을 end 로 설정합니다.
예) SCAN_END_DATE = "2026-05-13"  →  end = "2026-05-14"
"""

import io
import datetime
import requests
import pandas as pd
import yfinance as yf

from config.settings import Config


_WIKI_SOURCES: dict[str, dict] = {
    "sp500": {
        "url":   "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "col":   "Symbol",
        "label": "S&P 500",
    },
    "sp400": {
        "url":   "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
        "col":   "Ticker symbol",
        "label": "S&P 400 MidCap",
    },
}

_FALLBACK_TICKERS: list[str] = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]


class DataFetcher:

    # 티커 → 회사명 (get_tickers 가 위키 표에서 채움, 리포트 표시용)
    NAMES: dict[str, str] = {}
    SECTORS: dict[str, str] = {}   # 티커 → GICS 섹터 (영문, 위키 표)
    # (티커, 기간, 봉, 기준일) → OHLCV — 한 번 실행 동안 메모리에만 유지
    _CACHE: dict[tuple, pd.DataFrame] = {}
    _YIELD: dict[str, float | None] = {}

    @staticmethod
    def dividend_yield(ticker: str) -> float | None:
        """배당률 % — yfinance info. 실패 시 None, 성공만 캐시."""
        if ticker in DataFetcher._YIELD:
            return DataFetcher._YIELD[ticker]
        try:
            info = yf.Ticker(ticker).info
        except Exception:
            return None
        # dividendYield 는 이미 % 단위 (예: 0.31 → 0.31%)
        DataFetcher._YIELD[ticker] = info.get("dividendYield")
        return DataFetcher._YIELD[ticker]

    # ── 유니버스별 티커 수집 ────────────────────────────────────────────
    @staticmethod
    def _fetch_from_wiki(universe_key: str) -> list[str]:
        src = _WIKI_SOURCES.get(universe_key)
        if not src:
            print(f"  ⚠️  알 수 없는 유니버스: {universe_key}")
            return []
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp    = requests.get(src["url"], headers=headers, timeout=15)
            tables  = pd.read_html(io.StringIO(resp.text))
            for table in tables:
                if src["col"] in table.columns:
                    tickers = (
                        table[src["col"]]
                        .dropna()
                        .astype(str)
                        .str.replace(".", "-", regex=False)
                        .tolist()
                    )
                    name_col = next((c for c in ("Security", "Company") if c in table.columns), None)
                    syms = table[src["col"]].astype(str).str.replace(".", "-", regex=False)
                    for col, store in ((name_col, DataFetcher.NAMES), ("GICS Sector", DataFetcher.SECTORS)):
                        if col in table.columns:
                            store.update((s, str(v)) for s, v in zip(syms, table[col]) if pd.notna(v))
                    print(f"  ✅ {src['label']}: {len(tickers)}개 수집 완료")
                    return tickers
            print(f"  ⚠️  {src['label']}: 컬럼 '{src['col']}' 없음")
            return []
        except Exception as e:
            print(f"  ❌ {src['label']} 수집 실패: {e}")
            return []

    @staticmethod
    def get_tickers(cfg: Config = None) -> list[str]:
        cfg       = cfg or Config()
        all_tickers: list[str] = []
        print(f"📋 유니버스 수집 대상: {cfg.UNIVERSES}")
        for key in cfg.UNIVERSES:
            all_tickers.extend(DataFetcher._fetch_from_wiki(key))

        seen, unique = set(), []
        for t in all_tickers:
            if t not in seen:
                seen.add(t)
                unique.append(t)

        if not unique:
            print("  ⚠️  수집 실패 — fallback 티커 사용")
            return _FALLBACK_TICKERS

        print(f"  → 통합 티커: {len(unique)}개 (중복 제거 후)\n")
        return unique

    # ── yfinance 데이터 로드 ────────────────────────────────────────────
    @staticmethod
    def fetch(ticker: str, period: str, interval: str,
              end_date: str | None = None) -> pd.DataFrame:
        """
        단일 티커의 OHLCV 데이터를 로드합니다.

        Parameters
        ----------
        ticker    : 티커 심볼
        period    : 수집 기간 (예: "2y")
        interval  : 봉 단위 (예: "1d", "1wk")
        end_date  : 기준 날짜 "YYYY-MM-DD" — None 이면 오늘까지
                    지정 시 해당 날짜가 마지막 봉이 되도록 조회

        Returns
        -------
        pd.DataFrame : OHLCV, 실패 시 빈 DataFrame

        같은 (티커, 기간, 봉, 기준일) 은 한 번만 받아 재사용합니다 — 일목·컵핸들·캔들·
        백테스트·차트가 같은 데이터를 각자 요청해 Yahoo 요청 한도(429)에 걸리던 문제 방지.
        실패(빈 결과)는 캐시하지 않습니다.
        """
        key = (ticker, period, interval, end_date)
        if key in DataFetcher._CACHE:
            return DataFetcher._CACHE[key].copy()
        try:
            kwargs = dict(period=period, interval=interval, auto_adjust=True)

            if end_date:
                # yfinance end 는 exclusive → 지정 날짜 +1일 설정
                end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
                end_dt += datetime.timedelta(days=1)
                kwargs["end"] = end_dt.strftime("%Y-%m-%d")
                # period + end 동시 사용 시 start 가 필요
                # period 대신 start 로 변환
                period_map = {"1y": 365, "2y": 730, "3y": 1095, "5y": 1825}
                days = period_map.get(period, 730)
                start_dt = end_dt - datetime.timedelta(days=days)
                kwargs["start"]  = start_dt.strftime("%Y-%m-%d")
                kwargs.pop("period")

            raw = yf.Ticker(ticker).history(**kwargs)

            if raw.index.tz is not None:
                raw.index = raw.index.tz_localize(None)
            if not raw.empty:
                DataFetcher._CACHE[key] = raw
            return raw.copy()

        except Exception:
            return pd.DataFrame()

    # ── end_date 를 Config 에서 읽어 fetch 하는 편의 메서드 ─────────────
    @staticmethod
    def fetch_with_cfg(ticker: str, period: str, interval: str,
                       cfg: Config = None) -> pd.DataFrame:
        """Config.SCAN_END_DATE 를 자동으로 반영하여 데이터를 로드합니다."""
        cfg = cfg or Config()
        return DataFetcher.fetch(ticker, period, interval,
                                 end_date=cfg.SCAN_END_DATE)
