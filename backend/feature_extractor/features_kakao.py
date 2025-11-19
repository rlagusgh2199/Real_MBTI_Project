from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List
import re

# 욕설 / 강한 표현 (과제/연구용으로만 사용)
SWEAR_WORDS = [
    "시발", "씨발", "ㅅㅂ", "ㅆㅂ", "ㅂㅅ", "병신", "븅신", "존나",
    "개새끼", "새끼", "지랄", "꺼져", "미친", "또라이", "개같", "염병",
]

# 게임 관련 키워드 (롤/랭크/pc방 등)
GAME_WORDS = [
    "롤", "롤체", "리그오브레전드", "발로란트", "발로",
    "랭크", "티어", "솔랭", "듀오", "정글", "탑", "미드", "원딜", "서폿",
    "큐", "대기중", "pc방", "피시방", "게임", "배그", "피파",
]

# 대화 주제 분류용 키워드
TOPIC_KEYWORDS = {
    "daily_life": ["오늘", "어제", "내일", "아침", "점심", "저녁", "뭐해", "뭐함", "밥", "식사", "커피", "날씨", "집에"],
    "emotion": ["기분", "느낌", "슬퍼", "기뻐", "화나", "짜증", "행복", "우울", "사랑", "좋아", "싫어"],
    "planning": ["계획", "약속", "언제", "어디서", "만나", "여행", "주말에", "다음에", "같이"],
    "development": ["코딩", "개발", "프로젝트", "서버", "클라", "백엔드", "프론트", "버그", "깃", "github", "파이썬", "자바"],
    "school": ["과제", "수업", "교수님", "시험", "발표", "팀플", "도서관", "학점"],
    "hobby": ["취미", "영화", "드라마", "음악", "책", "운동", "게임", "유튜브", "넷플릭스"],
    "meme": ["ㅋㅋ", "ㅎㅎ", "레전드", "실화", "오히려", "폼 미쳤다", "가보자고", "킹받네"],
    "info_request": ["알려줘", "알려주세요", "뭐야", "뭔데", "어떻게", "왜"],
    "economy": ["주식", "코인", "돈", "경제", "가격", "비용", "투자", "월급"],
    "romance": ["연애", "소개팅", "데이트", "남친", "여친", "썸"],
}


def _get_time_bucket(dt: datetime) -> str:
    """
    대략적인 활동 시간대 버킷:
    - night : 00~06시
    - morning : 06~12시
    - afternoon : 12~18시
    - evening : 18~24시
    """
    h = dt.hour
    if 0 <= h < 6:
        return "night"
    if 6 <= h < 12:
        return "morning"
    if 12 <= h < 18:
        return "afternoon"
    return "evening"


def _count_words(text: str) -> int:
    """
    아주 단순한 단어 수 세기:
    - 공백 기준으로 split
    - 한국어 기준으로도 대략적인 “토막 수” 느낌으로 사용
    """
    if not text:
        return 0
    # 연속 공백을 자동으로 무시해주므로 그냥 split() 사용
    return len(text.split())


def _tokenize_basic(text: str) -> List[str]:
    """
    간단한 토큰 나누기 (상위 단어 집계용).
    - 알파벳/숫자/한글만 남기고 나머지는 공백 처리
    """
    if not text:
        return []
    cleaned = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", text)
    tokens = [t for t in cleaned.split() if t.strip()]
    return tokens


