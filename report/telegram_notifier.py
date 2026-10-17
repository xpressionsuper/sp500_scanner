"""
report/telegram_notifier.py
============================
스캔 결과 이미지와 요약 텍스트를 Telegram으로 전송합니다.

사용 방법
---------
환경변수 2개를 GitHub Secrets 에 등록하면 자동으로 동작합니다.
  - TELEGRAM_BOT_TOKEN  : BotFather 에서 발급받은 토큰
  - TELEGRAM_CHAT_ID    : 메시지를 받을 채팅 ID (개인 또는 그룹)

Telegram Bot 만들기
--------------------
1. Telegram 앱에서 @BotFather 검색
2. /newbot 명령 입력 → 이름 설정 → 토큰 발급
3. 발급받은 토큰을 TELEGRAM_BOT_TOKEN 에 저장
4. 본인 채팅 ID 확인: @userinfobot 에 /start 전송
5. 채팅 ID를 TELEGRAM_CHAT_ID 에 저장
"""

import os
import time
import requests
from datetime import datetime
from pathlib import Path


class TelegramNotifier:
    """Telegram Bot API를 통해 텍스트·이미지를 전송합니다."""

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self):
        self.token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)

        if not self.enabled:
            print("  ℹ️  Telegram 환경변수 없음 — 전송 건너뜀")

    # ── 연결 확인 ─────────────────────────────────────────────────────
    def check_connection(self) -> bool:
        """Bot 토큰 유효성 확인."""
        if not self.enabled:
            return False
        try:
            url  = self.BASE_URL.format(token=self.token, method="getMe")
            resp = requests.get(url, timeout=10)
            ok   = resp.json().get("ok", False)
            if ok:
                name = resp.json()["result"]["username"]
                print(f"  ✅ Telegram 연결 확인: @{name}")
            return ok
        except Exception as e:
            print(f"  ❌ Telegram 연결 실패: {e}")
            return False

    # ── 텍스트 전송 ───────────────────────────────────────────────────
    def send_text(self, message: str) -> bool:
        """텍스트 메시지를 전송합니다 (Markdown 지원)."""
        if not self.enabled:
            return False
        try:
            url  = self.BASE_URL.format(token=self.token, method="sendMessage")
            data = {
                "chat_id":    self.chat_id,
                "text":       message,
                "parse_mode": "Markdown",
            }
            resp = requests.post(url, data=data, timeout=15)
            return resp.json().get("ok", False)
        except Exception as e:
            print(f"  ❌ 텍스트 전송 실패: {e}")
            return False

    # ── 이미지 전송 ───────────────────────────────────────────────────
    def send_image(self, image_path: str, caption: str = "") -> bool:
        """이미지 파일을 전송합니다."""
        if not self.enabled:
            return False
        path = Path(image_path)
        if not path.exists():
            print(f"  ⚠️  파일 없음: {image_path}")
            return False
        try:
            url   = self.BASE_URL.format(token=self.token, method="sendPhoto")
            data  = {"chat_id": self.chat_id, "caption": caption, "parse_mode": "Markdown"}
            files = {"photo": (path.name, open(path, "rb"), "image/png")}
            resp  = requests.post(url, data=data, files=files, timeout=30)
            ok    = resp.json().get("ok", False)
            if ok:
                print(f"  📤 전송 완료: {path.name}")
            else:
                print(f"  ❌ 전송 실패: {resp.json()}")
            return ok
        except Exception as e:
            print(f"  ❌ 이미지 전송 실패 ({path.name}): {e}")
            return False

    # ── 문서(파일) 전송 ──────────────────────────────────────────────
    def send_document(self, file_path: str, caption: str = "") -> bool:
        """xlsx 등 파일을 문서로 전송합니다."""
        if not self.enabled:
            return False
        path = Path(file_path)
        if not path.exists():
            print(f"  ⚠️  파일 없음: {file_path}")
            return False
        try:
            url   = self.BASE_URL.format(token=self.token, method="sendDocument")
            data  = {"chat_id": self.chat_id, "caption": caption, "parse_mode": "Markdown"}
            files = {"document": (path.name, open(path, "rb"))}
            resp  = requests.post(url, data=data, files=files, timeout=60)
            ok    = resp.json().get("ok", False)
            if ok:
                print(f"  📎 문서 전송 완료: {path.name}")
            return ok
        except Exception as e:
            print(f"  ❌ 문서 전송 실패 ({path.name}): {e}")
            return False

    # ── 스캔 결과 일괄 전송 ──────────────────────────────────────────
    def send_daily_report(self,
                          today: str,
                          n_ich: int,
                          n_cup: int,
                          n_candle: int,
                          bt_summary: dict,
                          image_files: list[str],
                          xlsx_file: str,
                          n_bb: int = 0) -> None:
        """
        하루 스캔 결과를 순서대로 전송합니다.
          1. 요약 텍스트
          2. 시그널 이미지 (일목 / 컵핸들 / 캔들)
          3. 백테스트 이미지
          4. Excel 리포트 파일
        """
        if not self.enabled:
            return

        print("\n📨 Telegram 전송 시작...")
        date_fmt = datetime.strptime(today, "%Y%m%d").strftime("%Y년 %m월 %d일")

        # ── 1. 요약 텍스트 ────────────────────────────────────────────
        lines = [
            f"📈 *US 주식 스캐너 일일 리포트*",
            f"🗓 {date_fmt}",
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "📊 *오늘 시그널 요약*",
            f"  • 일목균형표 : *{n_ich}개*",
            f"  • 컵앤핸들   : *{n_cup}개*",
            f"  • 캔들 패턴  : *{n_candle}개*",
            f"  • 볼린저 밴드 : *{n_bb}개*",
            f"  • 합계       : *{n_ich + n_cup + n_candle + n_bb}개*",
        ]

        if bt_summary:
            lines += ["", "━━━━━━━━━━━━━━━━━━━━", "⏮ *백테스트 요약*"]
            for name, info in bt_summary.items():
                if info:
                    lines.append(
                        f"  • {name}: {info['total']}건 "
                        f"| 수익 {info['pos']}건 / 손실 {info['neg']}건 "
                        f"| 평균 {info['avg']:+.2f}%"
                    )
                else:
                    lines.append(f"  • {name}: 시그널 없음")

        lines += ["", "━━━━━━━━━━━━━━━━━━━━",
                  "_본 정보는 기술적 분석 참고용이며 투자 권유가 아닙니다._"]

        self.send_text("\n".join(lines))
        time.sleep(1)

        # ── 2. 시그널 이미지 전송 ─────────────────────────────────────
        image_labels = {
            f"Result_Ichimoku_{today}.png":  "📈 일목균형표 매수 시그널",
            f"Result_CupHandle_{today}.png": "🏆 컵앤핸들 패턴",
            f"Result_Candle_{today}.png":    "🕯 캔들 패턴",
            f"Result_BT_Ichimoku_{today}.png":  "⏮ 백테스트 — 일목균형표",
            f"Result_BT_CupHandle_{today}.png": "⏮ 백테스트 — 컵앤핸들",
            f"Result_BT_Candle_{today}.png":    "⏮ 백테스트 — 캔들 패턴",
        }

        for fname, label in image_labels.items():
            if Path(fname).exists():
                self.send_image(fname, caption=label)
                time.sleep(1)   # Telegram API rate limit 방지

        # ── 3. Excel 리포트 전송 ──────────────────────────────────────
        if Path(xlsx_file).exists():
            self.send_document(xlsx_file, caption="📂 전체 Excel 리포트")
