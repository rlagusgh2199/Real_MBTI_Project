// ======================================================
// 0. GLOBAL DOM & STATE
// ======================================================

const DOM = {
  userNameInput: null,
  fileInput: null,
  statusEl: null,

  resultLabel: null,
  resultMbti: null,
  resultBehavior: null,
  resultConf: null,
  resultMeta: null,
  resultReport: null,

  overviewMbti: null,
  overviewConf: null,

  analyzeBtn: null,
};

const STATE = {
  fileDropEl: null,
  fileDropTextEl: null,
  defaultFileText: "",
};


// ======================================================
// 1. API MODULE (서버 통신 전용)
// ======================================================

async function requestAnalyzeKakao(formData) {
  const res = await fetch("/analyze/kakao", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`서버 오류 (${res.status}): ${text}`);
  }
  return res.json();
}


// ======================================================
// 2. RENDER MODULE (UI 렌더링 전용)
// ======================================================

function renderMbtiSummary(type, scores) {
  const s = scores || {};
  const pairs = [
    ["E", "I"],
    ["S", "N"],
    ["T", "F"],
    ["J", "P"],
  ];

  const axisRows = pairs
    .map(([a, b]) => {
      const va = s[a] ?? 50;
      const vb = s[b] ?? 50;
      const total = va + vb || 1;
      const leftRate = Math.round((va / total) * 100);
      const rightRate = 100 - leftRate;
      return `
      <div class="axis-row">
        <span class="axis-label">${a}</span>
        <div class="axis-bar">
          <div class="axis-bar-left" style="width:${leftRate}%"></div>
          <div class="axis-bar-right" style="width:${rightRate}%"></div>
        </div>
        <span class="axis-label">${b}</span>
      </div>
    `;
    })
    .join("");

  return `
    <div class="mbti-card">
      <div class="mbti-badge">${escapeHtml(type || "????")}</div>
      <div class="axis-rows">
        ${axisRows}
      </div>
    </div>
  `;
}

// 🔹 신뢰도 컴팩트 카드 (개요 + 상세 공용)
function renderConfidenceCompact(confidence, wordCount, dataAmount, srcDiversity) {
  if (!confidence) {
    return `
      <div class="conf-card">
        <p class="conf-empty">신뢰도 정보를 계산할 수 없어요.</p>
      </div>
    `;
  }

  const score = confidence.score ?? 0;
  const levelLabel = confidence.level_label || confidence.level || "";
  const wordCountText = (wordCount ?? confidence.word_count ?? 0).toLocaleString();

  // 🔸 세부 점수: 함수 인자로 넘어온 값이 있으면 그걸 우선 사용
  const volumeScore =
    dataAmount ??
    confidence.volume_score ??
    confidence.data_volume_score ??
    confidence.data_amount_score ??
    confidence.amount_score ??
    "-";

  const diversityScore =
    srcDiversity ??
    confidence.source_score ??
    confidence.source_diversity_score ??
    confidence.diversity_score ??
    "-";

  return `
    <div class="conf-card">
      <div class="conf-header-row">
        <!-- 🔥 여기 있던 "신뢰도" 텍스트는 제거 -->
        <div class="conf-pill-row">
          <span class="conf-pill-main">
            신뢰도 ${score} / 100${levelLabel ? ` (${levelLabel})` : ""}
          </span>
          <span class="conf-pill-sub">단어 수 ${wordCountText}</span>
        </div>
      </div>

      <div class="conf-bar-wrap">
        <div class="conf-bar-track">
          <div class="conf-bar-fill" style="width: ${Math.max(
            5,
            Math.min(score, 100)
          )}%;"></div>
        </div>
      </div>

      <dl class="conf-metrics">
        <div class="conf-metric-row">
          <dt class="conf-metric-label">데이터 양 점수</dt>
          <dd class="conf-metric-value">${volumeScore}</dd>
        </div>
        <div class="conf-metric-row">
          <dt class="conf-metric-label">소스 다양성 점수</dt>
          <dd class="conf-metric-value">${diversityScore}</dd>
        </div>
      </dl>
    </div>
  `;
}

