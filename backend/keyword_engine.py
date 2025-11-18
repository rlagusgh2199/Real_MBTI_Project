from __future__ import annotations

from typing import Dict, Any
import re

import requests

from .llm_reporter import OLLAMA_API_URL, OLLAMA_MODEL_NAME


def choose_dominant_aspect(features: Dict[str, Any]) -> str:
    """
    여러 행동 지표 중에서 "가장 튀는 축"을 하나 고른다.
    이 값은 LLM 프롬프트에 dominant_aspect 로 전달되어,
    어떤 방향의 수식어를 만들지 힌트를 주는 용도로만 사용된다.
    """
    # 주제 분석 결과 중 가장 높은 비율을 가진 주제를 찾는다.
    topic_ratios = {
        k.replace("topic_", "").replace("_ratio", ""): v
        for k, v in features.items()
        if k.startswith("topic_") and isinstance(v, (int, float))
    }

    dominant_topic = None
    if topic_ratios:
        # 가장 비율이 높은 주제
        dominant_topic_name, dominant_topic_ratio = max(
            topic_ratios.items(), key=lambda item: item[1]
        )
        dominant_topic = (dominant_topic_name, dominant_topic_ratio)

    candidates: list[tuple[str, float]] = []

    # 야행성: 밤(대략 21시~03시)에 보낸 메시지 비율
    night = float(features.get("user_night_message_ratio", 0.0) or 0.0)
    if night >= 0.7:
        candidates.append(("night_owl", night))

    # 이모티콘/감정 표현
    emoji = float(features.get("user_emoji_ratio", 0.0) or 0.0)
    if emoji >= 0.4:
        candidates.append(("emoji", emoji))

    # 게임/밈 대화 비율
    game = float(features.get("user_game_msg_ratio", 0.0) or 0.0)
    if game >= 0.3:
        candidates.append(("game", game))

    # 질문형 메시지 비율
    question = float(features.get("user_question_ratio", 0.0) or 0.0)
    if question >= 0.3:
        candidates.append(("questioner", question))

    # 욕설/강한 표현 비율
    swear = float(features.get("user_swear_msg_ratio", 0.0) or 0.0)
    if swear >= 0.1:
        candidates.append(("swear", swear))

    # 평균 답장 시간 (분) 기준: 매우 빠른/매우 느린 경우만 후보에 추가
    avg_reply = features.get("avg_reply_minutes", None)
    try:
        avg_reply_val = float(avg_reply) if avg_reply is not None else None
    except (TypeError, ValueError):
        avg_reply_val = None

    if avg_reply_val is not None:
        # 10분 이내: 즉답러
        if avg_reply_val <= 10:
            # 0분(바로바로 답장)에 가까울수록 점수 ↑
            score = 1.0 - max(0.0, min(avg_reply_val, 10.0)) / 10.0
            candidates.append(("fast_reply", score))
        # 60분(1시간) 이상: 느린 답장
        elif avg_reply_val >= 60:
            # 60분에서 180분(3시간) 사이를 0~1 스케일로 정규화
            norm = min(avg_reply_val, 180.0) - 60.0
            score = norm / 120.0  # 60~180분 -> 0~1
            candidates.append(("slow_reply", score))
    
    # 가장 두드러지는 주제가 특정 임계값(e.g., 15%)을 넘으면 후보에 추가
    if dominant_topic and dominant_topic[1] >= 0.15:
        # 주제 비율을 그대로 점수로 사용
        candidates.append(dominant_topic)

    if not candidates:
        return "neutral"

    # 가장 스코어가 높은 축 선택
    best = max(candidates, key=lambda x: x[1])[0]
    return best


