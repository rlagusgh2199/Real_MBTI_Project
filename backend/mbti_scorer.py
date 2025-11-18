from __future__ import annotations

from typing import Dict, Any



def _clamp(value: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
    return max(min_value, min(max_value, value))


def score_mbti(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    특징(features)을 받아 MBTI 4축 점수(E/I, S/N, T/F, J/P)를 계산한다.
    - 점수 범위: 0 ~ 100
    - 예: E=70, I=30 (항상 E+I=100 되도록)
    """

    # 공통 텍스트 특징
    word_count = features.get("word_count", 0)
    avg_sentence_len = features.get("avg_sentence_len", 0.0)
    first_person_ratio = features.get("first_person_ratio", 0.0)
    question_ratio = features.get("question_ratio", 0.0)
    exclamation_ratio = features.get("exclamation_ratio", 0.0)
    positive_ratio = features.get("positive_ratio", 0.0)
    negative_ratio = features.get("negative_ratio", 0.0)

    # 카카오톡 전용 특징
    talkativeness = features.get("talkativeness", 1.0) # 1.0이 평균
    user_night_ratio = features.get("user_night_message_ratio", 0.0)
    user_question_ratio = features.get("user_question_ratio", question_ratio)
    user_exclamation_ratio = features.get("user_exclamation_ratio", exclamation_ratio)
    user_emoji_ratio = features.get("user_emoji_ratio", 0.0)
    avg_reply_minutes = features.get("avg_reply_minutes", 0.0)

    # 새로 추가된 특수 특징
    user_swear_ratio = features.get("user_swear_msg_ratio", 0.0)
    user_game_ratio = features.get("user_game_msg_ratio", 0.0)
    user_night_game_ratio = features.get("user_night_game_msg_ratio", 0.0)

    # 주제 분석 특징
    topic_daily_life = features.get("topic_daily_life_ratio", 0.0)
    topic_emotion = features.get("topic_emotion_ratio", 0.0)
    topic_planning = features.get("topic_planning_ratio", 0.0)
    topic_development = features.get("topic_development_ratio", 0.0)
    topic_school = features.get("topic_school_ratio", 0.0)
    topic_hobby = features.get("topic_hobby_ratio", 0.0)
    topic_meme = features.get("topic_meme_ratio", 0.0)
    topic_info_request = features.get("topic_info_request_ratio", 0.0)
    topic_economy = features.get("topic_economy_ratio", 0.0)
    topic_romance = features.get("topic_romance_ratio", 0.0)

    # ---- 페르소나 추정 ----
    persona_scores = {
        "developer": topic_development * 1.5 + topic_school + topic_economy,
        "socializer": topic_romance * 1.5 + topic_emotion + topic_daily_life,
        "hobbyist": topic_hobby * 1.2 + topic_meme + user_game_ratio,
        "planner": topic_planning * 2.0,
    }
    # 가장 점수가 높은 페르소나를 선택 (최소 임계값 0.1 이상)
    top_persona = "default"
    max_score = 0.1
    for p, s in persona_scores.items():
        if s > max_score:
            max_score = s
            top_persona = p
    persona = top_persona

    # 페르소나 기반 가중치 설정
    weights = {
        "t_f_swear": 40.0,  # 기본: 욕설 -> T
        "j_p_night": -20.0, # 기본: 야행성 -> P
        "j_p_game": -20.0,  # 기본: 게임 -> P
        "j_p_reply_fast": 10.0, # 기본: 빠른 답장 -> J
    }
    if persona == "developer":
        weights["t_f_swear"] = 50.0  # 개발자는 직설적일 확률 높음
    elif persona == "socializer":
        weights["t_f_swear"] = 20.0  # 친한 사이의 욕설은 T 성향을 덜 반영
    elif persona == "hobbyist":
        weights["j_p_night"] = -30.0 # 취미 활동으로 늦게 잘 가능성
        weights["j_p_game"] = -30.0  # 게임/취미는 P 성향을 더 강하게 반영
    elif persona == "planner":
        weights["j_p_reply_fast"] = 15.0 # 계획적인 사람은 빠른 답장을 더 중요하게 생각

    # ---- E / I ----
    e_score = 50.0

    # 질문/감탄/이모티콘 많이 쓰면 E 쪽
    e_score += (user_question_ratio + user_exclamation_ratio) * 25.0
    e_score += user_emoji_ratio * 30.0

    # 참여자 수 보정 발화량 (평균(1.0)보다 높으면 E 쪽)
    e_score += (talkativeness - 1.0) * 20.0

    # 욕설/게임 얘기 많이 = 보통 친구들이랑 떠드는 톤 → 약간 E 쪽
    e_score += user_swear_ratio * 10.0
    e_score += user_game_ratio * 10.0

    # 1인칭 비율이 너무 높으면 약간 I쪽으로 (조금만 반영)
    e_score -= first_person_ratio * 10.0

    e_score = _clamp(e_score)
    i_score = 100.0 - e_score

    # ---- S / N ----
    # 문장이 길수록, 그리고 밤에 활동/게임할수록 N 쪽으로 약간 가중치
    normalized_len = (avg_sentence_len - 5.0) / (30.0 - 5.0)
    n_score = 50.0 + normalized_len * 25.0  # -25 ~ +25
    n_score += (user_night_ratio - 0.2) * 30.0  # 밤 활동 많으면 N 쪽
    n_score += user_night_game_ratio * 20.0     # 밤에 게임 얘기 자주 → N 쪽 살짝

    n_score = _clamp(n_score)
    s_score = 100.0 - n_score

    # ---- T / F ----
    # 부정 단어 + 욕설 많으면 T 쪽, 감정/이모티콘 많으면 F 쪽
    t_score = 50.0
    t_score += negative_ratio * 80.0
    t_score -= positive_ratio * 40.0
    t_score -= user_emoji_ratio * 20.0
    t_score += user_swear_ratio * weights["t_f_swear"]  # 페르소나 가중치 적용

    t_score = _clamp(t_score)
    f_score = 100.0 - t_score

    # ---- J / P ----
    j_score = 50.0

    # 문장이 길수록 조금 더 J(정리된 표현)
    j_score += avg_sentence_len * 0.8

    # 질문 많이 하면 P 쪽 경향 (열어두는 질문형)
    j_score -= user_question_ratio * 30.0

    # 야행성이 강하면 P쪽으로 (조금)
    j_score += user_night_ratio * weights["j_p_night"] # 페르소나 가중치 적용

    # 답장 속도: 빠를수록 J, 매우 느리면 P
    if avg_reply_minutes > 0:
        if avg_reply_minutes <= 5:
            j_score += weights["j_p_reply_fast"]
        elif avg_reply_minutes >= 60:
            j_score -= 10.0

    # 게임 비율/욕설 비율이 높으면 P쪽(즉흥/자유로운 패턴)으로 약간
    j_score -= user_game_ratio * weights["j_p_game"]
    j_score -= user_swear_ratio * 10.0

    j_score = _clamp(j_score)
    p_score = 100.0 - j_score

    e, i_ = int(round(e_score)), int(round(i_score))
    s, n = int(round(s_score)), int(round(n_score))
    t, f = int(round(t_score)), int(round(f_score))
    j, p = int(round(j_score)), int(round(p_score))

    mbti_type = ""
    mbti_type += "E" if e >= i_ else "I"
    mbti_type += "S" if s >= n else "N"
    mbti_type += "T" if t >= f else "F"
    mbti_type += "J" if j >= p else "P"

    # ---------- 여기서부터 설명(explanation) 생성 ----------
    explanations = {
        "persona": persona, # 페르소나 정보 추가
        "E": [],
        "I": [],
        "S": [],
        "N": [],
        "T": [],
        "F": [],
        "J": [],
        "P": [],
    }

    # E / I 근거
    user_msg_ratio = features.get("user_message_ratio", 0.0)
    if talkativeness > 0:
        if talkativeness >= 1.2:
            explanations["E"].append(
                f"평균보다 약 {talkativeness:.1f}배 더 많이 대화에 참여해, 대화를 주도하는 편입니다."
            )
        elif talkativeness <= 0.8:
            explanations["I"].append(
                f"평균보다 적게 대화에 참여({talkativeness:.1f}배)하여, 주로 듣는 역할을 하는 편입니다."
            )

    if user_question_ratio >= 0.08:
        explanations["E"].append(
            f"질문형 메시지 비율이 {user_question_ratio * 100:.1f}%로 상대에게 자주 말을 겁니다."
        )
    elif user_question_ratio <= 0.02:
        explanations["I"].append(
            f"질문형 메시지 비율이 {user_question_ratio * 100:.1f}%로 질문보다는 반응 위주로 대화합니다."
        )

    if user_emoji_ratio >= 0.02:
        explanations["E"].append(
            "이모티콘/감정 표현이 자주 등장해 분위기를 이끄는 편입니다."
        )

    # S / N 근거
    if avg_sentence_len > 0:
        if avg_sentence_len >= 15:
            explanations["N"].append(
                f"문장 평균 길이가 {avg_sentence_len:.1f} 단어로, 한 번에 상대적으로 긴 메시지를 보내는 편입니다."
            )
        elif avg_sentence_len <= 7:
            explanations["S"].append(
                f"문장 평균 길이가 {avg_sentence_len:.1f} 단어로, 짧고 직관적인 표현을 자주 사용합니다."
            )

    if user_night_ratio >= 0.3:
        explanations["N"].append(
            f"야간(밤/새벽)에 보낸 메시지 비율이 {user_night_ratio * 100:.1f}%로, 늦은 시간대에 활동하는 편입니다."
        )

    if user_game_ratio >= 0.1:
        explanations["S"].append(
            f"게임/현실 활동 관련 대화 비율이 {user_game_ratio * 100:.1f}%로, 구체적인 활동과 상황에 대한 이야기가 많습니다."
        )

    if topic_development > 0.05:
        explanations["N"].append("개발, 코딩 등 추상적이고 논리적인 주제에 대한 대화가 많습니다.")
    if topic_daily_life > 0.1:
        explanations["S"].append("일상, 식사, 날씨 등 현실적이고 구체적인 주제의 대화를 자주 나눕니다.")

    # T / F 근거
    if negative_ratio > 0:
        explanations["T"].append(
            f"부정적인 단어 비율이 {negative_ratio * 100:.2f}%로, 상황을 비판적/현실적으로 보는 표현이 있는 편입니다."
        )
    if positive_ratio > 0:
        explanations["F"].append(
            f"긍정적인 단어 비율이 {positive_ratio * 100:.2f}%로, 좋은 감정을 표현하는 편입니다."
        )
    if user_swear_ratio > 0:
        explanations["T"].append(
            f"욕설/강한 표현이 포함된 메시지가 전체의 {user_swear_ratio * 100:.1f}%입니다."
        )
    if user_emoji_ratio > 0:
        explanations["F"].append(
            f"이모티콘/감정 표현 비율이 {user_emoji_ratio * 100:.2f}%로, 감정을 직접적으로 드러냅니다."
        )
    
    if topic_emotion > 0.03 or topic_romance > 0.03:
        explanations["F"].append("개인적인 감정이나 연애와 같이 관계 중심적인 대화를 나누는 편입니다.")
    if topic_economy > 0.03 or topic_info_request > 0.05:
        explanations["T"].append("경제, 정보 요청 등 객관적이고 사실 기반의 대화를 하는 경향이 있습니다.")

    # J / P 근거
    if avg_reply_minutes > 0:
        if avg_reply_minutes <= 10:
            explanations["J"].append(
                f"평균 답장 시간이 약 {avg_reply_minutes:.1f}분으로 비교적 빠르게 응답하는 편입니다."
            )
        elif avg_reply_minutes >= 60:
            explanations["P"].append(
                f"평균 답장 시간이 약 {avg_reply_minutes:.1f}분으로 꽤 느긋한 편입니다."
            )

    if user_night_ratio >= 0.3:
        explanations["P"].append(
            "야간에 자주 대화를 하는 패턴이 있어, 생활 리듬이 유연한 편일 수 있습니다."
        )
    if user_game_ratio >= 0.1:
        explanations["P"].append(
            f"게임/여가 관련 대화 비율이 {user_game_ratio * 100:.1f}%로, 현재의 재미와 즉흥적인 활동을 즐깁니다."
        )
    
    if topic_planning > 0.05:
        explanations["J"].append("약속, 계획 등 체계적이고 목표 지향적인 대화를 자주 합니다.")
    if topic_hobby > 0.05 or topic_meme > 0.05:
        explanations["P"].append("취미, 밈(meme) 등 즉흥적이고 자유로운 주제의 대화를 즐기는 편입니다.")

    result: Dict[str, Any] = {
        "type": mbti_type,
        "scores": {
            "E": e,
            "I": i_,
            "S": s,
            "N": n,
            "T": t,
            "F": f,
            "J": j,
            "P": p,
        },
        "features": features,
        "explanation": explanations,  # ★ 추가
    }
    return result
