# Lucide icon map

Replace every hand-drawn SVG in the prototype with a Lucide `<i data-lucide="…">`.
Never ship inline `<svg>` for chrome icons.

**Exception -- the 3 grid tools + palette swatches.** Both modes use the same
pre-rotated landscape pencil/eraser art and upright crayon SVGs, inlined by
`js/utils/toolArt.js`, per the prototype's craft-box aesthetic -- simple mode
renders them as bookmark-style tabs bleeding off the sidebar
(`landscapeArtHtml`), advanced mode renders the same art as a small,
fully-contained icon inside its usual bordered button (`compactArtHtml`). No
Lucide icon is used for these three tools in either mode -- see the table
below.

| UI action | Both modes (art SVG, `toolArt.js`) |
|-----------|-------------------------------------|
| Reset pixel / revert (top) | `rotated_pencil_eraser.svg`, fixed colours |
| Eraser (paint off) | `rotated_color_pencil.svg`, MainColor = dark grey |
| Pencil / draw | `rotated_color_pencil.svg`, MainColor = brush colour |
| Palette swatch | `Crayon.svg`, MainColor = swatch colour, upright, side by side (simple); CSS `.swatch-crayon` rectangle (advanced) |
| Undo | `undo-2` (top bar, next to Rename) | `undo-2` (top bar, next to Rename) |
| New file | `file-plus` |
| Open | `folder-open` |
| Save | `save` |
| Rename | `pencil-line` |
| Adjust / pixelation | `sliders-horizontal` |
| Advanced / settings gear | `settings` |
| Download | `download` |
| Device plug | `plug-zap` |
| Close × | `x` |
| Crop scissors | `scissors` |
| Brightness sun | `sun` |
| Add colour + | `plus` |
| HW drawer closed | `chevron-right` |
| HW drawer open | `chevron-down` |
| Delete | `trash-2` |
| Refresh | `refresh-cw` |
| Send | `send` |
| Copy | `copy` |
| Pause | `pause` |
| Play / resume | `play` |
| Eye show | `eye` |
| Eye hide | `eye-off` |
| Connect bolt | `zap` |

After every reactive remount and after opening a popover/drawer, call:

```js
window.lucide?.createIcons?.();
```