// 🔹 신뢰도 “상세” 카드 (아래 아코디언용)
function renderConfidenceDetail(c, dataAmount, srcDiversity, wordCount) {
  // 위의 compact에도 dataAmount/srcDiversity를 같이 넘겨서
  // 카드 안/아래 리스트 모두 같은 값이 보이게 함.
  const compact = renderConfidenceCompact(c, wordCount, dataAmount, srcDiversity);

  return `
    ${compact}
    <ul class="meta-list">
      <li><span>데이터 양 점수</span><strong>${dataAmount}</strong></li>
      <li><span>소스 다양성 점수</span><strong>${srcDiversity}</strong></li>
    </ul>
  `;
}


function renderBehaviorSection(container, mbti) {
  const explanations = mbti.explanation || {};
  const features = mbti.features || {};
  const ambiguousAxes = mbti.ambiguous_axes || [];

  // 축별 설명 배열 헬퍼
  const axisHtml = (code, label, arr) => {
    const items = arr || [];
    if (!items.length) {
      return `
        <div class="behavior-axis-card">
          <p class="behavior-axis-title">${code} <span>(${label})</span></p>
          <p class="hint">뚜렷하게 설명할 근거가 많지 않습니다.</p>
        </div>
      `;
    }
    return `
      <div class="behavior-axis-card">
        <p class="behavior-axis-title">${code} <span>(${label})</span></p>
        <ul>
          ${items.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}
        </ul>
      </div>
    `;
  };

  // 시간대 한글 변환
  const mostActive = features.user_most_active_period || null;
  const mostActiveKo =
    mostActive === "morning"
      ? "아침 (6~12시)"
      : mostActive === "afternoon"
      ? "낮/오후 (12~18시)"
      : mostActive === "evening"
      ? "저녁 (18~24시)"
      : mostActive === "night"
      ? "새벽/밤 (0~6시)"
      : "특정 시간대가 두드러지지 않습니다.";

  // 자주 쓰는 단어 / 이모티콘 칩
  const topWords = features.user_top_words || [];
  const topEmojis = features.user_top_emojis || [];

  const topWordsHtml = topWords.length
    ? topWords
        .map((w) => `<span class="behavior-chip">${escapeHtml(w)}</span>`)
        .join("")
    : `<span class="hint">뚜렷하게 반복되는 단어가 없습니다.</span>`;

  const topEmojisHtml = topEmojis.length
    ? topEmojis
        .map((e) => `<span class="behavior-chip">${escapeHtml(e)}</span>`)
        .join("")
    : `<span class="hint">자주 쓰는 이모티콘이 뚜렷하게 나타나지 않았습니다.</span>`;

  // 실제 대화 예시 (이모티콘만 있는 줄은 최대한 제외)
  const rawSamples = features.sample_common_messages || [];
  const textSamples = rawSamples.filter((s) =>
    /[\p{L}\p{N}]/u.test(s || "")
  );
  const samples = textSamples.length ? textSamples : rawSamples;
  const samplesHtml = samples.length
    ? `
      <ul class="behavior-list">
        ${samples.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}
      </ul>
    `
    : `<p class="hint">표시할 만한 예시 문장이 충분하지 않습니다.</p>`;

  // 0) 애매한 축 요약
  const ambiguousHtml =
    ambiguousAxes.length > 0
      ? `<span class="behavior-chip behavior-chip-strong">${ambiguousAxes.join(
          ", "
        )}</span>`
      : `<span class="hint">이번 분석에서는 대부분의 축이 한쪽으로 뚜렷하게 기울어져 있습니다.</span>`;

  container.innerHTML = `
    <div class="behavior-layout">

      <!-- 0) MBTI 판정 요약 -->
      <section class="behavior-block">
        <div class="behavior-block-header">
          <div class="behavior-block-index">0</div>
          <div>
            <div class="behavior-block-title">MBTI 판정 요약</div>
            <p class="behavior-block-desc">
              애매한 축과 같이, 대화 데이터만으로는 한쪽을 강하게 단정하기 어려운 부분을 먼저 보여줍니다.
            </p>
          </div>
        </div>
        <p style="margin-top:6px; font-size:0.83rem;">
          <strong>애매한 축</strong>
        </p>
        <div class="behavior-chip-row">
          ${ambiguousHtml}
        </div>
      </section>

      <!-- 1) MBTI 축별 근거 -->
      <section class="behavior-block">
        <div class="behavior-block-header">
          <div class="behavior-block-index">1</div>
          <div>
            <div class="behavior-block-title">MBTI 축별 근거</div>
            <p class="behavior-block-desc">
              각 축(E/I, S/N, T/F, J/P)에 대해 카카오톡 대화에서 포착된 특징을 정리했습니다.
            </p>
          </div>
        </div>

        <div class="behavior-axis-grid">
          ${axisHtml("E", "외향", explanations.E || [])}
          ${axisHtml("I", "내향", explanations.I || [])}
          ${axisHtml("S", "감각", explanations.S || [])}
          ${axisHtml("N", "직관", explanations.N || [])}
          ${axisHtml("T", "사고", explanations.T || [])}
          ${axisHtml("F", "감정", explanations.F || [])}
          ${axisHtml("J", "판단", explanations.J || [])}
          ${axisHtml("P", "인식", explanations.P || [])}
        </div>
      </section>

      <!-- 2) 대화 습관 요약 -->
      <section class="behavior-block">
        <div class="behavior-block-header">
          <div class="behavior-block-index">2</div>
          <div>
            <div class="behavior-block-title">대화 습관 요약</div>
          </div>
        </div>

        <p><strong>가장 많이 대화하는 시간대</strong><br />${mostActiveKo}</p>

        <p style="margin-top:10px;"><strong>자주 쓰는 단어</strong></p>
        <div class="behavior-chip-row">
          ${topWordsHtml}
        </div>

        <p style="margin-top:10px;"><strong>자주 쓰는 이모티콘 / 반응</strong></p>
        <div class="behavior-chip-row">
          ${topEmojisHtml}
        </div>
      </section>

      <!-- 3) 실제 대화 예시 -->
      <section class="behavior-block">
        <div class="behavior-block-header">
          <div class="behavior-block-index">3</div>
          <div>
            <div class="behavior-block-title">실제 대화 예시</div>
          </div>
        </div>

        ${samplesHtml}
      </section>

    </div>
  `;
}



