"""
scanner/data_fetcher.py
=======================
스캔 대상 티커 목록 수집 및 yfinance 히스토리 데이터 로드를 담당합니다.

지원 유니버스
------------
- S&P 500  (대형주, ~500개)  : UNIVERSES = ["sp500"]
- S&P 400  (중형주, ~400개)  : UNIVERSES = ["sp400"]
- 통합       (~900개)         : UNIVERSES = ["sp500", "sp400"]
"""

import io
import requests
import pandas as pd
import yfinance as yf

from config.settings import Config


# Wikipedia 티커 소스 정의
_WIKI_SOURCES: dict[str, dict] = {
    "sp500": {
        "url":    "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "col":    "Symbol",
        "label":  "S&P 500",
    },
    "sp400": {
        "url":    "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
        "col":    "Ticker symbol",
        "label":  "S&P 400 MidCap",
    },
}

# Wikipedia 파싱 실패 시 사용할 대체 티커
_FALLBACK_TICKERS: list[str] = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
]


class DataFetcher:
    """
    티커 목록 수집 및 yfinance 데이터 로드를 담당하는 클래스입니다.

    모든 메서드는 staticmethod로 구현되어 있어
    인스턴스 생성 없이 DataFetcher.method() 형태로 호출 가능합니다.
    """

    # ── 유니버스별 티커 수집 ────────────────────────────────────────────
    @staticmethod
    def _fetch_from_wiki(universe_key: str) -> list[str]:
        """
        Wikipedia에서 특정 지수의 티커 목록을 수집합니다.
        실패 시 빈 리스트 반환.
        """
        src = _WIKI_SOURCES.get(universe_key)
        if not src:
            print(f"  ⚠️  알 수 없는 유니버스: {universe_key}")
            return []

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp    = requests.get(src["url"], headers=headers, timeout=15)
            tables  = pd.read_html(io.StringIO(resp.text))

            # 컬럼명이 일치하는 테이블 탐색
            for table in tables:
                if src["col"] in table.columns:
                    tickers = (
                        table[src["col"]]
                        .dropna()
                        .astype(str)
                        .str.replace(".", "-", regex=False)
                        .tolist()
                    )
                    print(f"  ✅ {src['label']}: {len(tickers)}개 수집 완료")
                    return tickers

            print(f"  ⚠️  {src['label']}: 컬럼 '{src['col']}' 없음")
            return []

        except Exception as e:
            print(f"  ❌ {src['label']} 수집 실패: {e}")
            return []

    @staticmethod
    def get_tickers(cfg: Config = None) -> list[str]:
        """
        Config.UNIVERSES 설정에 따라 티커를 수집하고
        중복 제거 후 정렬된 통합 리스트를 반환합니다.

        Parameters
        ----------
        cfg : Config (None이면 기본값 사용)

        Returns
        -------
        list[str] : 중복 없는 티커 목록
        """
        cfg       = cfg or Config()
        universes = cfg.UNIVERSES
        all_tickers: list[str] = []

        print(f"📋 유니버스 수집 대상: {universes}")
        for key in universes:
            tickers = DataFetcher._fetch_from_wiki(key)
            all_tickers.extend(tickers)

        # 중복 제거 (순서 보존)
        seen    = set()
        unique  = []
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
    def fetch(ticker: str, period: str, interval: str) -> pd.DataFrame:
        """
        단일 티커의 OHLCV 데이터를 yfinance에서 로드합니다.

        Parameters
        ----------
        ticker   : 티커 심볼 (예: "AAPL")
        period   : 수집 기간 (예: "2y", "3y", "5y")
        interval : 봉 단위 (예: "1d", "1wk", "1mo")

        Returns
        -------
        pd.DataFrame : OHLCV DataFrame, 실패 시 빈 DataFrame
        """
        try:
            raw = yf.Ticker(ticker).history(
                period=period,
                interval=interval,
                auto_adjust=True,
            )
            # timezone 제거 (이후 인덱스 비교 안정화)
            if raw.index.tz is not None:
                raw.index = raw.index.tz_localize(None)
            return raw
        except Exception:
            return pd.DataFrame()