def extract_kakao_features(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    카카오톡 파싱 결과(dict)를 받아,
    - 발화자 비율
    - 야행성 비율
    - 질문/감탄/이모티콘 비율
    - 욕설/게임 관련 대화 비율
    - 평균 답장 시간(분)
    - ✅ 내가 쓴 단어 수 / 방 전체 단어 수
    - ✅ 시간대별 활동 비율, 상위 단어/이모티콘, 샘플 메시지
    등을 계산한다.
    """
    messages: List[Dict[str, Any]] = parsed.get("messages", [])
    meta = parsed.get("meta", {})
    user_sender = meta.get("user_sender")

    total_messages = len(messages)
    if total_messages == 0:
        return {
            "kakao_message_count": 0,
            "kakao_sender_count": 0,
            # 단어 수 0으로 세팅 (안전)
            "word_count": 0,
            "user_word_count": 0,
            "room_word_count": 0,
        }

    # 발화자별 개수
    sender_counts: Dict[str, int] = {}
    for msg in messages:
        s = msg["sender"]
        sender_counts[s] = sender_counts.get(s, 0) + 1

    # 가장 많이 말한 사람을 user로 가정 (fallback)
    if not user_sender:
        user_sender = max(sender_counts, key=sender_counts.get)

    user_msgs = [m for m in messages if m["sender"] == user_sender]
    other_msgs = [m for m in messages if m["sender"] != user_sender]

    user_msg_count = len(user_msgs)
    user_msg_ratio = user_msg_count / total_messages if total_messages > 0 else 0.0

    # ✅ 단어 수: 내 메시지 기준 + 방 전체 기준
    user_word_count = sum(_count_words(m["text"]) for m in user_msgs)
    room_word_count = sum(_count_words(m["text"]) for m in messages)

    # 평균 글자 수 (내 메시지 기준)
    if user_msg_count > 0:
        avg_user_len = sum(len(m["text"]) for m in user_msgs) / user_msg_count
    else:
        avg_user_len = 0.0

    # 시간대/샘플/상위 단어/이모티콘 집계용
    bucket_counts = {"night": 0, "morning": 0, "afternoon": 0, "evening": 0}
    night_samples: List[str] = []
    game_samples: List[str] = []
    word_freq: Dict[str, int] = {}
    emoji_freq: Dict[str, int] = {}

    # 야행성 비율 (자기 메시지 중 밤/심야 비율)
    night_count = 0

    # 질문/감탄/이모티콘/욕설/게임 관련 비율
    def is_question(text: str) -> bool:
        return "?" in text

    def is_exclamation(text: str) -> bool:
        return "!" in text

    EMO_PATTERNS = ["ㅋㅋ", "ㅎㅎ", "ㅠㅠ", "ㅠ", "ㅜㅜ", "ㅜ", "^^", "❤️", "♥", "ㅋ", "ㅎ"]

    def emoji_like_ratio(text: str) -> float:
        if not text:
            return 0.0
        count = 0
        for p in EMO_PATTERNS:
            count += text.count(p)
        # 너무 많이 나와도 최대 1.0까지만
        return min(1.0, count / max(1, len(text)))

    def contains_any(text: str, patterns: List[str]) -> bool:
        return any(p in text for p in patterns)

    q_cnt = 0
    e_cnt = 0
    emoji_ratios: List[float] = []
    swear_msg_cnt = 0
    game_msg_cnt = 0
    night_game_msg_cnt = 0
    topic_counts = {topic: 0 for topic in TOPIC_KEYWORDS}

    for m in user_msgs:
        t = m["text"]
        bucket = _get_time_bucket(m["timestamp"])
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

        # 야간 메시지 카운트
        if bucket == "night":
            night_count += 1
            if len(night_samples) < 3 and t:
                night_samples.append(t)

        # 질문/감탄/이모티콘
        if is_question(t):
            q_cnt += 1
        if is_exclamation(t):
            e_cnt += 1

        emoji_ratios.append(emoji_like_ratio(t))

        # 욕설/게임
        has_swear = contains_any(t, SWEAR_WORDS)
        has_game = contains_any(t, GAME_WORDS)

        if has_swear:
            swear_msg_cnt += 1
        if has_game:
            game_msg_cnt += 1
            if len(game_samples) < 3 and t:
                game_samples.append(t)
            if bucket == "night":
                night_game_msg_cnt += 1
        
        # 주제 분석
        for topic, keywords in TOPIC_KEYWORDS.items():
            if contains_any(t, keywords):
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # 상위 단어 수집
        for w in _tokenize_basic(t):
            w_lower = w.lower()
            # 너무 짧은 단어/숫자만 있는 토큰은 제외 (노이즈 감소용)
            if len(w_lower) < 2:
                continue
            if w_lower.isdigit():
                continue
            word_freq[w_lower] = word_freq.get(w_lower, 0) + 1

        # 상위 이모티콘/반응 수집
        for p in EMO_PATTERNS:
            c = t.count(p)
            if c > 0:
                emoji_freq[p] = emoji_freq.get(p, 0) + c

    if user_msg_count > 0:
        user_night_ratio = night_count / user_msg_count
        user_question_ratio = q_cnt / user_msg_count
        user_exclamation_ratio = e_cnt / user_msg_count
        user_emoji_ratio = sum(emoji_ratios) / len(emoji_ratios) if emoji_ratios else 0.0
        user_swear_msg_ratio = swear_msg_cnt / user_msg_count
        user_game_msg_ratio = game_msg_cnt / user_msg_count
        user_night_game_msg_ratio = (
            night_game_msg_cnt / game_msg_cnt if game_msg_cnt > 0 else 0.0
        )
    else:
        user_night_ratio = 0.0
        user_question_ratio = 0.0
        user_exclamation_ratio = 0.0
        user_emoji_ratio = 0.0
        user_swear_msg_ratio = 0.0
        user_game_msg_ratio = 0.0
        user_night_game_msg_ratio = 0.0

    # 시간대 비율 및 최다 활동 시간대
    if user_msg_count > 0:
        user_time_ratio_night = bucket_counts["night"] / user_msg_count
        user_time_ratio_morning = bucket_counts["morning"] / user_msg_count
        user_time_ratio_afternoon = bucket_counts["afternoon"] / user_msg_count
        user_time_ratio_evening = bucket_counts["evening"] / user_msg_count
        most_active_period = max(bucket_counts, key=bucket_counts.get)
    else:
        user_time_ratio_night = 0.0
        user_time_ratio_morning = 0.0
        user_time_ratio_afternoon = 0.0
        user_time_ratio_evening = 0.0
        most_active_period = None

    # 주제 비율 계산
    user_topic_ratios = {}
    if user_msg_count > 0:
        for topic, count in topic_counts.items():
            user_topic_ratios[f"topic_{topic}_ratio"] = count / user_msg_count

    # 상위 단어/이모티콘 정렬
    def _top_n(d: Dict[str, int], n: int) -> List[str]:
        return [k for k, _ in sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]]

    top_words = _top_n(word_freq, 10)
    top_emojis = _top_n(emoji_freq, 5)

    # === 내가 자주 쓰는 말 예시 (이모티콘/플레이스홀더 제외) ===
    common_samples: List[str] = []
    MAX_SAMPLES = 5

    for w in top_words:
        if len(common_samples) >= MAX_SAMPLES:
            break
        for m in user_msgs:
            t = m["text"] or ""

            # 🔥 Kakao 내보내기에서 이모티콘은 "이모티콘" 같은 텍스트로 들어오므로 걸러준다
            if "이모티콘" in t:
                continue

            # (옵션) 너무 짧은 건 제외하고 싶으면 유지, 아니라면 지워도 됨
            if len(t.strip()) < 2:
                continue

            if w in t and t not in common_samples:
                common_samples.append(t)
                if len(common_samples) >= MAX_SAMPLES:
                    break


    # 평균 답장 시간 (other -> user)
    reply_deltas: List[float] = []
    if user_msg_count > 0 and other_msgs:
        n = len(messages)
        for i, msg in enumerate(messages):
            if msg["sender"] == user_sender:
                continue
            for j in range(i + 1, n):
                if messages[j]["sender"] == user_sender:
                    delta = messages[j]["timestamp"] - msg["timestamp"]
                    minutes = delta.total_seconds() / 60.0
                    # 하루 이상 차이나면 답장이라고 보지 않고 버림
                    if 0 < minutes < 60 * 24:
                        reply_deltas.append(minutes)
                    break

    if reply_deltas:
        avg_reply_minutes = sum(reply_deltas) / len(reply_deltas)
    else:
        avg_reply_minutes = 0.0

    # 2. 참여자 수 보정 발화량 (talkativeness)
    sender_count = len(sender_counts)
    talkativeness = 0.0
    if sender_count > 0:
        # 내가 말한 비율 / (1/n) -> n명이 동등하게 말했을 때 대비 얼마나 더 말했는가
        talkativeness = user_msg_ratio / (1 / sender_count)

    features: Dict[str, Any] = {
        "kakao_message_count": total_messages,
        "kakao_sender_count": len(sender_counts),

        "user_sender_name": user_sender,

        # ✅ 단어 수 관련
        # - word_count: "내가 쓴 단어 수" (MBTI/신뢰도에서 사용할 값)
        # - user_word_count: 내가 쓴 단어 수 (디버그/표시용)
        # - room_word_count: 방 전체 단어 수 (참고용)
        "word_count": user_word_count,
        "user_word_count": user_word_count,
        "room_word_count": room_word_count,

        "user_message_ratio": user_msg_ratio,
        "talkativeness": talkativeness, # ✅ 참여자 수 보정 발화량
        "user_avg_chars_per_message": avg_user_len,
        "user_night_message_ratio": user_night_ratio,
        "user_question_ratio": user_question_ratio,
        "user_exclamation_ratio": user_exclamation_ratio,
        "user_emoji_ratio": user_emoji_ratio,
        "user_swear_msg_ratio": user_swear_msg_ratio,
        "user_game_msg_ratio": user_game_msg_ratio,
        "user_night_game_msg_ratio": user_night_game_msg_ratio,
        "avg_reply_minutes": avg_reply_minutes,

        # ✅ 시간대 관련
        "user_time_ratio_night": user_time_ratio_night,
        "user_time_ratio_morning": user_time_ratio_morning,
        "user_time_ratio_afternoon": user_time_ratio_afternoon,
        "user_time_ratio_evening": user_time_ratio_evening,
        "user_most_active_period": most_active_period,

        # ✅ 상위 단어/이모티콘 + 샘플 메시지
        "user_top_words": top_words,
        "user_top_emojis": top_emojis,
        "sample_night_messages": night_samples,
        "sample_game_messages": game_samples,
        "sample_common_messages": common_samples,
    }
    
    # 주제 비율 추가
    features.update(user_topic_ratios)

    return features