def _build_label_prompt(mbti_result: Dict[str, Any], confidence: Dict[str, Any]) -> str:
    scores = mbti_result["scores"]
    features = mbti_result.get("features", {})
    mbti_type = mbti_result["type"]

    conf_score = confidence.get("score", 0)
    conf_level = confidence.get("level", "unknown")

    # 행동 지표들 (없으면 0으로 처리)
    night = float(features.get("user_night_message_ratio", 0.0) or 0.0)
    emoji = float(features.get("user_emoji_ratio", 0.0) or 0.0)
    game = float(features.get("user_game_msg_ratio", 0.0) or 0.0)
    swear = float(features.get("user_swear_msg_ratio", 0.0) or 0.0)
    question = float(features.get("user_question_ratio", 0.0) or 0.0)
    avg_reply = features.get("avg_reply_minutes", None)
    try:
        avg_reply_val = float(avg_reply) if avg_reply is not None else None
    except (TypeError, ValueError):
        avg_reply_val = None

    # 새로 추가된 참고용 정보
    most_active = features.get("user_most_active_period")  # night/morning/...
    top_words = features.get("user_top_words") or []
    top_emojis = features.get("user_top_emojis") or []

    # 주제 분석 요약
    topic_ratios = {
        k.replace("topic_", "").replace("_ratio", ""): v
        for k, v in features.items()
        if k.startswith("topic_") and isinstance(v, (int, float)) and v > 0.01
    }
    sorted_topics = sorted(topic_ratios.items(), key=lambda item: item[1], reverse=True)
    topic_summary = ", ".join(
        [f"{topic.replace('_', ' ').title()} ({ratio:.1%})" for topic, ratio in sorted_topics[:3]]
    )
    if not topic_summary:
        topic_summary = "정보 없음"

    # 문자열로 정리
    top_words_str = ", ".join(top_words[:5])
    top_emojis_str = " ".join(top_emojis[:5])

    # 가장 두드러지는 특징(aspect) 선택
    dominant = choose_dominant_aspect(features)

    reply_str = f"{avg_reply_val:.1f}" if avg_reply_val is not None else "알 수 없음"

    prompt = f"""
역할: 당신은 카카오톡 대화 기반 MBTI 분석 결과에 어울리는 짧은 수식어를 붙여주는 어시스턴트입니다.

조건:
- 출력은 반드시 한 줄이고, 형식은 정확히 다음과 같습니다: 수식어 MBTI
- 예: "야행성 ESFP", "이모티콘 부자 INFP", "즉답 ENFJ"
- 수식어는 1~4글자의 자연스러운 한국어 표현으로, 한 단어 또는 두 단어(띄어쓰기 최대 1회)만 사용합니다.
- 비속어, 심한 욕설은 사용하지 않습니다.
- 따옴표("), 괄호, 이모티콘, 설명 문장은 쓰지 않습니다.
- 결과에는 반드시 MBTI 네 글자를 포함해야 합니다.

입력 정보:
- MBTI: {mbti_type}
- MBTI 점수:
  - E: {scores.get("E", 0)} / I: {scores.get("I", 0)}
  - S: {scores.get("S", 0)} / N: {scores.get("N", 0)}
  - T: {scores.get("T", 0)} / F: {scores.get("F", 0)}
  - J: {scores.get("J", 0)} / P: {scores.get("P", 0)}
- 신뢰도:
  - 점수: {conf_score} / 100
  - 수준: {conf_level}

주요 행동 지표:
- 야행성(user_night_message_ratio): {night:.3f}
- 이모티콘/감정 표현(user_emoji_ratio): {emoji:.3f}
- 게임 관련 대화(user_game_msg_ratio): {game:.3f}
- 욕설/강한 표현(user_swear_msg_ratio): {swear:.3f}
- 질문형 메시지 비율(user_question_ratio): {question:.3f}
- 평균 답장 시간(avg_reply_minutes, 분): {reply_str}

추가 참고:
- 가장 많이 활동하는 시간대: {most_active or "알 수 없음"}
- 자주 쓰는 단어 예시: {top_words_str or "정보 없음"}
- 자주 쓰는 이모티콘/반응: {top_emojis_str or "정보 없음"}
- 주요 대화 주제: {topic_summary}

dominant_aspect(가장 강조하고 싶은 축): {dominant}
- night_owl: 밤늦게 카톡을 많이 보내는 패턴
- emoji: 이모티콘/감정 표현을 많이 쓰는 패턴
- game: 게임/밈 관련 대화 비율이 높은 패턴
- questioner: 질문을 많이 하는 패턴
- fast_reply: 답장을 빠르게 보내는 패턴
- slow_reply: 답장이 느리거나 띄엄띄엄인 패턴
- swear: 거칠고 직설적인 말투를 사용하는 패턴
- neutral: 특별히 튀는 지표 없이 균형 잡힌 패턴
- 그 외 (development, romance, economy 등): 해당 주제의 대화 비율이 특히 높은 패턴

요청:
- 위 정보를 종합적으로 참고해서, 이 사용자의 카카오톡 말투/행동/관심사를 한 단어로 요약하는 "수식어"를 만들고 MBTI 앞에 붙여 주세요.
- 특히 `dominant_aspect`와 `주요 대화 주제`를 가장 중요한 힌트로 사용하세요. 예를 들어 dominant_aspect가 'development'라면 '코딩하는', '개발하는' 같은 수식어를, 'romance'라면 '로맨틱한', '사랑꾼' 같은 수식어를 만들 수 있습니다.
- 예시와 완전히 같은 표현은 피하고, 비슷한 느낌의 새로운 수식어를 만드세요.
- 최종 출력은 설명 없이 오직 한 줄, "수식어 MBTI" 형식으로만 출력하세요.
"""
    return prompt


