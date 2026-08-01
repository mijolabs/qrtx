import { LTDecoder } from "./fountain.js";
import { fnv1a, parseFrame } from "./protocol.js";

const OVERHEAD_EST = 1.18;

const startBtn = document.getElementById("start");
const video = document.getElementById("video");
const preview = document.getElementById("preview");
const statsEl = document.getElementById("stats");
const progress = document.getElementById("progress");
const bar = document.getElementById("bar");
const result = document.getElementById("result");
const settings = document.getElementById("settings");
const metrics = document.getElementById("metrics");

const metric = (id) => document.getElementById(`m-${id}`);

let decoder = null;
let sessionId = null;
let startTs = 0;
let captureGen = 0;
let done = false;
let stream = null;

const workers = [];
const busy = [];
const captureTimes = [];
const decodeTimes = [];

const cfgWidth = document.getElementById("cfg-width");
const cfgCapFps = document.getElementById("cfg-capfps");
const cfgWorkers = document.getElementById("cfg-workers");

startBtn.addEventListener("click", start);

async function start() {
  if (!navigator.mediaDevices?.getUserMedia) {
    statsEl.textContent = "Camera requires HTTPS (secure context)";
    return;
  }

  const captureW = Number(cfgWidth.value);
  const captureFps = Number(cfgCapFps.value);
  const workerCount = Number(cfgWorkers.value);

  startBtn.style.display = "none";
  settings.style.display = "none";
  preview.style.display = "block";
  metrics.style.display = "grid";
  progress.style.display = "block";

  const constraints = {
    video: {
      facingMode: "environment",
      width: { ideal: captureW },
      height: { ideal: Math.round(captureW * 3 / 4) },
    },
  };

  try {
    constraints.video.frameRate = { exact: captureFps };
    stream = await navigator.mediaDevices.getUserMedia(constraints);
  } catch {
    constraints.video.frameRate = { ideal: captureFps };
    stream = await navigator.mediaDevices.getUserMedia(constraints);
  }

  video.srcObject = stream;
  await video.play();

  const track = stream.getVideoTracks()[0];
  const s = track.getSettings();
  statsEl.textContent = `${s.width}×${s.height} @ ${s.frameRate} fps`;

  for (let i = 0; i < workerCount; i++) {
    const w = new Worker("/static/js/worker.js", { type: "module" });
    w.onmessage = (e) => {
      const { id, bytes } = e.data;
      if (id === -1) return;
      busy[id] = false;
      if (bytes) {
        decodeTimes.push(performance.now());
        onDecoded(new Uint8Array(bytes));
      }
    };
    workers.push(w);
    busy.push(false);
  }

  const gen = ++captureGen;
  scheduleFrame(gen);
  setInterval(updateStats, 500);

  try {
    await navigator.wakeLock?.request("screen");
  } catch {}
}

function scheduleFrame(gen) {
  if (gen !== captureGen || done) return;
  if ("requestVideoFrameCallback" in video) {
    video.requestVideoFrameCallback(() => {
      captureFrame();
      scheduleFrame(gen);
    });
  } else {
    requestAnimationFrame(() => {
      captureFrame();
      scheduleFrame(gen);
    });
  }
}

const offscreen = document.createElement("canvas");
const offCtx = offscreen.getContext("2d", { willReadFrequently: true });

function captureFrame() {
  if (done || video.videoWidth === 0) return;
  const w = video.videoWidth;
  const h = video.videoHeight;
  offscreen.width = w;
  offscreen.height = h;
  offCtx.drawImage(video, 0, 0);
  const img = offCtx.getImageData(0, 0, w, h);

  captureTimes.push(performance.now());

  let slot = -1;
  for (let i = 0; i < workers.length; i++) {
    if (!busy[i]) { slot = i; break; }
  }
  if (slot === -1) return;
  busy[slot] = true;
  workers[slot].postMessage(
    { id: slot, buf: img.data.buffer, w, h },
    [img.data.buffer],
  );
}

function onDecoded(bytes) {
  if (done) return;
  const parsed = parseFrame(bytes);
  if (!parsed) return;
  const { header, block } = parsed;

  if (sessionId !== header.sessionId) {
    sessionId = header.sessionId;
    decoder = new LTDecoder(header.k, header.blockLen, header.sessionId, header.totalLen);
    startTs = performance.now();
    done = false;
    bar.style.width = "0%";
    result.innerHTML = "";
  }

  decoder.addFrame(header.seq, block);

  const pct = Math.min(0.99, decoder.framesNew / (decoder.k * OVERHEAD_EST));
  bar.style.width = `${(pct * 100).toFixed(1)}%`;

  if (decoder.isComplete) {
    const payload = decoder.assemble();
    const hash = fnv1a(payload);
    const hashOk = hash === header.payloadFnv;
    finish(payload, hashOk, header);
  }
}

function finish(payload, hashOk, header) {
  done = true;
  bar.style.width = "100%";

  if (stream) {
    for (const track of stream.getTracks()) track.stop();
  }
  for (const w of workers) w.terminate();

  const elapsed = ((performance.now() - startTs) / 1000).toFixed(1);
  const size = payload.length;
  const rate = (size / 1024 / parseFloat(elapsed)).toFixed(1);

  const blob = new Blob([payload], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);

  result.innerHTML = `
    <div class="complete">
      <h2>Transfer complete</h2>
      <p>${(size / 1024).toFixed(1)} KB in ${elapsed}s (${rate} KB/s)</p>
      <p>Hash: ${hashOk ? "verified ✓" : "MISMATCH ✗"}</p>
      <p>${decoder.framesNew} frames received, ${decoder.framesDup} duplicates</p>
      <a href="${url}" download="received_file" class="download-btn">Download file</a>
    </div>
  `;
}

function updateStats() {
  if (!decoder) return;
  const now = performance.now();
  const window2s = now - 2000;

  while (captureTimes.length > 0 && captureTimes[0] < window2s) captureTimes.shift();
  while (decodeTimes.length > 0 && decodeTimes[0] < window2s) decodeTimes.shift();

  const capFps = captureTimes.length / 2;
  const decFps = decodeTimes.length / 2;
  const elapsed = ((now - startTs) / 1000).toFixed(1);
  const goodput = startTs > 0 && decoder.framesNew > 0
    ? ((decoder.framesNew * decoder.blockLen) / 1024 / ((now - startTs) / 1000)).toFixed(1)
    : "—";

  metric("cap").textContent = capFps.toFixed(0);
  metric("dec").textContent = decFps.toFixed(0);
  metric("rate").textContent = `${goodput} KB/s`;
  metric("time").textContent = `${elapsed}s`;
  metric("frames").textContent = `${decoder.framesNew} / ${decoder.framesDup}`;
  metric("k").textContent = decoder.k;
  metric("block").textContent = decoder.blockLen;
  metric("payload").textContent = `${(decoder.totalLen / 1024).toFixed(1)} KB`;
}
