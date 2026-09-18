const fileInput = document.querySelector("#score-file");
const recognizeButton = document.querySelector("#recognize-button");
const photoscoreButton = document.querySelector("#photoscore-button");
const statusNode = document.querySelector("#status");
const parseOutput = document.querySelector("#parse-output");
const answerOutput = document.querySelector("#answer-output");

const imageLikeExtensions = new Set([".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".pdf"]);
const xmlLikeExtensions = new Set([".xml", ".musicxml", ".mxl"]);

function setStatus(message) {
  statusNode.textContent = message;
}

function render(node, value) {
  node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function setBusy(isBusy, message) {
  recognizeButton.disabled = isBusy;
  photoscoreButton.disabled = isBusy;
  if (message) setStatus(message);
}

function selectedFile() {
  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    throw new Error("请先选择一个谱面文件。");
  }
  return file;
}

function extensionOf(file) {
  const name = file.name || "";
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

async function uploadForm(endpoint, file, extraFields = {}) {
  const form = new FormData();
  form.append("file", file);
  Object.entries(extraFields).forEach(([key, value]) => form.append(key, String(value)));
  const response = await fetch(endpoint, { method: "POST", body: form });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof payload.detail === "string" ? payload.detail : `请求失败：${response.status}`);
  }
  return payload;
}

async function postJson(endpoint, body) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof payload.detail === "string" ? payload.detail : `请求失败：${response.status}`);
  }
  return payload;
}

function buildSolveRequest(parsed) {
  const extraction = parsed.exerciseExtraction || {};
  return {
    key: parsed.key || parsed.rawSummary?.key || extraction.key || "C",
    timeSignature: parsed.timeSignature || parsed.rawSummary?.timeSignature || extraction.timeSignature || "4/4",
    questionType: extraction.recommendedQuestionType || "melody",
    melodyMeasures: parsed.melodyMeasures || [],
    bassMeasures: parsed.bassMeasures || [],
    altoMeasures: parsed.altoMeasures || [],
    tenorMeasures: parsed.tenorMeasures || [],
  };
}

async function solveParsedScore(parsed) {
  if (parsed.endToEnd) return parsed.endToEnd;
  const request = buildSolveRequest(parsed);
  const hasVoice = request.melodyMeasures.length || request.bassMeasures.length ||
    request.altoMeasures.length || request.tenorMeasures.length;
  if (!hasVoice) {
    return { status: "skipped", message: "解析结果里没有可提交给求解器的声部数据。" };
  }
  return postJson("/solve-melody", request);
}

function answerSummary(result) {
  const answer = result.answer || result;
  const lines = [];
  lines.push(`状态：${answer.status || answer.summary?.status || "unknown"}`);
  if (answer.questionType) lines.push(`题型：${answer.questionType}`);
  if (answer.exerciseKind) lines.push(`识别类型：${answer.exerciseKind}`);
  const fourPart = answer.solution?.fourPart || answer.fourPart;
  const voices = fourPart?.voices || [];
  if (voices.length) {
    lines.push("");
    lines.push("四部答案：");
    for (const voice of voices) {
      lines.push(`${voice.name || voice.voice || "voice"}：${JSON.stringify(voice.entries || voice.measures || voice)}`);
    }
  }
  const harmonies = fourPart?.harmonies || answer.solution?.harmonies || [];
  if (harmonies.length) {
    lines.push("");
    lines.push("和声：");
    lines.push(JSON.stringify(harmonies, null, 2));
  }
  if (answer.issues?.length) {
    lines.push("");
    lines.push("需要复核：");
    lines.push(JSON.stringify(answer.issues, null, 2));
  }
  return lines.join("\n");
}

function reviewSummary(result) {
  return {
    source: result.source,
    inputPolicy: result.inputPolicy,
    textReview: result.textReview,
    quality: result.quality,
    exerciseExtraction: result.exerciseExtraction,
    solverEligibility: result.solverEligibility,
  };
}

async function photoscoreSolve() {
  const file = selectedFile();
  const extension = extensionOf(file);
  if (!xmlLikeExtensions.has(extension)) {
    throw new Error("PhotoScore 主流程需要上传导出的 .xml/.musicxml/.mxl 文件。");
  }
  setBusy(true, "PhotoScore XML 求解中");
  try {
    const result = await uploadForm("/api/photoscore/solve", file, { measureLimit: 32, autoSolve: true });
    render(answerOutput, answerSummary(result));
    render(parseOutput, reviewSummary(result));
    setStatus("完成");
  } catch (error) {
    render(answerOutput, { error: error.message });
    setStatus("失败");
  } finally {
    setBusy(false);
  }
}

async function recognizeAndSolve() {
  const file = selectedFile();
  const extension = extensionOf(file);
  setBusy(true, "识别求解中");
  try {
    const parsed = imageLikeExtensions.has(extension)
      ? await uploadForm("/api/omr/enhanced-parse", file, { useVision: true, maxRegions: 3, autoSolve: true })
      : await uploadForm(xmlLikeExtensions.has(extension) ? "/parse-score" : "/read-score", file);
    const answer = await solveParsedScore(parsed);
    render(answerOutput, answerSummary(answer));
    render(parseOutput, parsed);
    setStatus("完成");
  } catch (error) {
    render(answerOutput, { error: error.message });
    setStatus("失败");
  } finally {
    setBusy(false);
  }
}

photoscoreButton.addEventListener("click", () => {
  photoscoreSolve().catch((error) => {
    render(answerOutput, { error: error.message });
    setStatus("失败");
  });
});

recognizeButton.addEventListener("click", () => {
  recognizeAndSolve().catch((error) => {
    render(answerOutput, { error: error.message });
    setStatus("失败");
  });
});
