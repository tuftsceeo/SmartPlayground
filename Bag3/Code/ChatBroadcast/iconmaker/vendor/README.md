# Vendored third-party assets

## cropperjs 1.6.2
- Files: `cropper.min.js`, `cropper.min.css`
- Source: https://unpkg.com/cropperjs@1.6.2/dist/
- Upstream: https://github.com/fengyuanchen/cropperjs
- License: MIT (Copyright 2015-present Chen Fengyuan) -- see the banner
  comment preserved at the top of each file.

Vendored rather than loaded from a CDN on purpose: this tool is meant to
work on classroom wifi and from a plain `python3 -m http.server`, so it
should not acquire a runtime dependency on an external host. 41KB total.

Used ONLY for the crop/scale interaction (drag, zoom, 1:1 aspect lock,
handles). The actual pixel resampling is done by
`js/pipeline/decode.js:renderWorking()` from the crop rectangle Cropper
reports via `getData()` -- deliberately NOT by `getCroppedCanvas()`, so the
smoothing policy stays under our control (see that function's comments:
nearest-neighbour when upscaling keeps flat-colour art on the exact-fill
segmentation path).
