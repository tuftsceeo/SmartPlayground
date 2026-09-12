/** simpleLayout.js -- teacher-facing prototype card; no hardware drawer. */

export function simpleLayoutHtml() {
  return `
    <div class="app-card">
      <div class="flex items-stretch border-b-2 border-[var(--border)]">
        <div id="topBarMount" class="flex-1 min-w-0"></div>
        <div id="deviceMount" class="relative flex items-center pr-6 flex-none"></div>
      </div>

      <div class="flex gap-5 px-6 py-5 flex-1 min-h-0 overflow-hidden">
        <div class="w-24 flex flex-col gap-2.5 flex-none">
          <div class="flex flex-col gap-1.5 items-center">
            <span class="text-[10.5px] font-bold text-[var(--muted2)] text-center">source photo</span>
            <div data-canvas-slot="source" class="canvas-slot-source-simple"></div>
            <div id="importMount" class="w-full"></div>
          </div>
          <div id="toolRowMount"></div>
        </div>

        <div class="flex-1 flex items-center justify-center min-w-0 min-h-0">
          <div data-canvas-slot="grid" class="canvas-slot-grid-simple hero-grid-wrap"></div>
        </div>

        <div class="w-[200px] flex flex-col gap-3.5 flex-none overflow-y-auto">
          <div id="paletteMount"></div>
          <div class="panel flex flex-col gap-2 items-center">
            <span class="panel-label self-start">LED preview</span>
            <div data-canvas-slot="preview" class="canvas-slot-preview-simple"></div>
            <div id="brightnessMount" class="w-full"></div>
          </div>
          <div id="gridControlsMount" class="hidden" aria-hidden="true"></div>
          <div id="problemsMount" class="hidden" aria-hidden="true"></div>
        </div>
      </div>

      <div id="adjustDrawer">
        <button type="button" id="adjustDrawerToggle" class="drawer-header drawer-header-adjust">
          <span class="flex items-center gap-2">
            <i data-lucide="sliders-horizontal" class="w-4 h-4"></i>
            Pixelation &amp; segment colours
          </span>
          <span class="adjust-chevron-wrap"><i data-lucide="chevron-down" class="w-4 h-4"></i></span>
        </button>
        <div id="adjustDrawerBody" class="hidden border-t-2 border-[var(--border)] bg-[var(--adjust-bg)] px-6 py-5">
          <div class="flex gap-6">
            <div class="w-[230px] flex flex-col gap-1.5 flex-none">
              <span class="panel-label">Segmentation result</span>
              <div data-canvas-slot="segmented" class="canvas-segmented-drawer"></div>
              <span class="text-[11px] font-semibold text-[var(--muted2)]">the auto colour-fill, before your edits</span>
            </div>
            <div class="flex-1 flex flex-col gap-3.5 min-w-0">
              <div id="segmentListMount"></div>
            </div>
          </div>
        </div>
      </div>

      <div id="hwDrawerMount" class="hidden" aria-hidden="true"></div>
    </div>
  `;
}
