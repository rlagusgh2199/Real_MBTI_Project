from __future__ import annotations

from typing import Dict, Any
import re
from openai import OpenAI

# ==========================================
# [설정] OpenAI API 키를 입력하세요 (llm_reporter와 동일하게)
API_KEY = "OPENAI_API_KEY" 
# ==========================================

client = OpenAI(api_key=API_KEY)
GPT_MODEL_NAME = "gpt-4o-mini"

def choose_dominant_aspect(features: Dict[str, Any]) -> str:
    # === 기존 로직 그대로 유지 ===
    topic_ratios = {
        k.replace("topic_", "").replace("_ratio", ""): v
        for k, v in features.items()
        if k.startswith("topic_") and isinstance(v, (int, float))
    }

    dominant_topic = None
    if topic_ratios:
        dominant_topic_name, dominant_topic_ratio = max(
            topic_ratios.items(), key=lambda item: item[1]
        )
        dominant_topic = (dominant_topic_name, dominant_topic_ratio)

    candidates: list[tuple[str, float]] = []

    night = float(features.get("user_night_message_ratio", 0.0) or 0.0)
    if night >= 0.7: candidates.append(("night_owl", night))

    emoji = float(features.get("user_emoji_ratio", 0.0) or 0.0)
    if emoji >= 0.4: candidates.append(("emoji", emoji))

    game = float(features.get("user_game_msg_ratio", 0.0) or 0.0)
    if game >= 0.3: candidates.append(("game", game))

    question = float(features.get("user_question_ratio", 0.0) or 0.0)
    if question >= 0.3: candidates.append(("questioner", question))

    swear = float(features.get("user_swear_msg_ratio", 0.0) or 0.0)
    if swear >= 0.1: candidates.append(("swear", swear))

    avg_reply = features.get("avg_reply_minutes", None)
    try:
        avg_reply_val = float(avg_reply) if avg_reply is not None else None
    except (TypeError, ValueError):
        avg_reply_val = None

    if avg_reply_val is not None:
        if avg_reply_val <= 10:
            score = 1.0 - max(0.0, min(avg_reply_val, 10.0)) / 10.0
            candidates.append(("fast_reply", score))
        elif avg_reply_val >= 60:
            norm = min(avg_reply_val, 180.0) - 60.0
            score = norm / 120.0
            candidates.append(("slow_reply", score))
    
    if dominant_topic and dominant_topic[1] >= 0.15:
        candidates.append(dominant_topic)

    if not candidates:
        return "neutral"

    best = max(candidates, key=lambda x: x[1])[0]
    return best


def _build_label_prompt(mbti_result: Dict[str, Any], confidence: Dict[str, Any]) -> str:
    # === 기존 로직 그대로 유지 (일부 생략했지만 핵심은 동일) ===
    scores = mbti_result["scores"]
    features = mbti_result.get("features", {})
    mbti_type = mbti_result["type"]
    conf_score = confidence.get("score", 0)
    
    dominant = choose_dominant_aspect(features)
    
    prompt = f"""
역할: 카카오톡 대화 기반 MBTI 분석 결과에 어울리는 '수식어+MBTI' 라벨 생성기

입력 정보:
- MBTI: {mbti_type} (E:{scores.get("E")}, N:{scores.get("N")}, F:{scores.get("F")}, P:{scores.get("P")})
- 주요 특징(Dominant Aspect): {dominant}
- 신뢰도: {conf_score}

요청:
- 위 사용자의 특징을 가장 잘 나타내는 '한 단어 수식어'를 창작해줘.
- 출력 형식은 오직 "수식어 MBTI" (예: "야행성 ENFP", "칼답러 ISTJ")
- 설명 금지, 따옴표 금지.
"""
    return prompt


def generate_label_with_llm(mbti_result: Dict[str, Any], confidence: Dict[str, Any]) -> Dict[str, str]:
    mbti_type = mbti_result.get("type", "XXXX")
    fallback_label = f"기본형 {mbti_type}"
    fallback_keyword = "기본형"

    prompt = _build_label_prompt(mbti_result, confidence)

    try:
        response = client.chat.completions.create(
            model=GPT_MODEL_NAME,
            messages=[
                {"role": "system", "content": "당신은 창의적인 작명가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
        )
        
        raw_text = response.choices[0].message.content.strip()
        
        # 정제 작업 (따옴표 제거 등)
        cleaned = raw_text.replace('"', '').replace("'", "").split('\n')[0]
        
        # MBTI 부분 분리 시도
        if mbti_type in cleaned:
            keyword_part = cleaned.replace(mbti_type, "").strip()
        else:
            # MBTI가 없으면 뒤에 붙여줌
            keyword_part = cleaned
            cleaned = f"{keyword_part} {mbti_type}"
            
        if not keyword_part: keyword_part = fallback_keyword

        return {
            "label": cleaned,
            "keyword": keyword_part
        }

    except Exception as e:
        print(f"OpenAI Label Error: {e}")
        return {"label": fallback_label, "keyword": fallback_keyword}