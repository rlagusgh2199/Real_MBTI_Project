from __future__ import annotations

from typing import Dict, Any
import requests

OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL_NAME = "exaone3.5:2.4b"  # 필요하면 다른 모델 이름으로 변경


def _build_prompt(mbti_result: Dict[str, Any], confidence: Dict[str, Any]) -> str:
    scores = mbti_result["scores"]
    features = mbti_result.get("features", {})
    explanation = mbti_result.get("explanation", {})
    mbti_type = mbti_result["type"]

    conf_score = confidence["score"]
    conf_level = confidence["level"]

    # 카톡 전용 특징
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

    # 주제 분석 특징을 문자열로 예쁘게 포맷
    topic_ratios = {
        k.replace("topic_", "").replace("_ratio", ""): v
        for k, v in features.items()
        if k.startswith("topic_") and isinstance(v, (int, float)) and v > 0.01
    }
    # 비율이 높은 순으로 정렬
    sorted_topics = sorted(topic_ratios.items(), key=lambda item: item[1], reverse=True)
    
    topic_summary = "\n".join(
        [f"- {topic.replace('_', ' ').title()}: {ratio:.2%}" for topic, ratio in sorted_topics]
    )
    if not topic_summary:
        topic_summary = "특별히 두드러지는 대화 주제가 없습니다."
        
    # 페르소나 정보 추가
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

[추정 페르소나 (Persona)]
- 시스템이 추정한 당신의 대화 스타일 페르소나: {persona_kr}
- (참고: 이 페르소나는 대화 주제 비율을 바탕으로 추정되었으며, MBTI 점수 계산 시 일부 행동 지표의 가중치를 동적으로 조절하는 데 사용되었습니다.)


[텍스트 기반 특징(요약)]
- 전체 단어 수(word_count): {word_count}
- 평균 문장 길이(avg_sentence_len): {features.get('avg_sentence_len')}
- 1인칭 비율(first_person_ratio): {features.get('first_person_ratio'):.3f}
- 질문 비율(question_ratio): {features.get('question_ratio'):.3f}
- 느낌표 비율(exclamation_ratio): {features.get('exclamation_ratio'):.3f}
- 긍정 단어 비율(positive_ratio): {features.get('positive_ratio'):.3f}
- 부정 단어 비율(negative_ratio): {features.get('negative_ratio'):.3f}

[카카오톡 대화 패턴]
- 대화 총 메시지 수: {msg_count}
- 추정 사용자 닉네임: {user_name}
- 사용자의 발화 비율(user_message_ratio): {user_msg_ratio:.3f}
- 야간(00~06시) 발화 비율(user_night_message_ratio): {user_night_ratio:.3f}
- 이모티콘/감정 표현 비율(user_emoji_ratio): {user_emoji_ratio:.3f}
- 욕설/강한 표현이 포함된 메시지 비율(user_swear_msg_ratio): {user_swear_ratio:.3f}
- 게임 관련 대화 비율(user_game_msg_ratio): {user_game_ratio:.3f}
- 그 중 야간 게임 대화 비율(user_night_game_msg_ratio): {user_night_game_ratio:.3f}
- 사용자 메시지당 평균 글자 수(user_avg_chars_per_message): {features.get('user_avg_chars_per_message', 0.0):.1f}
- 질문형 메시지 비율(user_question_ratio): {features.get('user_question_ratio', 0.0):.3f}
- 평균 답장 시간(avg_reply_minutes, 분): {avg_reply:.1f}

[주요 대화 주제 비율]
{topic_summary}

[신뢰도(Confidence)]
- 점수: {conf_score} / 100
- 수준: {conf_level}

요청사항:
1. 한 문단 정도로 사용자의 MBTI 유형을 요약해서 설명해줘.
2. 각 축(E/I, S/N, T/F, J/P)에 대해 점수가 무엇을 의미하는지 설명해줘.
   - 특히, 위 [추정 페르소나], [카카오톡 대화 패턴], [주요 대화 주제 비율]을 종합적으로 연결하여 사용자가 공감할 수 있도록 설명해줘.
   - 예를 들어, "당신은 '개발자' 페르소나로 분석되었는데, T 성향이 높게 나타난 것은 이러한 페르소나의 특성과 관련이 깊습니다. 개발/분석 주제의 대화에서 나타나는 직설적인 표현은 감정적인 이유보다는 논리적인 사고의 결과로 해석되어 T 점수에 더 큰 영향을 주었습니다." 와 같이 페르소나가 분석에 미친 영향을 구체적으로 언급해줘.
3. 일/대인관계/생활 패턴에서 예상되는 특징을 3~5가지 정도 bullet point로 써줘.
4. 마지막에, 이 분석이 정식 심리검사가 아니라:
   - 카카오톡 행동 데이터
   - 규칙 기반 알고리즘
   - 그리고 너(LLM)의 자연어 해석
   을 조합한 "참고용 분석"이라는 점과, 데이터의 양/기간/편향에 따라 실제 성격과 차이가 있을 수 있다는 점을 2~3줄로 정리해줘.
5. 전체 답변은 한국어로 써줘.
"""
    return prompt


def generate_report(mbti_result: Dict[str, Any], confidence: Dict[str, Any]) -> str:
    prompt = _build_prompt(mbti_result, confidence)

    payload = {
        "model": OLLAMA_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
    except Exception as e:
        return (
            "=== Real MBTI 리포트 (LLM 호출 실패) ===\n"
            f"Ollama 호출 중 오류가 발생했습니다: {e}\n\n"
            "현재는 규칙 기반 점수와 신뢰도까지만 확인할 수 있습니다."
        )

    try:
        data = response.json()
    except Exception as e:
        return (
            "=== Real MBTI 리포트 (LLM 응답 파싱 실패) ===\n"
            f"JSON 파싱 중 오류가 발생했습니다: {e}\n\n"
            f"원본 응답: {response.text[:500]}..."
        )

    llm_text = (
        data.get("response")
        or data.get("output")
        or ""
    ).strip()

    if not llm_text:
        return (
            "=== Real MBTI 리포트 (LLM 응답 비어 있음) ===\n"
            "Ollama에서 유효한 응답을 받지 못했습니다.\n"
        )

    header = "=== Real MBTI 리포트 (LLM 기반) ===\n"
    return header + llm_text
