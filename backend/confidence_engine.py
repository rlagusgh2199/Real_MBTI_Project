from __future__ import annotations

from typing import Dict, Any


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def compute_confidence(features: Dict[str, Any], source_count: int = 1) -> Dict[str, Any]:
    """
    규칙 기반으로 신뢰도 점수를 계산한다.

    - word_count: "분석 대상 사용자가 쓴 단어 수"를 기준으로 데이터 양 점수(data_amount_score)를 매긴다.
    - source_count: 업로드한 파일 개수 (카톡 방/로그 수)에 따라 소스 다양성 점수(source_diversity_score)를 매긴다.
    - room_word_count: 방 전체 단어 수(참고용, 점수에는 직접 사용하지 않음).
    """

    # 내가 쓴 단어 수 (features_kakao에서 word_count를 user_word_count로 덮어씀)
    word_count = int(features.get("word_count", 0) or 0)
    # 방 전체 단어 수(있으면 사용, 없으면 내 단어 수와 동일하게 둠)
    room_word_count = int(features.get("room_word_count", word_count) or 0)

    # ◾ 데이터 양 점수: "내가 쓴 단어 수" 기준으로 대략적인 구간 나누기
    #   - <  200 단어  : 20
    #   - <  800 단어  : 40
    #   - < 2000 단어  : 60
    #   - < 5000 단어  : 80
    #   - 그 이상      : 95
    if word_count < 200:
        data_amount_score = 20
    elif word_count < 800:
        data_amount_score = 40
    elif word_count < 2000:
        data_amount_score = 60
    elif word_count < 5000:
        data_amount_score = 80
    else:
        data_amount_score = 95

    # ◾ 소스 다양성 점수: 파일이 많을수록 약간 보너스
    #   (1개: 40, 2개: 60, 3개: 75, 4개 이상: 90 정도 느낌)
    if source_count <= 1:
        source_diversity_score = 40
    elif source_count == 2:
        source_diversity_score = 60
    elif source_count == 3:
        source_diversity_score = 75
    else:
        source_diversity_score = 90

    # 최종 신뢰도 점수: 데이터 양 70%, 소스 다양성 30%
    score_float = data_amount_score * 0.7 + source_diversity_score * 0.3
    score = int(round(_clamp(score_float)))

    if score < 40:
        level = "low"
    elif score < 70:
        level = "medium"
    else:
        level = "high"

    return {
        "score": score,
        "level": level,
        "data_amount_score": int(data_amount_score),
        "source_diversity_score": int(source_diversity_score),

        # ✅ 이제 이 값은 "내가 쓴 단어 수"
        "word_count": word_count,

        # 참고용: 방 전체 단어 수
        "room_word_count": room_word_count,

        "source_count": int(source_count),
    }