function updateLabelSection(data) {
  const el = DOM.resultLabel;
  if (!el || !data.label) return;

  let labelText = "";
  let keyword = "";

  if (typeof data.label === "string") {
    labelText = data.label;
  } else if (typeof data.label === "object") {
    labelText = data.label.label || "";
    keyword = data.label.keyword || "";
  }

  if (!labelText) return;

  el.innerHTML = `
    <p class="label-caption">나만의 한 줄 요약</p>
    <p class="label-main">${escapeHtml(labelText)}</p>
    ${
      keyword
        ? `<p class="label-sub"><span class="keyword-pill">키워드: ${escapeHtml(
            keyword
          )}</span></p>`
        : ""
    }
  `;
}

function updateMbtiSection(data) {
  if (!data.mbti) return;
  const mbti = data.mbti;
  const scores = mbti.scores || {};

  if (DOM.resultMbti) {
    DOM.resultMbti.innerHTML = renderMbtiSummary(mbti.type, scores);
  }

  if (DOM.overviewMbti) {
    // 바깥 제목/박스 없이 MBTI 카드만 넣기
    DOM.overviewMbti.innerHTML = renderMbtiSummary(mbti.type, scores);
  }


  if (DOM.resultBehavior) {
    renderBehaviorSection(DOM.resultBehavior, mbti);
  }
}

