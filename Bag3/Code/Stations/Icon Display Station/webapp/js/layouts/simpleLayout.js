/** simpleLayout.js -- teacher-facing MS-Paint layout; grid promoted, larger. */

export function simpleLayoutHtml() {
  return `
    <div id="topBarMount"></div>
    <div class="flex-1 grid grid-cols-[220px_260px_1fr] overflow-hidden">
      <div class="flex flex-col overflow-y-auto border-r border-neutral-800">
        <div id="importMount"></div>
        <div class="p-2 flex flex-col gap-2 items-center">
          <div>
            <div class="text-[11px] text-neutral-500 mb-1">source</div>
            <div data-canvas-slot="source" class="canvas-slot-source-simple"></div>
          </div>
          <div>
            <div class="text-[11px] text-neutral-500 mb-1">segmented</div>
            <div data-canvas-slot="segmented" class="canvas-slot-source-simple"></div>
          </div>
        </div>
      </div>

      <div id="segmentListMount" class="overflow-y-auto border-r border-neutral-800"></div>

      <div class="flex flex-col overflow-y-auto">
        <div class="p-2 flex flex-col items-center">
          <div data-canvas-slot="preview" class="canvas-slot-preview-simple"></div>
        </div>
        <div id="brightnessMount"></div>

        <div class="p-3 flex flex-col items-center border-t border-neutral-800 flex-1 min-h-0">
          <div data-canvas-slot="grid" class="canvas-slot-grid-simple"></div>
        </div>
        <div id="gridControlsMount"></div>

        <div id="problemsMount" class="hidden"></div>
        <div id="deviceMount"></div>
      </div>
    </div>
  `;
}
