from __future__ import annotations

from typing import Dict, Any
import os

from dotenv import load_dotenv
from openai import OpenAI

# ==============================
# 환경 변수(.env) 로드 & 클라이언트 설정
# ==============================
load_dotenv()  # .env 파일 자동 로드

API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "o3-mini")

if API_KEY:
    client = OpenAI(api_key=API_KEY)
else:
    client = None  # API 키 없을 때를 대비


def _build_prompt(mbti_result: Dict[str, Any], confidence: Dict[str, Any]) -> str:
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
    header = "=== Real MBTI 리포트 (AI 분석) ===\n"

    if client is None:
        # API 키가 설정 안 된 경우 안전하게 처리
        return (
            header
            + "AI 리포트를 생성하려면 OPENAI_API_KEY 환경변수가 필요합니다.\n"
            + "서버의 .env 파일 또는 환경변수를 확인해주세요."
        )

    prompt = _build_prompt(mbti_result, confidence)

    try:
        # o3-mini / o3 는 Responses API 사용 + temperature 등 미지원
        response = client.responses.create(
            model=GPT_MODEL_NAME,
            reasoning={"effort": "medium"},  # 필요 없으면 제거해도 됨
            input=[
                {"role": "system", "content": "당신은 전문 심리 분석가이자 데이터 과학자입니다."},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=2000,  # 리포트 길이 제한
        )

        # 최신 SDK에서는 output_text 속성 제공
        llm_text = ""
        if hasattr(response, "output_text") and response.output_text:
            llm_text = response.output_text.strip()
        else:
            # 혹시 모를 호환성 문제 대비한 fallback
            try:
                first_output = response.output[0]
                first_content = first_output.content[0]
                llm_text = getattr(getattr(first_content, "text", ""), "value", "").strip()
            except Exception:
                llm_text = "AI 응답 파싱 중 예상치 못한 형식이 감지되었습니다."

        if not llm_text:
            llm_text = "AI로부터 유효한 리포트를 받지 못했습니다."

        return header + llm_text

    except Exception as e:
        print(f"OpenAI API Error: {e}")
        return (
            header
            + "AI 서버와의 연결이 원활하지 않아 상세 리포트를 생성하지 못했습니다.\n\n"
            + f"(디버그용 에러 메시지: {str(e)})"
        )
    
def _build_persona_prompt(mbti_result: Dict[str, Any]) -> str:
    """
    MBTI 결과(dict)를 받아, 사용자 소개용 페르소나 개요 프롬프트를 만든다.
    """
    mbti_type = mbti_result.get("type", "????")
    explanation = mbti_result.get("explanation", {}) or {}

    # 축별 설명 중 앞부분 1~2개만 간단히 모아서 힌트로 넘긴다.
    axis_summaries = []
    for axis in ["E", "I", "S", "N", "T", "F", "J", "P"]:
        lines = explanation.get(axis) or []
        if not lines:
            continue
        axis_summaries.append(f"{axis}: " + " / ".join(lines[:2]))

    axis_text = (
        "\n".join(axis_summaries)
        if axis_summaries
        else "축별 설명은 따로 제공되지 않았습니다."
    )

    prompt = f"""
너는 'Real MBTI' 서비스에서 사용자를 소개하는 카피를 작성하는 작성자야.

[MBTI 유형]
- {mbti_type}

[행동 특징 요약]
{axis_text}

위 정보를 바탕으로, 이 사용자를 소개하는 짧은 페르소나 개요를 작성해줘.

조건:
- 한국어로 작성
- 3~5문장 정도의 하나의 단락
- "~한 편입니다.", "~하는 스타일입니다." 처럼 부드럽고 자연스러운 말투
- MBTI 이론 강의처럼 딱딱하게 설명하지 말고, 실제 사람을 소개하듯 써줘
- 첫 문장 또는 두 번째 문장 안에 "{mbti_type}" 라는 타입 이름을 한 번 언급해줘
"""
    return prompt

def generate_persona_overview(mbti_result: Dict[str, Any]) -> str:
    """
    MBTI 결과를 기반으로 한 페르소나 개요 문단을 생성한다.
    - OPENAI_API_KEY가 없거나 오류가 나면 빈 문자열("")을 반환한다.
    """
    if client is None:
        # API 키 없으면 조용히 빈 문자열 리턴 (프론트에서 옵션으로 처리)
        return ""

    prompt = _build_persona_prompt(mbti_result)

    try:
        response = client.responses.create(
            model=GPT_MODEL_NAME,
            reasoning={"effort": "medium"},
            input=[
                {
                    "role": "system",
                    "content": "너는 한국어로 친근하고 간결하게 성격을 설명해 주는 도우미야.",
                },
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=2000,
        )

        text = ""
        if hasattr(response, "output_text") and response.output_text:
            text = response.output_text.strip()
        else:
            # generate_report 와 동일한 fallback 로직 재사용
            try:
                first_output = response.output[0]
                first_content = first_output.content[0]
                text = getattr(getattr(first_content, "text", ""), "value", "").strip()
            except Exception:
                text = ""

        return text
    except Exception as e:
        print(f"OpenAI API Error (persona): {e}")
        return ""
