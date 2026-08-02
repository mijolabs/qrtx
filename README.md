# qrtx

Transfer files between devices using only a screen and a camera. No network, no app install, no pairing — the payload travels as light.

One device displays a file as a stream of animated QR codes; the other points its camera at the screen and reconstructs the file. Fountain codes make it resilient to missed frames: any sufficient subset of frames is enough to recover the data.

**[Try it live](https://mijolabs.github.io/qrtx/)**

Based on [decimen-optical-transfer](https://github.com/bashalarmistalt/decimen-optical-transfer), a proof-of-concept that demonstrated fountain-coded QR transfer with fixed demo payloads. qrtx takes the same core algorithm and turns it into a deployable tool that can send any file.

## How it works

1. **Sender** reads a file, splits it into blocks, and encodes each frame as an XOR of a pseudorandom subset of blocks (Luby Transform / fountain code). Each frame carries a 20-byte self-describing header so the receiver can lock onto the stream mid-flight.

2. **Receiver** opens the camera, captures frames into a pool of Web Workers running zxing-wasm for QR decoding, and feeds decoded bytes into an LT decoder. Once ~1.18x the number of source blocks have been received, belief propagation solves the remaining blocks and the file is assembled.

3. The sender loops forever. The receiver can start at any point, miss frames, and still reconstruct the file — dropped frames cost time but never correctness.

## Local development

Serve the `site/` directory with any static file server:

```sh
python3 -m http.server -d site
# or
npx serve site
```

Open `http://localhost:8000` (or whatever port your server uses). Camera access requires HTTPS or localhost.

## Differences from decimen-optical-transfer

The upstream project is a proof-of-concept that only streams fixed demo payloads.

| | decimen-optical-transfer | qrtx |
|---|---|---|
| Purpose | PoC / demo | Deployable file transfer tool |
| File selection | Fixed demo payloads only | Any file (drag-and-drop / picker) |
| Receiver output | Displays image in browser | Download button for any file type |
| Deployment | Vite dev server on LAN | Hosted publicly, doesn't require setup |
| Language | TypeScript + Vite | Vanilla JS |
| QR decoding | zxing-wasm (bundled by Vite) | zxing-wasm (vendored) |
| iOS Safari | No fallback | Main-thread decoder fallback |

The core algorithm is identical: fountain codes, binary frame protocol, soliton distribution, FNV-1a integrity check, same default settings.

## License

MIT
