"""
config/settings.py
==================
스캐너 전반에서 참조하는 설정값을 하나의 클래스로 관리합니다.
값을 변경하고 싶을 때 이 파일만 수정하면 됩니다.
"""


class Config:

    # ── 스캔 대상 유니버스 ─────────────────────────────────────────────
    # 포함할 지수 목록 (순서 무관)
    # 선택 가능: "sp500", "sp400"
    # - sp500 : S&P 500  (대형주 ~500개)
    # - sp400 : S&P 400  (중형주 ~400개)
    UNIVERSES: list[str] = ["sp500", "sp400"]

    # ── 백테스트 ──────────────────────────────────────────────────────
    BACKTEST_DAYS: int  = 140       # 과거 몇 거래일(봉)까지 소급 검증
    RUN_BACKTEST:  bool = True     # False 시 백테스트 전체 건너뜀

    # ── 병렬 처리 ─────────────────────────────────────────────────────
    MAX_WORKERS: int = 15

    # ── 일목균형표 파라미터 ───────────────────────────────────────────
    TENKAN:       int = 9
    KIJUN:        int = 26
    SENKOU_B:     int = 52
    DISPLACEMENT: int = 26

    # ── 구름 돌파 허용 버퍼 ──────────────────────────────────────────
    BREAKOUT_BUFFER: float = 1.005

    # ── 컵앤핸들 ──────────────────────────────────────────────────────
    CUP_LOOKBACK: int = 120        # 컵앤핸들 분석 lookback 봉 수

    # ── 타임프레임별 데이터 수집 기간 ────────────────────────────────
    PERIOD_DAILY:   str = "2y"
    PERIOD_WEEKLY:  str = "3y"
    PERIOD_MONTHLY: str = "5y"

    # ── 색상 팔레트 (xlsx / 이미지 공용) ─────────────────────────────
    C_TITLE_BG:   str = "16213E"
    C_HEADER_BG:  str = "1A1A2E"
    C_HEADER_FG:  str = "FFFFFF"
    C_DAILY_HDR:  str = "1B4F72"
    C_WEEKLY_HDR: str = "1A5E20"
    C_CUP_HDR:    str = "6E2F8A"
    C_CANDLE_HDR: str = "8B4513"
    C_GREEN:      str = "00B050"
    C_RED:        str = "FF0000"
    C_GOLD:       str = "FFC000"
    C_BO:         str = "D5F5E3"
    C_PB:         str = "FEF9E7"
