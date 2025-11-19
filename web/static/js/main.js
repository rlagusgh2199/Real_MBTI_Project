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

function renderConfidenceCompact(c, wordCount) {
  const score = c.score ?? 0;
  const level = c.level || "unknown";
  const levelLabel =
    level === "high"
      ? "높음"
      : level === "medium"
      ? "보통"
      : level === "low"
      ? "낮음"
      : level;

  return `
    <div class="confidence-chip-row">
      <div class="confidence-chip">
        <span>신뢰도</span>
        <strong>${score} / 100 (${levelLabel})</strong>
      </div>
      <div class="confidence-chip">
        <span>단어 수</span>
        <strong>${wordCount}</strong>
      </div>
    </div>
    <div class="confidence-bar-wrapper">
      <div class="confidence-bar">
        <div class="confidence-bar-fill" style="width:${Math.min(
          100,
          score
        )}%;"></div>
      </div>
    </div>
  `;
}

function renderConfidenceDetail(c, dataAmount, srcDiversity, wordCount) {
  const compact = renderConfidenceCompact(c, wordCount);
  return `
    <h3>신뢰도(Confidence)</h3>
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

  const axisDetails = mbti.axis_details || {};
  const ambiguousAxes = mbti.ambiguous_axes || [];
  const persona = mbti.persona || null;

  // 축별 설명 리스트
  const exE = explanations.E || [];
  const exI = explanations.I || [];
  const exS = explanations.S || [];
  const exN = explanations.N || [];
  const exT = explanations.T || [];
  const exF = explanations.F || [];
  const exJ = explanations.J || [];
  const exP = explanations.P || [];

  // 시간대, 상위 단어/이모티콘, 샘플 메시지
  const mostActive = features.user_most_active_period || null;
  const topWords = features.user_top_words || [];
  const topEmojis = features.user_top_emojis || [];
  const nightSamples = features.sample_night_messages || [];
  const gameSamples = features.sample_game_messages || [];

  const mostActiveKo = (function () {
    switch (mostActive) {
      case "night":
        return "새벽/밤 (0~6시)";
      case "morning":
        return "아침 (6~12시)";
      case "afternoon":
        return "낮/오후 (12~18시)";
      case "evening":
        return "저녁 (18~24시)";
      default:
        return null;
    }
  })();

  const topWordsHtml = topWords.length
    ? topWords.map((w) => `<span class="chip">${escapeHtml(w)}</span>`).join(" ")
    : '<span class="hint">자주 쓰는 단어가 뚜렷하게 나타나지 않았습니다.</span>';

  const topEmojisHtml = topEmojis.length
    ? topEmojis
        .map((e) => `<span class="chip chip-emoji">${escapeHtml(e)}</span>`)
        .join(" ")
    : '<span class="hint">자주 쓰는 이모티콘이 뚜렷하게 나타나지 않았습니다.</span>';

  const nightSamplesHtml = nightSamples.length
    ? nightSamples.map((t) => `<li>${escapeHtml(t)}</li>`).join("")
    : "";

  const gameSamplesHtml = gameSamples.length
    ? gameSamples.map((t) => `<li>${escapeHtml(t)}</li>`).join("")
    : "";

  container.innerHTML = `
    <h3>행동 패턴 & 근거</h3>

    <div class="behavior-section">
      <h4>0) MBTI 판정 요약</h4>
      <ul class="meta-list">
        ${
          persona
            ? `<li><span>주요 페르소나</span><strong>${escapeHtml(persona)}</strong></li>`
            : ""
        }
        <li>
          <span>애매한 축</span>
          <strong>
            ${
              ambiguousAxes.length
                ? ambiguousAxes.join(", ")
                : "뚜렷하게 우세한 축이 많습니다."
            }
          </strong>
        </li>
      </ul>
      <p class="hint">
        애매한 축은 두 성향 점수 차이가 작아, 대화 데이터만으로는 한쪽을 강하게 단정하기 어려운 경우입니다.
      </p>
    </div>

    <div class="behavior-section">
      <h4>1) MBTI 축별 근거</h4>
      <div class="axis-grid">
        <div>
          <h5>E (외향)</h5>
          ${
            exE.length
              ? `<ul>${exE
                  .map((x) => `<li>${escapeHtml(x)}</li>`)
                  .join("")}</ul>`
              : "<p class='hint'>뚜렷한 외향 패턴 근거가 적습니다.</p>"
          }
        </div>
        <div>
          <h5>I (내향)</h5>
          ${
            exI.length
              ? `<ul>${exI
                  .map((x) => `<li>${escapeHtml(x)}</li>`)
                  .join("")}</ul>`
              : "<p class='hint'>뚜렷한 내향 패턴 근거가 적습니다.</p>"
          }
        </div>
        <div>
          <h5>S (감각)</h5>
          ${
            exS.length
              ? `<ul>${exS
                  .map((x) => `<li>${escapeHtml(x)}</li>`)
                  .join("")}</ul>`
              : "<p class='hint'>감각형으로 해석할 만한 근거가 많지 않습니다.</p>"
          }
        </div>
        <div>
          <h5>N (직관)</h5>
          ${
            exN.length
              ? `<ul>${exN
                  .map((x) => `<li>${escapeHtml(x)}</li>`)
                  .join("")}</ul>`
              : "<p class='hint'>직관형으로 해석할 만한 근거가 많지 않습니다.</p>"
          }
        </div>
        <div>
          <h5>T (사고)</h5>
          ${
            exT.length
              ? `<ul>${exT
                  .map((x) => `<li>${escapeHtml(x)}</li>`)
                  .join("")}</ul>`
              : "<p class='hint'>사고형으로 해석할 만한 근거가 많지 않습니다.</p>"
          }
        </div>
        <div>
          <h5>F (감정)</h5>
          ${
            exF.length
              ? `<ul>${exF
                  .map((x) => `<li>${escapeHtml(x)}</li>`)
                  .join("")}</ul>`
              : "<p class='hint'>감정형으로 해석할 만한 근거가 많지 않습니다.</p>"
          }
        </div>
        <div>
          <h5>J (판단)</h5>
          ${
            exJ.length
              ? `<ul>${exJ
                  .map((x) => `<li>${escapeHtml(x)}</li>`)
                  .join("")}</ul>`
              : "<p class='hint'>판단형으로 해석할 만한 근거가 많지 않습니다.</p>"
          }
        </div>
        <div>
          <h5>P (인식)</h5>
          ${
            exP.length
              ? `<ul>${exP
                  .map((x) => `<li>${escapeHtml(x)}</li>`)
                  .join("")}</ul>`
              : "<p class='hint'>인식형으로 해석할 만한 근거가 많지 않습니다.</p>"
          }
        </div>
      </div>
    </div>

    <div class="behavior-section">
      <h4>2) 대화 습관 요약</h4>
      <ul>
        ${
          mostActiveKo
            ? `<li>가장 많이 대화하는 시간대: <strong>${mostActiveKo}</strong></li>`
            : `<li>가장 활발한 시간대 정보를 뽑을 수 없었습니다.</li>`
        }
      </ul>

      <h5>자주 쓰는 단어</h5>
      <div class="chip-row">
        ${topWordsHtml}
      </div>

      <h5>자주 쓰는 이모티콘/반응</h5>
      <div class="chip-row">
        ${topEmojisHtml}
      </div>
    </div>

    ${
      nightSamplesHtml || gameSamplesHtml
        ? `
    <div class="behavior-section">
      <h4>3) 실제 대화 예시</h4>

      ${
        nightSamplesHtml
          ? `
      <h5>야간 대화 예시</h5>
      <ul class="sample-list">
        ${nightSamplesHtml}
      </ul>
      `
          : ""
      }

      ${
        gameSamplesHtml
          ? `
      <h5>게임/맴 관련 대화 예시</h5>
      <ul class="sample-list">
        ${gameSamplesHtml}
      </ul>
      `
          : ""
      }
    </div>
    `
        : ""
    }
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
    DOM.overviewMbti.innerHTML = `
      <h4>MBTI 유형</h4>
      ${renderMbtiSummary(mbti.type, scores)}
    `;
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
    DOM.overviewConf.innerHTML = `
      <h4>신뢰도 요약</h4>
      ${renderConfidenceCompact(c, wordCount)}
    `;
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

  const htmlReport = data.report
    .replace(/\n/g, "<br />")
    .replace(/ {2}/g, "&nbsp;&nbsp;");

  DOM.resultReport.innerHTML = `
    <h3>AI 리포트</h3>
    <div class="report-box">${htmlReport}</div>
  `;
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
}

function updateUIWithAnalysis(data) {
  updateLabelSection(data);
  updateMbtiSection(data);
  updateConfidenceSection(data);
  updateMetaSection(data);
  updateReportSection(data);
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


// ======================================================
// 6. DOMContentLoaded 진입점
// ======================================================

document.addEventListener("DOMContentLoaded", () => {
  cacheDom();
  setupEventListeners();
});
