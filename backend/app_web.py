from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Request, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .data_loader.kakao_parser import parse_kakao_txt
from .feature_extractor.features_common import extract_text_features
from .feature_extractor.features_kakao import extract_kakao_features
from .mbti_scorer import score_mbti
from .confidence_engine import compute_confidence
from .llm_reporter import generate_report, generate_persona_overview
from .keyword_engine import generate_label_with_llm  # ★ 추가


BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Real MBTI API", version="0.3.0")

templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "web" / "static")),
    name="static",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def _decode_kakao_bytes(raw_bytes: bytes) -> str:
    """
    카카오톡 내보내기 txt 인코딩 유추 (utf-8 우선, 안 되면 cp949).
    """
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("cp949", errors="ignore")


@app.post("/analyze/kakao")
async def analyze_kakao(
    # 여러 개 파일 업로드
    files: List[UploadFile] = File(...),
    # 단톡방에서의 "내 이름" (카톡 닉네임)
    user_name: str = Form(...),
):
    """
    카카오톡 내보내기 txt 파일들 + 사용자 이름을 입력 받아서:
    - 각 파일을 파싱
    - 모든 메시지를 합쳐서 하나의 타임라인으로 보고
    - user_name과 일치하는 발화자만 "나"로 간주하여 특징 추출
    """
    if not files:
        raise HTTPException(status_code=400, detail="최소 1개 이상의 파일이 필요합니다.")

    user_name = user_name.strip()
    if not user_name:
        raise HTTPException(status_code=400, detail="사용자 이름을 입력해야 합니다.")

    parsed_list: List[Dict[str, Any]] = []

    for f in files:
        raw_bytes = await f.read()
        text = _decode_kakao_bytes(raw_bytes)
        parsed = parse_kakao_txt(text)
        parsed_list.append(parsed)

    # === 여러 파일을 하나로 합치기 ===
    all_messages = []
    total_line_count = 0
    senders_merged: Dict[str, int] = {}

    for parsed in parsed_list:
        msgs = parsed.get("messages", [])
        meta = parsed.get("meta", {})
        all_messages.extend(msgs)
        total_line_count += meta.get("line_count", 0)

        for s, cnt in meta.get("senders", {}).items():
            senders_merged[s] = senders_merged.get(s, 0) + cnt

    # 타임스탬프 순으로 정렬 (파일 여러 개 섞일 수 있으니까)
    all_messages.sort(key=lambda m: m["timestamp"])

    # user_name이 실제로 존재하는지 확인
    user_sender_name = None
    if user_name in senders_merged:
        user_sender_name = user_name
    elif senders_merged:
        # 못 찾으면 예전처럼 가장 많이 말한 사람으로 fallback
        user_sender_name = max(senders_merged, key=senders_merged.get)

    parsed_all = {
        "messages": all_messages,
        "meta": {
            "source": "kakao",
            "line_count": total_line_count,
            "message_count": len(all_messages),
            "senders": senders_merged,
            "user_sender": user_sender_name,
        },
        "raw_text": "\n".join(m["text"] for m in all_messages),
    }

    # 공통 텍스트 특징 (전체 대화 텍스트 기반)
    all_text = parsed_all["raw_text"]
    common_features = extract_text_features(all_text)

    # 카카오톡 전용 특징 (여기서 user_sender = user_name 기반으로 잡힘)
    kakao_features = extract_kakao_features(parsed_all)

     # 공통 + 카톡 특징 합치기
    all_features = {**common_features, **kakao_features}

    mbti_result = score_mbti(all_features)
    confidence = compute_confidence(all_features, source_count=len(files))
    label = generate_label_with_llm(mbti_result, confidence)  # ★ 수식어 생성
        # ★ MBTI 페르소나 개요 생성
    persona_overview = generate_persona_overview(mbti_result)

    report = generate_report(mbti_result, confidence)

    # ★ mbti_result 딕셔너리에 바로 붙여서 프론트로 넘김
    mbti_result["persona_overview"] = persona_overview

    return {
        "mbti": mbti_result,
        "confidence": confidence,
        "label": label, 
        "report": report,
        "meta": {
            "file_count": len(files),
            "user_name_input": user_name,
            "user_sender_resolved": kakao_features.get("user_sender_name"),
        },
    }

