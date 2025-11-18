async function analyze() {
  const userNameInput = document.getElementById("userName");
  const fileInput = document.getElementById("fileInput");
  const statusEl = document.getElementById("status");

  const resultLabel = document.getElementById("result-label");
  const resultMbti = document.getElementById("result-mbti");
  const resultBehavior = document.getElementById("result-behavior");
  const resultConf = document.getElementById("result-confidence");
  const resultMeta = document.getElementById("result-meta");
  const resultReport = document.getElementById("result-report");

  const overviewMbti = document.getElementById("overview-mbti");
  const overviewConf = document.getElementById("overview-confidence");

  const userName = userNameInput.value.trim();
  const files = fileInput.files;

  // 초기화
  if (resultLabel) resultLabel.innerHTML = "";
  if (resultMbti) resultMbti.innerHTML = "";
  if (resultBehavior) resultBehavior.innerHTML = "";
  if (resultConf) resultConf.innerHTML = "";
  if (resultMeta) resultMeta.innerHTML = "";
  if (resultReport) resultReport.innerHTML = "";
  if (overviewMbti) overviewMbti.innerHTML = "";
  if (overviewConf) overviewConf.innerHTML = "";

  if (!userName) {
    setStatus(statusEl, "먼저 내 카카오톡 이름을 입력해주세요.", "error");
    return;
  }

  if (!files || files.length === 0) {
    setStatus(statusEl, "최소 1개 이상의 카카오톡 내보내기 파일을 선택해주세요.", "error");
    return;
  }

  setStatus(statusEl, "카카오톡 대화를 분석 중입니다...", "loading");

  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("user_name", userName);

  try {
    const res = await fetch("/analyze/kakao", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`서버 오류 (${res.status}): ${text}`);
    }

    const data = await res.json();

    setStatus(statusEl, "분석이 완료되었습니다. 결과를 확인해보세요 🙌", "success");

    // ========== 0. 한 줄 요약 라벨 ==========
    if (data.label && resultLabel) {
      let labelText = "";
      let keyword = "";

      if (typeof data.label === "string") {
        labelText = data.label;
      } else if (typeof data.label === "object") {
        labelText = data.label.label || "";
        keyword = data.label.keyword || "";
      }

      if (labelText) {
        resultLabel.innerHTML = `
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
    }

    // ========== 1. MBTI 요약 ==========
    let mbti = null;
    if (data.mbti && resultMbti) {
      mbti = data.mbti;
      const scores = mbti.scores || {};

      resultMbti.innerHTML = renderMbtiSummary(mbti.type, scores);

      // 개요 섹션에도 간단 요약 복사
      if (overviewMbti) {
        overviewMbti.innerHTML = `
          <h4>MBTI 유형</h4>
          ${renderMbtiSummary(mbti.type, scores)}
        `;
      }

      // 행동 패턴 & 근거 섹션
      if (resultBehavior) {
        renderBehaviorSection(resultBehavior, mbti);
      }
    }

    // ========== 2. 신뢰도 섹션 ==========
    if (data.confidence && resultConf) {
      const c = data.confidence;
      const dataAmount =
        typeof c.data_amount_score === "number" ? c.data_amount_score : "-";
      const srcDiversity =
        typeof c.source_diversity_score === "number"
          ? c.source_diversity_score
          : "-";
      const wordCount =
        typeof c.word_count === "number" ? c.word_count : 0;

      resultConf.innerHTML = renderConfidenceDetail(c, dataAmount, srcDiversity, wordCount);

      // 개요 섹션 요약
      if (overviewConf) {
        overviewConf.innerHTML = `
          <h4>신뢰도 요약</h4>
          ${renderConfidenceCompact(c, wordCount)}
        `;
      }
    }

    // ========== 3. 메타 정보 ==========
    if (data.meta && resultMeta) {
      const m = data.meta;
      const resolved = m.user_sender_resolved || "(감지 실패)";
      resultMeta.innerHTML = `
        <h3>분석 메타 정보</h3>
        <ul class="meta-list">
          <li><span>업로드한 파일 수</span><strong>${m.file_count}</strong></li>
          <li><span>입력한 내 이름</span><strong>${escapeHtml(m.user_name_input || "")}</strong></li>
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

    // ========== 4. AI 리포트 ==========
    if (data.report && resultReport) {
      const htmlReport = data.report
        .replace(/\n/g, "<br />")
        .replace(/ {2}/g, "&nbsp;&nbsp;");

      resultReport.innerHTML = `
        <h3>AI 리포트</h3>
        <div class="report-box">${htmlReport}</div>
      `;
    }

    // 분석 끝나면 "개요" 아코디언을 자동으로 펼치기
    openAccordion("overview");
  } catch (err) {
    console.error(err);
    setStatus(
      statusEl,
      `분석 중 오류가 발생했습니다: ${err.message}`,
      "error"
    );
  }
}

/* ---------- 렌더링 유틸 ---------- */

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
      <h5>게임/밈 관련 대화 예시</h5>
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

/* ---------- 공통 유틸 ---------- */

function escapeHtml(str) {
  if (typeof str !== "string") return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function setStatus(el, text, mode) {
  if (!el) return;

  // mode 없으면 그냥 숨기기
  if (!mode) {
    el.textContent = "";
    el.className = "status-pill status-hidden";
    return;
  }

  el.textContent = text;
  // 기본 클래스 리셋 + 숨김 제거
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


/* ---------- 아코디언 유틸 ---------- */

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

/* ---------- 초기화 ---------- */

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("analyzeBtn");
  if (btn) {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      analyze();
    });
  }

  // ★ 파일 선택 시 UI 업데이트
  const fileInput = document.getElementById("fileInput");
  const fileDrop = fileInput ? fileInput.closest(".file-drop") : null;
  const fileText = fileDrop ? fileDrop.querySelector(".file-drop-text") : null;
  const defaultFileText = fileText ? fileText.innerHTML : "";

  if (fileInput && fileDrop && fileText) {
    fileInput.addEventListener("change", () => {
      const files = fileInput.files;

      if (!files || files.length === 0) {
        // 아무 파일도 없으면 원래 상태로
        fileDrop.classList.remove("has-files");
        fileText.innerHTML = defaultFileText;
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

  // 아코디언 이벤트 바인딩
  document.querySelectorAll(".accordion-header").forEach((header) => {
    header.addEventListener("click", () => {
      toggleAccordion(header);
    });
  });

  // 기본으로 열려 있는(is-open) 아코디언 초기 max-height 세팅
  document.querySelectorAll(".accordion-item.is-open").forEach((item) => {
    const header = item.querySelector(".accordion-header");
    if (!header) return;
    const target = header.dataset.target;
    const body = document.getElementById(`accordion-${target}`);
    if (!body) return;
    body.style.maxHeight = body.scrollHeight + "px";
  });
});
