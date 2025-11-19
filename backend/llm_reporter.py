from __future__ import annotations

from typing import Dict, Any
import os
from openai import OpenAI

# ==========================================
# [설정] OpenAI API 키를 입력하세요
# (보안을 위해 나중에는 환경변수로 빼는 것이 좋습니다)
API_KEY = "OPENAI_API_KEY" 
# ==========================================

client = OpenAI(api_key=API_KEY)

# GPT 모델 설정 (가성비: gpt-4o-mini / 고성능: gpt-4o)
GPT_MODEL_NAME = "gpt-4o-mini"

def _build_prompt(mbti_result: Dict[str, Any], confidence: Dict[str, Any]) -> str:
    # === 기존 프롬프트 로직 그대로 유지 ===
    scores = mbti_result["scores"]
    features = mbti_result.get("features", {})
    explanation = mbti_result.get("explanation", {})
    mbti_type = mbti_result["type"]

    conf_score = confidence["score"]
    conf_level = confidence["level"]

    user_name = features.get("user_sender_name", "사용자")
    user_msg_ratio = features.get("user_message_ratio", 0.0)
    user_night_ratio = features.get("user_night_message_ratio", 0.0)
    avg_reply = features.get("avg_reply_minutes", 0.0)
    msg_count = features.get("kakao_message_count", 0)
    word_count = features.get("word_count", 0)
    user_emoji_ratio = features.get("user_emoji_ratio", 0.0)
    user_swear_ratio = features.get("user_swear_msg_ratio", 0.0)
    user_game_ratio = features.get("user_game_msg_ratio", 0.0)
    user_night_game_ratio = features.get("user_night_game_msg_ratio", 0.0)

    topic_ratios = {
        k.replace("topic_", "").replace("_ratio", ""): v
        for k, v in features.items()
        if k.startswith("topic_") and isinstance(v, (int, float)) and v > 0.01
    }
    sorted_topics = sorted(topic_ratios.items(), key=lambda item: item[1], reverse=True)
    
    topic_summary = "\n".join(
        [f"- {topic.replace('_', ' ').title()}: {ratio:.2%}" for topic, ratio in sorted_topics]
    )
    if not topic_summary:
        topic_summary = "특별히 두드러지는 대화 주제가 없습니다."
        
    persona = explanation.get("persona", "default")
    persona_map = {
        "developer": "개발자/분석가",
        "socializer": "사교가/관계중심",
        "hobbyist": "취미가/자유로운 영혼",
        "planner": "계획가/체계적",
        "default": "균형잡힌",
    }
    persona_kr = persona_map.get(persona, "균형잡힌")

    prompt = f"""
너는 'Real MBTI'라는 시스템의 설명을 담당하는 분석가야.
이 시스템은 카카오톡 대화 로그를 기반으로 사용자의 행동 패턴을 분석하고,
규칙 기반으로 MBTI 점수를 계산한 뒤, 너에게 그 결과를 보내 해석을 부탁한다.

[MBTI 점수]
- 유형: {mbti_type}
- E: {scores['E']} / I: {scores['I']}
- S: {scores['S']} / N: {scores['N']}
- T: {scores['T']} / F: {scores['F']}
- J: {scores['J']} / P: {scores['P']}

[추정 페르소나]
- {persona_kr} (대화 주제 기반 추정)

[텍스트 기반 특징]
- 단어 수: {word_count}, 문장 길이: {features.get('avg_sentence_len')}
- 1인칭: {features.get('first_person_ratio'):.3f}, 질문: {features.get('question_ratio'):.3f}
- 감탄사: {features.get('exclamation_ratio'):.3f}
- 긍정: {features.get('positive_ratio'):.3f}, 부정: {features.get('negative_ratio'):.3f}

[대화 패턴]
- 총 메시지: {msg_count}, 닉네임: {user_name}
- 본인 발화 점유율: {user_msg_ratio:.3f}
- 야간 발화 비율: {user_night_ratio:.3f}
- 이모티콘 비율: {user_emoji_ratio:.3f}
- 욕설/강한 표현: {user_swear_ratio:.3f}
- 게임 대화: {user_game_ratio:.3f} (야간 게임: {user_night_game_ratio:.3f})
- 질문 비율: {features.get('user_question_ratio', 0.0):.3f}
- 평균 답장 시간: {avg_reply:.1f}분

[주요 대화 주제]
{topic_summary}

[신뢰도]
- {conf_score}점 ({conf_level})

요청사항:
1. 사용자의 MBTI 유형({mbti_type})을 한 문단으로 요약 설명해줘.
2. E/I, S/N, T/F, J/P 각 축의 점수와 위 행동 데이터(페르소나, 패턴, 주제)를 연결해서 설명해줘.
   (예: "개발 주제 대화가 많아 T 성향이 높게 측정되었습니다.")
3. 예상되는 생활/대인관계 특징 3~5가지를 bullet point로 작성해줘.
4. 마지막에 이 분석은 카톡 데이터와 알고리즘 기반의 '참고용 분석'임을 명시해줘.
5. 한국어로 부드럽고 전문적인 어조로 작성해줘.
"""
    return prompt

def generate_report(mbti_result: Dict[str, Any], confidence: Dict[str, Any]) -> str:
    prompt = _build_prompt(mbti_result, confidence)

    try:
        response = client.chat.completions.create(
            model=GPT_MODEL_NAME,
            messages=[
                {"role": "system", "content": "당신은 전문 심리 분석가이자 데이터 과학자입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        
        llm_text = response.choices[0].message.content.strip()
        
        header = "=== Real MBTI 리포트 (AI 분석 완료) ===\n"
        return header + llm_text

    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return (
            "=== Real MBTI 리포트 (분석 지연) ===\n"
            "AI 서버와의 연결이 원활하지 않아 상세 리포트를 생성하지 못했습니다.\n\n"
            f"에러 메시지: {str(e)}"
        )