# Lucide icon map

Replace every hand-drawn SVG in the prototype with a Lucide `<i data-lucide="…">`.
Never ship inline `<svg>` for chrome icons.

| UI action | Lucide name |
|-----------|-------------|
| Pencil / draw | `pencil` |
| Eraser | `eraser` |
| Reset pixel / revert | `rotate-ccw` |
| Undo | `undo-2` |
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
