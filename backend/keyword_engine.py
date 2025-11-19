from __future__ import annotations

from typing import Dict, Any
import os
import re
import random

from dotenv import load_dotenv
from openai import OpenAI

# ==============================
# 환경 변수(.env) 로드 & 클라이언트 설정
# ==============================
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

if API_KEY:
    client = OpenAI(api_key=API_KEY)
else:
    client = None

print("[keyword_engine] API_KEY set:", bool(API_KEY), "client is None:", client is None)


# ==============================
# Dominant Aspect 계산
# ==============================
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
    except:
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

    return max(candidates, key=lambda x: x[1])[0]


# ==============================
# LLM 프롬프트 생성
# ==============================
def _build_label_prompt(mbti_result: Dict[str, Any], confidence: Dict[str, Any]) -> str:
    scores = mbti_result.get("scores", {})
    features = mbti_result.get("features", {})
    mbti_type = mbti_result.get("type", "XXXX")
    conf_score = confidence.get("score", 0)
    dominant = choose_dominant_aspect(features)

    prompt = f"""
역할: MBTI + 카카오톡 행동 패턴 기반의 창의적인 수식어 생성기.

입력 정보:
- MBTI: {mbti_type} (E:{scores.get("E")}, N:{scores.get("N")}, F:{scores.get("F")}, P:{scores.get("P")})
- 주요 특징(Dominant Aspect): {dominant}
- 신뢰도: {conf_score}

요청:
- 사용자의 특징을 가장 잘 나타내는 '한 단어 수식어 + MBTI' 형태의 라벨을 **3개** 만들어라.
- 반드시 아래 형식을 따라라:

label1: (수식어) (MBTI)
label2: (수식어) (MBTI)
label3: (수식어) (MBTI)

예:
label1: 야행성 ENFP
label2: 칼답러 ENFP
label3: 감성파 ENFP

규칙:
- 반드시 한 단어 수식어 사용.
- 한국어 수식어 사용.
- 다른 설명 절대 금지.
- 반드시 위 3줄 형식 그대로 출력.
"""
    return prompt


# ==============================
# 최종 라벨 + 키워드 생성
# ==============================
def generate_label_with_llm(
    mbti_result: Dict[str, Any],
    confidence: Dict[str, Any],
) -> Dict[str, str]:

    mbti_type = mbti_result.get("type", "XXXX")
    fallback_label = f"기본형 {mbti_type}"
    fallback_keyword = "기본형"

    if client is None:
        return {"label": fallback_label, "keyword": fallback_keyword}

    prompt = _build_label_prompt(mbti_result, confidence)

    model_for_chat = GPT_MODEL_NAME
    if model_for_chat.startswith("o3"):
        print("[keyword_engine] model is o3*, fallback gpt-4o-mini")
        model_for_chat = "gpt-4o-mini"

    try:
        completion = client.chat.completions.create(
            model=model_for_chat,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "반드시 label1, label2, label3 형태로만 출력하라. "
                        "설명 금지. 다른 문장 금지. 형식 변경 금지."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=128,
            temperature=1.3,
            top_p=0.9,
        )

        raw_text = (completion.choices[0].message.content or "").strip()

        # 라인별 파싱
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

        labels = []
        for line in lines:
            if line.lower().startswith("label"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    label = parts[1].strip()
                    labels.append(label)

        if not labels:
            print("[keyword_engine] parsing failed, fallback")
            return {"label": fallback_label, "keyword": fallback_keyword}

        # 🎯 후보 3개 중 랜덤 1개 선택
        selected = random.choice(labels)

        # 정제
        cleaned = selected.replace('"', "").replace("'", "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # keyword = MBTI 앞부분
        mbti_pattern = re.compile(r"\b[EI][NS][TF][PJ]\b")
        m = mbti_pattern.search(cleaned)
        if m:
            found_mbti = m.group(0)
            keyword_part = cleaned.replace(found_mbti, "").strip()
            final_label = f"{keyword_part} {mbti_type}"
        else:
            keyword_part = cleaned
            final_label = f"{cleaned} {mbti_type}"

        return {
            "label": final_label,
            "keyword": keyword_part,
        }

    except Exception as e:
        print(f"[keyword_engine] ERROR: {e}")
        return {"label": fallback_label, "keyword": fallback_keyword}
