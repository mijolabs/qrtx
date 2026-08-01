import { prepareZXingModule, readBarcodes } from "https://unpkg.com/zxing-wasm@2/dist/reader/index.js";

prepareZXingModule({
  overrides: {
    locateFile: (path, prefix) =>
      path.endsWith(".wasm")
        ? "https://unpkg.com/zxing-wasm@2/dist/reader/zxing_reader.wasm"
        : prefix + path,
  },
});

self.onmessage = async (e) => {
  const { id, buf, w, h } = e.data;
  try {
    const img = new ImageData(new Uint8ClampedArray(buf), w, h);
    const results = await readBarcodes(img, { formats: ["QRCode"], maxNumberOfSymbols: 1 });
    const r = results.find((x) => x.isValid && x.bytes.length > 0);
    self.postMessage({ id, bytes: r ? r.bytes : null });
  } catch {
    self.postMessage({ id, bytes: null });
  }
};

readBarcodes(new ImageData(8, 8), { formats: ["QRCode"] }).then(
  () => self.postMessage({ id: -1, bytes: null }),
  () => self.postMessage({ id: -2, bytes: null }),
);