def generate_label_with_llm(mbti_result: Dict[str, Any],
                            confidence: Dict[str, Any]) -> Dict[str, str]:
    """
    LLM에게 '수식어 MBTI' 한 줄을 만들어 달라고 요청한다.
    - label: 최종 출력("야행성 ESFP")
    - keyword: MBTI 앞에 붙는 수식어("야행성")
    실패하거나 형식이 맞지 않으면 '기본형 ESFP'와 같은 fallback을 사용한다.
    """
    mbti_type = mbti_result.get("type", "XXXX")
    fallback_label = f"기본형 {mbti_type}"
    fallback_keyword = "기본형"

    prompt = _build_label_prompt(mbti_result, confidence)

    payload = {
        "model": OLLAMA_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
        response.raise_for_status()
    except Exception:
        # Ollama 호출 실패 시 규칙 기반 기본 라벨 반환
        return {"label": fallback_label, "keyword": fallback_keyword}

    try:
        data = response.json()
    except Exception:
        return {"label": fallback_label, "keyword": fallback_keyword}

    raw_text = (
        data.get("response")
        or data.get("output")
        or ""
    ).strip()

    if not raw_text:
        return {"label": fallback_label, "keyword": fallback_keyword}

    # 여러 줄이 나왔다면 첫 번째 의미 있는 줄만 사용
    first_line = next((ln.strip() for ln in raw_text.splitlines() if ln.strip()), "")
    if not first_line:
        return {"label": fallback_label, "keyword": fallback_keyword}

    # 따옴표 등 불필요한 문자 제거
    cleaned = first_line.strip().strip('"').strip("'")

    # MBTI 네 글자를 찾아본다.
    mbti_pattern = re.compile(r"(E|I)(S|N)(T|F)(J|P)")
    match = mbti_pattern.search(cleaned)
    if match:
        mbti_in_text = match.group(0)
    else:
        mbti_in_text = mbti_type

    # keyword = 전체 문자열에서 MBTI 부분을 제거한 나머지
    if mbti_in_text in cleaned:
        keyword_part = cleaned.replace(mbti_in_text, "").strip()
        # '수식어 MBTI' 형태일 걸 가정하고, 양쪽 공백 정리
        if not keyword_part:
            keyword_part = fallback_keyword
    else:
        keyword_part = fallback_keyword

    final_label = f"{keyword_part} {mbti_type}".strip()

    return {
        "label": final_label,
        "keyword": keyword_part,
    }
