const fileInput = document.querySelector("#score-file");
const recognizeButton = document.querySelector("#recognize-button");
const contextButton = document.querySelector("#context-button");
const statusNode = document.querySelector("#status");
const parseOutput = document.querySelector("#parse-output");
const answerOutput = document.querySelector("#answer-output");

const imageLikeExtensions = new Set([".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".pdf"]);
const xmlLikeExtensions = new Set([".xml", ".musicxml", ".mxl"]);

function setStatus(message) {
  statusNode.textContent = message;
}

function render(node, value) {
  node.textContent = JSON.stringify(value, null, 2);
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
    throw new Error(payload.detail || `请求失败：${response.status}`);
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
    throw new Error(payload.detail || `请求失败：${response.status}`);
  }
  return payload;
}

function buildSolveRequest(parsed) {
  const extraction = parsed.exerciseExtraction || {};
  const recommended = extraction.recommendedQuestionType || "melody-given";
  return {
    key: parsed.key || parsed.rawSummary?.key || extraction.key || "C",
    timeSignature: parsed.timeSignature || parsed.rawSummary?.timeSignature || extraction.timeSignature || "4/4",
    questionType: recommended,
    melodyMeasures: parsed.melodyMeasures || [],
    bassMeasures: parsed.bassMeasures || [],
    altoMeasures: parsed.altoMeasures || [],
    tenorMeasures: parsed.tenorMeasures || [],
  };
}

async function solveParsedScore(parsed) {
  if (parsed.endToEnd) {
    return parsed.endToEnd;
  }
  const request = buildSolveRequest(parsed);
  if (!request.melodyMeasures.length && !request.bassMeasures.length && !request.altoMeasures.length && !request.tenorMeasures.length) {
    return { status: "skipped", message: "解析结果里没有可提交给求解器的声部数据。" };
  }
  return postJson("/solve-melody", request);
}

async function recognizeAndSolve() {
  const file = selectedFile();
  const extension = extensionOf(file);
  setStatus("处理中");
  recognizeButton.disabled = true;
  contextButton.disabled = true;
  try {
    const parsed = imageLikeExtensions.has(extension)
      ? await uploadForm("/api/omr/enhanced-parse", file, { useVision: true, maxRegions: 3, autoSolve: true })
      : await uploadForm(xmlLikeExtensions.has(extension) ? "/parse-score" : "/read-score", file);
    render(parseOutput, parsed);
    const answer = await solveParsedScore(parsed);
    render(answerOutput, answer);
    setStatus("完成");
  } catch (error) {
    render(answerOutput, { error: error.message });
    setStatus("失败");
  } finally {
    recognizeButton.disabled = false;
    contextButton.disabled = false;
  }
}

async function buildAiContext() {
  const file = selectedFile();
  setStatus("生成上下文");
  recognizeButton.disabled = true;
  contextButton.disabled = true;
  try {
    const context = await uploadForm("/api/photoscore/ai-context", file, { measureLimit: 32 });
    render(parseOutput, context);
    render(answerOutput, { next: "把 parse-score 的结果提交到 /solve-melody 可以生成四部和声答案。" });
    setStatus("完成");
  } catch (error) {
    render(answerOutput, { error: error.message });
    setStatus("失败");
  } finally {
    recognizeButton.disabled = false;
    contextButton.disabled = false;
  }
}

recognizeButton.addEventListener("click", recognizeAndSolve);
contextButton.addEventListener("click", buildAiContext);
