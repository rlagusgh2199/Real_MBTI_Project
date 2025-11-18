from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Any, List, Optional

# 스타일 A (예전/다른 형식: "2025년 9월 7일 오후 11:22, 김현호 : 안녕")
STYLE_A_PATTERN = re.compile(
    r"^(\d{4})년 (\d{1,2})월 (\d{1,2})일\s+"
    r"(오전|오후)\s+(\d{1,2}):(\d{2}),\s"
    r"(.+?)\s:\s(.+)$"
)

# 스타일 B 날짜 줄: "--------------- 2025년 9월 7일 일요일 ---------------"
DATE_LINE_PATTERN = re.compile(
    r"^-{3,}\s*(\d{4})년\s(\d{1,2})월\s(\d{1,2})일.*-{3,}\s*$"
)

# 스타일 B 메시지 줄: "[김현호] [오전 11:22] 안녕"
STYLE_B_PATTERN = re.compile(
    r"^\[(.+?)\]\s\[(오전|오후)\s(\d{1,2}):(\d{2})\]\s(.+)$"
)


def _build_datetime(
    year: int,
    month: int,
    day: int,
    ampm: str,
    hour: int,
    minute: int,
) -> datetime:
    """카카오 오전/오후 → 24시간제로 변환."""
    if ampm == "오후" and hour != 12:
        hour += 12
    if ampm == "오전" and hour == 12:
        hour = 0
    return datetime(year, month, day, hour, minute)


def parse_kakao_txt(raw_text: str) -> Dict[str, Any]:
    """
    카카오톡 내보내기 txt를 파싱해서

    [
      {"timestamp": datetime, "sender": "김현호", "text": "안녕"},
      ...
    ]

    형태의 messages 리스트로 변환한다.

    - 스타일 A: 2025년 9월 7일 오후 11:22, 김현호 : 안녕
    - 스타일 B(지금 네 파일): 날짜 구분선 + [이름] [오전 11:22] 내용
    """
    lines = raw_text.splitlines()

    messages: List[Dict[str, Any]] = []
    current_msg: Optional[Dict[str, Any]] = None

    # 스타일 B용 현재 날짜
    current_year: Optional[int] = None
    current_month: Optional[int] = None
    current_day: Optional[int] = None

    for line in lines:
        line = line.rstrip("\n")
        if not line.strip():
            continue

        # 1) 스타일 B 날짜 라인인지 먼저 확인
        m_date = DATE_LINE_PATTERN.match(line.strip())
        if m_date:
            current_year = int(m_date.group(1))
            current_month = int(m_date.group(2))
            current_day = int(m_date.group(3))
            # 날짜 라인이 나오면, 이전 메시지는 확정
            if current_msg is not None:
                messages.append(current_msg)
                current_msg = None
            continue

        # 2) 스타일 A 형식인지 체크
        m_a = STYLE_A_PATTERN.match(line.strip())
        if m_a:
            if current_msg is not None:
                messages.append(current_msg)

            year = int(m_a.group(1))
            month = int(m_a.group(2))
            day = int(m_a.group(3))
            ampm = m_a.group(4)
            hour = int(m_a.group(5))
            minute = int(m_a.group(6))
            sender = m_a.group(7).strip()
            text = m_a.group(8).strip()

            ts = _build_datetime(year, month, day, ampm, hour, minute)
            current_msg = {
                "timestamp": ts,
                "sender": sender,
                "text": text,
            }
            continue

        # 3) 스타일 B 메시지 형식인지 체크
        m_b = STYLE_B_PATTERN.match(line.strip())
        if m_b and current_year is not None:
            if current_msg is not None:
                messages.append(current_msg)

            sender = m_b.group(1).strip()
            ampm = m_b.group(2)
            hour = int(m_b.group(3))
            minute = int(m_b.group(4))
            text = m_b.group(5).strip()

            ts = _build_datetime(current_year, current_month, current_day, ampm, hour, minute)
            current_msg = {
                "timestamp": ts,
                "sender": sender,
                "text": text,
            }
            continue

        # 4) 위 어느 형식도 아니면 → 이전 메시지의 이어쓰기(줄바꿈 포함)
        if current_msg is not None:
            current_msg["text"] += "\n" + line.strip()
        # current_msg가 없는 경우(헤더 등)는 그냥 무시

    if current_msg is not None:
        messages.append(current_msg)

    # 메타 정보
    senders: Dict[str, int] = {}
    for msg in messages:
        senders[msg["sender"]] = senders.get(msg["sender"], 0) + 1

    # 가장 많이 말한 사람을 user로 가정
    user_sender: Optional[str] = None
    if senders:
        user_sender = max(senders, key=senders.get)

    combined_text = "\n".join(m["text"] for m in messages)

    return {
        "messages": messages,
        "meta": {
            "source": "kakao",
            "line_count": len(lines),
            "message_count": len(messages),
            "senders": senders,
            "user_sender": user_sender,
        },
        "raw_text": combined_text,
    }
