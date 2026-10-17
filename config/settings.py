"""
config/settings.py
==================
스캐너 전반에서 참조하는 설정값을 하나의 클래스로 관리합니다.
값을 변경하고 싶을 때 이 파일만 수정하면 됩니다.
"""


class Config:

    # ── 스캔 대상 유니버스 ─────────────────────────────────────────────
    # 선택 가능: "sp500", "sp400"
    # UNIVERSES: list[str] = ["sp500", "sp400"]
    UNIVERSES: list[str] = ["sp500"]

    # ── 스캔 기준 날짜 ────────────────────────────────────────────────
    # None       → 오늘 기준으로 최신 데이터 조회 (평소 운영)
    # "YYYY-MM-DD" → 해당 날짜 기준으로 데이터 조회 (과거 날짜 재현 시)
    # 예) SCAN_END_DATE = "2026-05-13"  → 2026-05-13 종가 기준으로 스캔
    SCAN_END_DATE: str | None = None

    # ── 백테스트 ──────────────────────────────────────────────────────
    BACKTEST_DAYS: int  = 7      # 과거 몇 거래일(봉)까지 소급 검증
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

    # ── 지지 반등 눌림 구간 (봉) ─────────────────────────────────────
    # 눌림 L봉 동안 구름 하단 위 유지 + 그 이전 L봉은 구름 위 → 진짜 눌림목만 인정
    PULLBACK_BARS: int = 5

    # ── 컵앤핸들 ──────────────────────────────────────────────────────
    CUP_LOOKBACK: int = 120

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
