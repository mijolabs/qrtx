# qrtx

Fountain-coded QR file transfer. Port of [decimen-optical-transfer](https://github.com/bashalarmistalt/decimen-optical-transfer), rewritten from TypeScript/Vite to vanilla JS. Hosted on GitHub Pages.

## Stack

- **Frontend**: Vanilla ES module JavaScript, no build step, no bundler
- **Hosting**: GitHub Pages (deployed via GitHub Actions on push to `main`)
- **QR encode**: Vendored [Project Nayuki qrcodegen](https://www.nayuki.io/page/qr-code-generator-library) (`site/js/qr.js`)
- **QR decode**: [zxing-wasm v2](https://github.com/niclasvaneyk/zxing-wasm) vendored in `site/js/zxing/`

## Project layout

```
site/                     # Deployed to GitHub Pages
  index.html              # Landing page
  send/index.html         # Sender page
  receive/index.html      # Receiver page
  css/style.css
  js/
    sender.js             # File -> LT encoder -> QR canvas stream
    receiver.js           # Camera -> Web Workers -> QR decode -> LT decoder -> file
    worker.js             # Web Worker: zxing-wasm QR decoding
    zxing/                # Vendored zxing-wasm v2.2.4 (reader.js, share.js, zxing_reader.wasm)
    protocol.js           # Binary frame protocol (20-byte header, pack/parse, FNV-1a)
    fountain.js           # LT fountain codes (LTEncoder, LTDecoder)
    qr.js                 # Vendored Nayuki QR code generator
.github/workflows/
  pages.yml               # Deploys site/ to GitHub Pages on push to main
```

## Commands

```sh
python3 -m http.server -d site          # local dev server (or: npx serve site)
```

## Key architecture notes

- There is no backend. All transfer logic runs client-side in the browser.
- The sender generates fountain-coded frames and renders them as QR codes on a canvas at configurable FPS.
- The receiver captures camera frames, dispatches them to a pool of Web Workers running zxing-wasm for QR decoding, then feeds decoded bytes into an LT decoder. If module workers fail (e.g. iOS Safari), a main-thread fallback decoder activates automatically.
- QR codes use error correction level L (minimum) because the fountain code layer handles frame loss.
- Camera requires HTTPS (or localhost) for `getUserMedia`. GitHub Pages provides HTTPS.
- All paths in HTML and JS are relative (no absolute `/` paths) so the site works on any base path.
