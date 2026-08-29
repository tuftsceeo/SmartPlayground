/** advancedLayout.js -- today's three-column dev surface; canvases are slots. */

export function advancedLayoutHtml() {
  return `
    <div id="topBarMount"></div>
    <div class="flex-1 grid grid-cols-[320px_360px_1fr] overflow-hidden">
      <div class="flex flex-col overflow-y-auto border-r border-neutral-800">
        <div id="importMount"></div>
        <div class="p-3 flex flex-col gap-2 items-center">
          <div>
            <div class="text-[11px] text-neutral-500 mb-1">source</div>
            <div data-canvas-slot="source" class="canvas-slot-source"></div>
          </div>
          <div>
            <div class="text-[11px] text-neutral-500 mb-1">segmented</div>
            <div data-canvas-slot="segmented" class="canvas-slot-source"></div>
          </div>
        </div>
      </div>

      <div id="segmentListMount" class="overflow-y-auto border-r border-neutral-800"></div>

      <div class="flex flex-col overflow-y-auto">
        <div class="p-3 flex flex-col items-center">
          <div data-canvas-slot="preview" class="canvas-slot-preview"></div>
        </div>
        <div id="brightnessMount"></div>

        <div class="p-3 flex flex-col items-center border-t border-neutral-800">
          <div data-canvas-slot="grid" class="canvas-slot-grid-advanced"></div>
        </div>
        <div id="gridControlsMount"></div>

        <div id="problemsMount"></div>
        <div id="deviceMount" class="mt-auto"></div>
      </div>
    </div>
  `;
}
