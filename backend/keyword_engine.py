from __future__ import annotations

from typing import Dict, Any
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

# ==============================
# 환경 변수(.env) 로드 & 클라이언트 설정
# ==============================
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "o3-mini")

if API_KEY:
    client = OpenAI(api_key=API_KEY)
else:
    client = None  # API 키 없을 때 대비


def choose_dominant_aspect(features: Dict[str, Any]) -> str:
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
    if night >= 0.7:
        candidates.append(("night_owl", night))

    emoji = float(features.get("user_emoji_ratio", 0.0) or 0.0)
    if emoji >= 0.4:
        candidates.append(("emoji", emoji))

    game = float(features.get("user_game_msg_ratio", 0.0) or 0.0)
    if game >= 0.3:
        candidates.append(("game", game))

    question = float(features.get("user_question_ratio", 0.0) or 0.0)
    if question >= 0.3:
        candidates.append(("questioner", question))

    swear = float(features.get("user_swear_msg_ratio", 0.0) or 0.0)
    if swear >= 0.1:
        candidates.append(("swear", swear))

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


def generate_label_with_llm(
    mbti_result: Dict[str, Any],
    confidence: Dict[str, Any],
) -> Dict[str, str]:
    mbti_type = mbti_result.get("type", "XXXX")
    fallback_label = f"기본형 {mbti_type}"
    fallback_keyword = "기본형"

    if client is None:
        # API 키 없으면 LLM 안 쓰고 기본값 리턴
        return {"label": fallback_label, "keyword": fallback_keyword}

    prompt = _build_label_prompt(mbti_result, confidence)

    try:
        response = client.responses.create(
            model=GPT_MODEL_NAME,
            reasoning={"effort": "low"},
            input=[
                {"role": "system", "content": "당신은 창의적인 작명가입니다."},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=32,
        )

        raw_text = ""
        if hasattr(response, "output_text") and response.output_text:
            raw_text = response.output_text.strip()
        else:
            try:
                first_output = response.output[0]
                first_content = first_output.content[0]
                raw_text = getattr(getattr(first_content, "text", ""), "value", "").strip()
            except Exception:
                raw_text = ""

        if not raw_text:
            return {"label": fallback_label, "keyword": fallback_keyword}

        # 정제 작업 (따옴표 제거 + 첫 줄만 사용)
        cleaned = raw_text.replace('"', "").replace("'", "").split("\n")[0].strip()

        # MBTI 부분 분리 시도
        if mbti_type in cleaned:
            keyword_part = cleaned.replace(mbti_type, "").strip()
        else:
            keyword_part = cleaned
            cleaned = f"{keyword_part} {mbti_type}"

        if not keyword_part:
            keyword_part = fallback_keyword

        return {
            "label": cleaned,
            "keyword": keyword_part,
        }

    except Exception as e:
        print(f"OpenAI Label Error: {e}")
        return {"label": fallback_label, "keyword": fallback_keyword}