function updateConfidenceSection(data) {
  if (!data.confidence) return;
  const c = data.confidence;

  const dataAmount =
    typeof c.data_amount_score === "number" ? c.data_amount_score : "-";
  const srcDiversity =
    typeof c.source_diversity_score === "number"
      ? c.source_diversity_score
      : "-";
  const wordCount =
    typeof c.word_count === "number" ? c.word_count : 0;

  if (DOM.resultConf) {
    DOM.resultConf.innerHTML = renderConfidenceDetail(
      c,
      dataAmount,
      srcDiversity,
      wordCount
    );
  }

  if (DOM.overviewConf) {
    // 개요에서도 데이터 양/소스 다양성 점수를 같이 전달
    DOM.overviewConf.innerHTML = renderConfidenceCompact(
      c,
      wordCount,
      dataAmount,
      srcDiversity
    );
  }

}

function updateMetaSection(data) {
  if (!data.meta || !DOM.resultMeta) return;

  const m = data.meta;
  const resolved = m.user_sender_resolved || "(감지 실패)";

  DOM.resultMeta.innerHTML = `
    <h3>분석 메타 정보</h3>
    <ul class="meta-list">
      <li><span>업로드한 파일 수</span><strong>${m.file_count}</strong></li>
      <li><span>입력한 내 이름</span><strong>${escapeHtml(
        m.user_name_input || ""
      )}</strong></li>
      <li><span>실제로 분석에 사용된 이름(대화 내 발화자)</span><strong>${escapeHtml(
        resolved
      )}</strong></li>
    </ul>
    <p class="hint">
      만약 "실제로 분석에 사용된 이름"이 내가 아닌 다른 사람으로 보인다면,
      카톡 내보내기 파일에서 닉네임이 정확히 일치하는지 다시 확인해주세요.
    </p>
  `;
}

function updateReportSection(data) {
  if (!data.report || !DOM.resultReport) return;

  const raw = data.report;

  // AI 리포트의 섹션 구분을 감지하여 자동 분리
  const lines = raw.split("\n").map((t) => t.trim());

  let html = "";
  let currentSection = "";

  const pushTitle = (title) => {
    html += `<div class="report-subtitle">${escapeHtml(title)}</div>`;
  };

  lines.forEach((line) => {
    if (!line) return;

    // === 섹션 제목 ===
    if (/^\d+\./.test(line)) {
      pushTitle(line);
      return;
    }

    // 글 머리 기호
    if (line.startsWith("•")) {
      html += `<ul class="report-bullet"><li>${escapeHtml(
        line.replace("•", "").trim()
      )}</li></ul>`;
      return;
    }

    // 일반 문단
    html += `<p>${escapeHtml(line)}</p>`;
  });

  DOM.resultReport.innerHTML = `
    <div class="report-block">
      <div class="report-title">📘 AI 리포트</div>
      ${html}
    </div>
  `;

  // 아코디언 리사이즈 적용
  const body = document.getElementById("accordion-report");
  if (body) {
    const item = body.closest(".accordion-item");
    if (item && item.classList.contains("is-open")) {
      body.style.maxHeight = body.scrollHeight + "px";
    }
  }
}



function resetResultUI() {
  if (DOM.resultLabel) DOM.resultLabel.innerHTML = "";
  if (DOM.resultMbti) DOM.resultMbti.innerHTML = "";
  if (DOM.resultBehavior) DOM.resultBehavior.innerHTML = "";
  if (DOM.resultConf) DOM.resultConf.innerHTML = "";
  if (DOM.resultMeta) DOM.resultMeta.innerHTML = "";
  if (DOM.resultReport) DOM.resultReport.innerHTML = "";
  if (DOM.overviewMbti) DOM.overviewMbti.innerHTML = "";
  if (DOM.overviewConf) DOM.overviewConf.innerHTML = "";
  if (DOM.overviewPersona) DOM.overviewPersona.innerHTML = "";

}

