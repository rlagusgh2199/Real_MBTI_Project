from __future__ import annotations

from typing import Dict, Any, List
import re


def _split_sentences(text: str) -> List[str]:
    raw_sentences = re.split(r"[\.!\?\n]+", text)
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    return sentences


def _tokenize(text: str) -> List[str]:
    cleaned = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", text)
    tokens = cleaned.split()
    return tokens


def extract_text_features(text: str) -> Dict[str, Any]:
    """
    순수 텍스트에서 공통적으로 쓸 수 있는 언어 패턴 특징 추출.
    (카톡, SNS, 유튜브 제목 합쳐서 텍스트로 만들 때 공용으로 사용 가능)
    """
    original_text = text
    text = text.strip()

    sentences = _split_sentences(text)
    tokens = _tokenize(text)

    word_count = len(tokens)
    sentence_count = len(sentences)
    avg_sentence_len = word_count / sentence_count if sentence_count > 0 else 0.0

    first_person_words = [
        "나", "내가", "난", "나는", "저", "제가",
        "i", "me", "my", "mine",
    ]
    first_person_count = sum(
        1 for t in tokens if any(fp == t or fp in t for fp in first_person_words)
    )

    question_mark_count = original_text.count("?")
    exclamation_mark_count = original_text.count("!")

    positive_words = [
        "좋다", "좋아", "행복", "재밌", "재미있", "사랑", "기쁘", "즐겁", "설렌",
        "happy", "love", "good", "great", "awesome", "fun",
    ]
    negative_words = [
        "싫", "짜증", "화나", "불안", "우울", "힘들", "어렵", "슬프", "미워",
        "sad", "angry", "anxious", "tired", "depress",
    ]

    pos_count = sum(1 for t in tokens if any(p in t for p in positive_words))
    neg_count = sum(1 for t in tokens if any(n in t for n in negative_words))

    def ratio(count: int, base: int) -> float:
        if base <= 0:
            return 0.0
        return count / base

    first_person_ratio = ratio(first_person_count, word_count)
    question_ratio = ratio(question_mark_count, max(1, sentence_count))
    exclamation_ratio = ratio(exclamation_mark_count, max(1, sentence_count))
    positive_ratio = ratio(pos_count, max(1, word_count))
    negative_ratio = ratio(neg_count, max(1, word_count))

    features: Dict[str, Any] = {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_len": avg_sentence_len,
        "first_person_ratio": first_person_ratio,
        "question_ratio": question_ratio,
        "exclamation_ratio": exclamation_ratio,
        "positive_ratio": positive_ratio,
        "negative_ratio": negative_ratio,
    }

    return features


# 옛 이름 유지 (혹시 CLI 코드 등에서 쓰고 있을 경우를 위해)
def extract_features(text: str) -> Dict[str, Any]:
    return extract_text_features(text)
