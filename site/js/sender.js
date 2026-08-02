import { LTEncoder } from "./fountain.js";
import { HEADER_LEN, fnv1a, packFrame } from "./protocol.js";
import { QrCode, QrSegment } from "./qr.js";

const MARGIN = 4;
const LOOKAHEAD = 3;

const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const canvas = document.getElementById("qr");
const specs = document.getElementById("specs");
const cfgFps = document.getElementById("cfg-fps");
const cfgBytes = document.getElementById("cfg-bytes");
const cfgSize = document.getElementById("cfg-size");
const status = document.getElementById("status");

let generation = 0;

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer.files.length > 0) startWithFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) startWithFile(fileInput.files[0]);
});

for (const el of [cfgFps, cfgBytes, cfgSize]) {
  el.addEventListener("change", () => {
    if (window._currentFile) startWithFile(window._currentFile);
  });
}

async function startWithFile(file) {
  window._currentFile = file;
  const gen = ++generation;
  const payload = new Uint8Array(await file.arrayBuffer());

  const txFps = Number(cfgFps.value);
  const frameBytes = Number(cfgBytes.value);
  const displayPx = Number(cfgSize.value);
  const blockLen = frameBytes - HEADER_LEN;

  const sessionId = (Math.floor(Math.random() * 0xfffe) + 1) & 0xffff;
  const encoder = new LTEncoder(payload, blockLen, sessionId);
  const header = {
    sessionId,
    seq: 0,
    k: encoder.k,
    blockLen,
    totalLen: payload.length,
    payloadFnv: fnv1a(payload),
  };

  dropZone.style.display = "none";
  canvas.style.display = "block";
  specs.textContent =
    `${file.name} · ${(payload.length / 1024).toFixed(1)} KB · ` +
    `K=${encoder.k} · ${txFps} fps · ${frameBytes} B/frame`;
  status.textContent = "streaming";
  status.className = "status streaming";

  let version;
  let modules = 0;
  let scale = 1;
  const staging = document.createElement("canvas");
  const queue = [];
  let nextSeq = 0;

  const sizeCanvas = () => {
    const dpr = window.devicePixelRatio || 1;
    const total = modules + 2 * MARGIN;
    const cssBudget = Math.min(0.9 * Math.min(window.innerWidth, window.innerHeight), displayPx);
    scale = Math.max(1, Math.floor((cssBudget * dpr) / total));
    staging.width = total;
    staging.height = total;
    canvas.width = total * scale;
    canvas.height = total * scale;
    canvas.style.width = `${(total * scale) / dpr}px`;
    canvas.style.height = `${(total * scale) / dpr}px`;
  };

  const makeFrame = () => {
    const bytes = packFrame({ ...header, seq: nextSeq }, encoder.encode(nextSeq));
    nextSeq++;
    const seg = QrSegment.makeBytes(Array.from(bytes));
    const qr = QrCode.encodeSegments([seg], QrCode.Ecc.LOW, 1, 40, -1, false);
    if (version === undefined) {
      version = qr.version;
      modules = qr.size;
      sizeCanvas();
    }
    const size = qr.size;
    const total = size + 2 * MARGIN;
    const img = new ImageData(total, total);
    const px = new Uint32Array(img.data.buffer);
    px.fill(0xffffffff);
    for (let y = 0; y < size; y++) {
      const row = (y + MARGIN) * total + MARGIN;
      for (let x = 0; x < size; x++) {
        if (qr.getModule(x, y)) px[row + x] = 0xff000000;
      }
    }
    return img;
  };

  const pump = () => {
    if (gen !== generation) return;
    try {
      while (queue.length < LOOKAHEAD) queue.push(makeFrame());
    } catch (err) {
      specs.textContent = `Error: ${err.message || err}`;
      return;
    }
    setTimeout(pump, 0);
  };
  pump();

  const interval = 1000 / txFps;
  let nextAt = performance.now();
  const tick = (now) => {
    if (gen !== generation) return;
    requestAnimationFrame(tick);
    if (now < nextAt) return;
    const img = queue.shift();
    if (!img) {
      nextAt = now + interval;
      return;
    }
    staging.getContext("2d").putImageData(img, 0, 0);
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(staging, 0, 0, canvas.width, canvas.height);
    nextAt += interval;
    if (now - nextAt > 3 * interval) nextAt = now + interval;
  };
  requestAnimationFrame(tick);

  try {
    await navigator.wakeLock?.request("screen");
  } catch {}
}