function updateUIWithAnalysis(data) {
  updateLabelSection(data);
  updateMbtiSection(data);
  updateConfidenceSection(data);
  updateMetaSection(data);
  updateReportSection(data);
  updatePersonaOverview(data);
}


// ======================================================
// 3. UTIL FUNCTIONS
// ======================================================

function escapeHtml(str) {
  if (typeof str !== "string") return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function setStatus(el, text, mode) {
  if (!el) return;

  if (!mode) {
    el.textContent = "";
    el.className = "status-pill status-hidden";
    return;
  }

  el.textContent = text;
  el.className = "status-pill";
  el.classList.remove("status-hidden");

  if (mode === "loading") {
    el.classList.add("status-loading");
  } else if (mode === "error") {
    el.classList.add("status-error");
  } else if (mode === "success") {
    el.classList.add("status-success");
  }
}

function openAccordion(sectionName) {
  const header = document.querySelector(
    `.accordion-header[data-target="${sectionName}"]`
  );
  if (!header) return;

  const item = header.closest(".accordion-item");
  const body = document.getElementById(`accordion-${sectionName}`);
  if (!item || !body) return;

  item.classList.add("is-open");
  body.style.maxHeight = body.scrollHeight + "px";
}

function toggleAccordion(header) {
  const target = header.dataset.target;
  const item = header.closest(".accordion-item");
  const body = document.getElementById(`accordion-${target}`);

  if (!item || !body) return;

  const isOpen = item.classList.contains("is-open");

  if (isOpen) {
    item.classList.remove("is-open");
    body.style.maxHeight = null;
  } else {
    item.classList.add("is-open");
    body.style.maxHeight = body.scrollHeight + "px";
  }
}


// ======================================================
// 4. BUSINESS LOGIC (검증, FormData, 분석 흐름)
// ======================================================

function validateInput() {
  const userName = DOM.userNameInput
    ? DOM.userNameInput.value.trim()
    : "";
  const files = DOM.fileInput ? DOM.fileInput.files : null;

  if (!userName) {
    return {
      ok: false,
      message: "먼저 내 카카오톡 이름을 입력해주세요.",
    };
  }

  if (!files || files.length === 0) {
    return {
      ok: false,
      message: "최소 1개 이상의 카카오톡 내보내기 파일을 선택해주세요.",
    };
  }

  return { ok: true, message: "", userName, files };
}

function buildFormData(userName, files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("user_name", userName);
  return formData;
}

async function analyze() {
  if (!DOM.statusEl) return;

  resetResultUI();

  const { ok, message, userName, files } = validateInput();
  if (!ok) {
    setStatus(DOM.statusEl, message, "error");
    return;
  }

  setStatus(DOM.statusEl, "카카오톡 대화를 분석 중입니다...", "loading");

  const formData = buildFormData(userName, files);

try {
    const data = await requestAnalyzeKakao(formData);

    setStatus(
      DOM.statusEl,
      "분석이 완료되었습니다. 결과를 확인해보세요 🙌",
      "success"
    );

    // ✅ 분석 결과 섹션 표시
    const resultsSection = document.getElementById("results-section");
    if (resultsSection) {
      resultsSection.removeAttribute("hidden");
      // 선택: 자동 스크롤
      // resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    updateUIWithAnalysis(data);
    openAccordion("overview");

  } catch (err) {
      console.error(err);
      setStatus(
        DOM.statusEl,
        `분석 중 오류가 발생했습니다: ${err.message}`,
        "error"
      );
  }

}


// ======================================================
// 5. INIT (DOM 캐싱, 이벤트 바인딩, 아코디언 초기화)
// ======================================================

function cacheDom() {
  DOM.userNameInput = document.getElementById("userName");
  DOM.fileInput = document.getElementById("fileInput");
  DOM.statusEl = document.getElementById("status");

  DOM.resultLabel = document.getElementById("result-label");
  DOM.resultMbti = document.getElementById("result-mbti");
  DOM.resultBehavior = document.getElementById("result-behavior");
  DOM.resultConf = document.getElementById("result-confidence");
  DOM.resultMeta = document.getElementById("result-meta");
  DOM.resultReport = document.getElementById("result-report");

  DOM.overviewMbti = document.getElementById("overview-mbti");
  DOM.overviewConf = document.getElementById("overview-confidence");
  DOM.overviewPersona = document.getElementById("overview-persona");


  DOM.analyzeBtn = document.getElementById("analyzeBtn");
}

function setupFileInputUI() {
  if (!DOM.fileInput) return;

  const fileDrop = DOM.fileInput.closest(".file-drop");
  const fileText = fileDrop ? fileDrop.querySelector(".file-drop-text") : null;

  STATE.fileDropEl = fileDrop;
  STATE.fileDropTextEl = fileText;
  STATE.defaultFileText = fileText ? fileText.innerHTML : "";

  if (!fileDrop || !fileText) return;

  DOM.fileInput.addEventListener("change", () => {
    const files = DOM.fileInput.files;

    if (!files || files.length === 0) {
      fileDrop.classList.remove("has-files");
      fileText.innerHTML = STATE.defaultFileText;
      return;
    }

    fileDrop.classList.add("has-files");

    if (files.length === 1) {
      const name = files[0].name;
      fileText.innerHTML = `
        선택된 파일 1개<br />
        <span class="file-highlight">${escapeHtml(name)}</span>
      `;
    } else {
      const first = files[0].name;
      const rest = files.length - 1;
      fileText.innerHTML = `
        선택된 파일 ${files.length}개<br />
        <span class="file-highlight">${escapeHtml(first)} 외 ${rest}개</span>
      `;
    }
  });
}

function setupAccordion() {
  // 헤더 클릭 이벤트
  document.querySelectorAll(".accordion-header").forEach((header) => {
    header.addEventListener("click", () => {
      toggleAccordion(header);
    });
  });

  // 기본으로 열려 있는(is-open) 아코디언의 max-height 세팅
  document.querySelectorAll(".accordion-item.is-open").forEach((item) => {
    const header = item.querySelector(".accordion-header");
    if (!header) return;
    const target = header.dataset.target;
    const body = document.getElementById(`accordion-${target}`);
    if (!body) return;
    body.style.maxHeight = body.scrollHeight + "px";
  });
}

function setupEventListeners() {
  if (DOM.analyzeBtn) {
    DOM.analyzeBtn.addEventListener("click", (e) => {
      e.preventDefault();
      analyze();
    });
  }

  setupFileInputUI();
  setupAccordion();
}

function updatePersonaOverview(data) {
  if (!DOM.overviewPersona) return;
  const mbti = data.mbti;
  if (!mbti || !mbti.persona_overview) return;

  const text = mbti.persona_overview;

  // 줄바꿈 기준 문단 처리
  const paragraphs = text
    .split("\n")
    .map((p) => p.trim())
    .filter((p) => p.length)
    .map((p) => `<p>${escapeHtml(p)}</p>`)
    .join("");

  DOM.overviewPersona.innerHTML = `
    <div class="persona-card">
      <div class="persona-label">MBTI PERSONA</div>
      <div class="persona-mbti">${mbti.type} 요약</div>
      <div class="persona-body">
        ${paragraphs}
      </div>
    </div>
  `;
}



// ======================================================
// 6. DOMContentLoaded 진입점
// ======================================================

document.addEventListener("DOMContentLoaded", () => {
  cacheDom();
  setupEventListeners();
});
