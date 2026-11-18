/**
 * toolArt.js -- hand-drawn "art supply" SVGs (colored pencil / eraser /
 * crayon) used as the simple-mode tool icons and palette swatches, per the
 * prototype's craft-box aesthetic. Advanced mode keeps plain Lucide icons.
 *
 * Each source SVG has a <g id="_x3C_MainColor_x3E_"> group (Illustrator's
 * <MainColor> layer convention) holding the paths that make up the tool's
 * primary body. recolorMainColor() overrides just those paths' fill via an
 * inline style attribute -- inline style always wins over the SVG's own
 * class-based <style> rules, so the rest of the artwork's shading/highlight
 * layers are left untouched.
 */

/** Pre-rotated landscape pencil (tip on the right); MainColor recolourable. */
export const ROTATED_COLOR_PENCIL_SVG = `<svg id="color_x5F_pencil" xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 342.7 33.8">
  <defs>
    <style>
      .st0 { fill: #fef8e4; }
      .st1 { fill: #f4ca97; }
      .st2 { fill: #36729c; }
      .st3 { fill: #f4edd6; }
      .st4 { isolation: isolate; opacity: .2; }
      .st5 { fill: #fdf4e0; }
    </style>
  </defs>
  <g id="_x3C_MainColor_x3E_">
    <path class="st2" d="M342.7,15.3c-.3,1.3.4,3.6-1.6,3.7-6.1,1.5-12.1,3.6-18.4,4.8-.2-1.5-.4-2.9-.6-4.4.7-.7,1.3-1.4,2-2.1-1.4-2.3-2.3-4.9-1.5-7.5,6.8,1.4,13.4,3.7,20.1,5.5h0Z"/>
    <path class="st2" d="M294.1,2.1c.3.5.8,1.6,1.1,2.1-2,2.1-4.2,4.2-6.9,5.4-79.4-.2-158.8,0-238.2-.1V.1h239c1.8.4,3.3,1.3,5,2h0Z"/>
    <path class="st2" d="M289,11.9c2.2,1.7,4,3.8,5.5,6-1.3,1-2.6,2.1-4,3.1-3.8-.5-7.6-.7-11.5-.6-76.4-.1-152.7-.2-229.1,0v-8.3h218.1c6.9,0,13.9.2,20.8-.1h.2Z"/>
    <path class="st2" d="M288.4,24.5c2.5,1.2,4.5,3.1,6.5,4.9-.5.5-1.4,1.5-1.8,1.9-.7.6-1.5,1.4-2.5,1.6-6.1-.7-12.3-.3-18.5-.4-16-.4-32-.3-48.1,0-28.6,0-57.3-.3-85.9-.2-14.4.4-28.7,0-43.1,0-15.1-.3-30.1.2-45.2,0v-7.8c60.1-.1,120.1.1,180.2,0,19.4,0,38.9.2,58.3-.2h.1Z"/>
    <path class="st2" d="M34.5,0c-.2,11.2-.1,22.5,0,33.7-9.4,0-18.8,0-28.3,0-3,.4-6.2-2.2-5.9-5.4C.3,20.6-.1,12.9,0,5.3,0,2.6,2.4,0,5.2,0,15,0,24.7.2,34.5,0h0Z"/>
    <path class="st2" d="M272.2,32.6c6.2,0,12.3-.3,18.5.4-2.7,1.1-5.6.7-8.5.8-77.4,0-154.8,0-232.2,0v-1.3c15.1,0,30.1-.4,45.2,0,14.4,0,28.7.3,43.1,0,28.6,0,57.3.2,85.9.2,16-.2,32-.3,48.1,0h0Z"/>
    <path class="st2" d="M279.1,20.4c3.8-.1,7.7,0,11.5.6-.4.2-1.2.7-1.6,1-44.6-.5-89.2-.1-133.8-.2-35.1,0-70.1,0-105.2,0v-1.3c76.4-.1,152.8,0,229.1,0h0Z"/>
  </g>
  <path class="st4" d="M278.9,20.5c3.8-.1,7.7,0,11.5.6-.4.2-1.2.7-1.6,1-44.6-.5-89.2-.1-133.8-.2-35.1,0-70.1,0-105.2,0v-1.3c76.4-.1,152.8,0,229.1,0h0Z"/>
  <path class="st4" d="M272.2,32.6c6.2,0,12.3-.3,18.5.4-2.7,1.1-5.6.7-8.5.8-77.4,0-154.8,0-232.2,0v-1.3c15.1,0,30.1-.4,45.2,0,14.4,0,28.7.3,43.1,0,28.6,0,57.3.2,85.9.2,16-.2,32-.3,48.1,0h0Z"/>
  <path class="st5" d="M289,22c0,.6-.4,1.9-.6,2.5-19.4.4-38.9.1-58.3.2-60.1.1-120.1-.1-180.2,0v-3c35.1,0,70.1.1,105.2,0,44.6.1,89.2-.3,133.8.2h0Z"/>
  <path class="st1" d="M322.6,9.9c-.8,2.7,0,5.2,1.5,7.5-.7.7-1.3,1.4-2,2.1.2,1.5.4,2.9.6,4.4-4.9,1.7-9.9,2.8-14.9,4.2-4.9,1.3-9.7,3-14.7,3.3.5-.5,1.4-1.5,1.8-1.9-2-1.9-4-3.7-6.5-4.9,0-.6.4-1.9.6-2.5.4-.2,1.2-.7,1.6-1,1.3-1,2.6-2,4-3.1-1.5-2.3-3.4-4.3-5.5-6.1-.2-.8-.5-1.5-.7-2.2,2.7-1.2,4.9-3.3,6.9-5.4-.3-.5-.8-1.6-1.1-2.1,9.6,2.3,19.1,4.8,28.5,7.8h0Z"/>
  <path class="st0" d="M288.3,9.6c.2.8.5,1.5.7,2.2-6.9.4-13.9.1-20.8.1H50.1v-2.6c79.4.2,158.8-.1,238.2.1h0v.2Z"/>
  <path class="st3" d="M50.1.1v33.7h-15.5c0-11.2-.2-22.5,0-33.7,5.2-.3,10.4,0,15.6,0h-.1Z"/>
</svg>`;

/** Pre-rotated landscape pencil-with-eraser tip; fixed palette, no MainColor group. */
export const ROTATED_PENCIL_ERASER_SVG = `<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 342.7 34.1">
  <defs>
    <style>
      .st0 { fill: #f6f0dc; }
      .st1 { fill: #fcb824; }
      .st2 { fill: #ffba22; }
      .st3 { fill: #ffbc23; }
      .st4 { fill: #ef95b0; }
      .st5 { fill: #1b313a; }
      .st6 { fill: #f7cd99; }
    </style>
  </defs>
  <path class="st5" d="M2.3,19c-1.7-.3-2.6-1.5-2.2-3.3.7-1.2,2.2-1.2,3.4-1.7,5.6-1.5,11.1-3.1,16.7-4.4,0,2.3-.5,4.6-1.2,6.7,1.3,2.4,1.5,5,1,7.6-5.9-1.5-11.8-3.3-17.7-5h0Z"/>
  <path class="st6" d="M19,16.4c.8-2.1,1.2-4.4,1.2-6.7,6.8-1.9,13.7-3.5,20.4-5.5,2.5-.8,5.2-1.3,7.9-1.6-.2.5-.6,1.6-.8,2.2,2,1.6,3.9,3.1,5.9,4.6.3.8.5,1.7.8,2.5-2.7.8-4.8,2.6-6.9,4.4,2,2.4,4.4,4.5,7.3,5.9-.3.4-.8,1.3-1.1,1.7-1.6,1.7-3.6,3.1-5.1,4.9.2,1,.3,2.1.6,3.1-9.8-2.3-19.6-5-29.2-8,.5-2.6.3-5.2-1-7.6h0Z"/>
  <path class="st1" d="M54.8,22.3c-2.8-1.4-5.2-3.5-7.3-5.9,2.1-1.8,4.2-3.6,6.9-4.4,32,.4,64.1.1,96.1.2,47.4,0,94.7,0,142.1,0,0,3.2,0,6.3,0,9.5-74.3,0-148.7,0-223,0-4.9,0-9.9-.5-14.8.6h0Z"/>
  <path class="st2" d="M47.7,4.8c.2-.5.6-1.6.8-2.2,2.2-1,4.4-2.7,7-2.5,79.1,0,158.1,0,237.2,0,0,3.1,0,6.1,0,9.2-79.7.1-159.4-.1-239,.1-2-1.5-4-3.1-5.9-4.6h0Z"/>
  <path class="st3" d="M49.2,32c-.2-1-.4-2-.6-3.1,1.5-1.9,3.5-3.2,5.1-4.9,4.9.6,9.9.3,14.8.4,74.7,0,149.5,0,224.2,0,0,3.1,0,6.2,0,9.3-2.4.1-4.7.2-7.1.2-41-.5-82.1.2-123.1-.2-12,.5-24-.2-36,.2-9,0-18,0-27,0-14.3.5-28.7-.5-43,0-2.6.3-5-1-7.3-1.9h0Z"/>
  <path class="st0" d="M54.4,11.9c-.3-.8-.5-1.6-.8-2.5,79.7-.3,159.3,0,239-.1,0-3.1,0-6.1,0-9.2,5.2-.4,10.4,0,15.5,0,.1,11.1,0,22.2,0,33.4-5.2.8-10.4.6-15.6.2,0-3.1,0-6.2,0-9.3-74.7-.1-149.5,0-224.2,0-4.9-.1-9.9.2-14.8-.4.3-.4.8-1.3,1.1-1.7,4.8-1.1,9.9-.5,14.8-.6,74.3,0,148.7,0,223,0,0-3.2.1-6.3,0-9.5-47.4,0-94.7,0-142.1,0-32.1,0-64.1.2-96.2-.2h0Z"/>
  <path class="st4" d="M308.3,33.5c0-11.1,0-22.2,0-33.4,9.8,0,19.6,0,29.4,0,2.5-.2,5,2,4.9,4.6.3,6.7,0,13.4.1,20.1,0,2.5.4,5.6-1.8,7.3-1.4,1.5-3.6,1.2-5.4,1.3-9,0-18.1-.2-27.2,0h0Z"/>
</svg>`;

export const CRAYON_SVG = `<svg id="crayon" xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 48.3 266.8">
  <defs>
    <style>
      .st0 { fill: #1d3843; }
      .st1 { fill: #1c3641; }
      .st2 { fill: #1e3841; }
      .st3 { fill: #0b293c; }
      .st4 { fill: #203943; }
      .st5 { fill: #faa427; }
      .st6 { fill: #fff; isolation: isolate; opacity: .4; }
    </style>
  </defs>
  <g id="_x3C_MainColor_x3E_">
    <path class="st5" d="M19,.8c4.3-1.1,10.8-1.7,13.2,2.9,4.4,15,7.7,30.4,12.1,45.4-2.5.4-5.1.6-7.7.6-10.9-.1-21.8,0-32.6,0,3.1-13.3,6.7-26.4,10-39.6.8-3.3,1-7.9,5-9.1h0Z"/>
    <path class="st5" d="M44.3,49.1c1.6,1,3.6,2.1,3.7,4.3.5,5.4.2,10.9.2,16.3-16,0-31.9.2-47.9,0,0-5.1-.3-10.2,0-15.2,0-2.1,1.4-4.7,3.7-4.8,10.9,0,21.8,0,32.6,0,2.6,0,5.1-.2,7.7-.6h0Z"/>
    <path class="st5" d="M0,92.3c.2-.3.5-1,.7-1.3,15.8.6,31.6-.2,47.3.3.2,42.4,0,84.8,0,127.1-16,.1-32,0-48-.2-.2-42,0-83.9,0-125.9H0Z"/>
    <path class="st5" d="M.2,239.8c16-.3,32,0,47.9-.2.1,6.9.3,13.8,0,20.7,0,3.7-3.8,6.6-7.4,6.4-10.4,0-20.8,0-31.1,0-2.6,0-5.5,0-7.4-2-1.8-1.6-2.1-4.2-2-6.4,0-6.2,0-12.4,0-18.6h0Z"/>
    <path class="st5" d="M0,225.6c16-.2,32.1-.2,48.1,0,0,2.3,0,4.6,0,6.9-16,.2-31.9,0-47.9,0,0-2.3-.2-4.6-.2-6.8h0Z"/>
    <path class="st5" d="M.2,77.1c16-.3,31.9-.3,47.9-.1,0,2.3,0,4.6,0,7-16,0-32,0-47.9,0,0-2.3,0-4.6,0-6.9h0Z"/>
  </g>
  <path class="st6" d="M44.8,49.1c1.6,1,3.6,2.1,3.7,4.3.5,5.4.2,10.9.2,16.3-16,0-31.9.2-47.9,0,0-5.1-.3-10.2,0-15.2,0-2.1,1.4-4.7,3.7-4.8,10.9,0,21.8,0,32.6,0,2.6,0,5.1-.2,7.7-.6h0Z"/>
  <path class="st6" d="M.7,77.1c16-.3,31.9-.3,47.9-.1,0,2.3,0,4.6,0,7-16,0-32,0-47.9,0,0-2.3,0-4.6,0-6.9h0Z"/>
  <path class="st6" d="M.6,92.4c.2-.3.5-1,.7-1.3,15.8.6,31.6-.2,47.3.3.2,42.4,0,84.8,0,127.1-16,.1-32,0-48-.2-.2-42,0-83.9,0-125.9h0Z"/>
  <path class="st6" d="M.6,225.7c16-.2,32.1-.2,48.1,0,0,2.3,0,4.6,0,6.9-16,.2-31.9,0-47.9,0,0-2.3-.1-4.6-.2-6.8h0Z"/>
  <path class="st6" d="M.6,239.9c16-.3,32,0,47.9-.2.1,6.9.3,13.8,0,20.7,0,3.7-3.8,6.6-7.4,6.4-10.4,0-20.8,0-31.1,0-2.6,0-5.5,0-7.4-2-1.8-1.6-2.1-4.2-2-6.4,0-6.2,0-12.4,0-18.6h0Z"/>
  <path class="st2" d="M.2,69.6c16,.3,31.9,0,47.9,0,0,2.4,0,4.8,0,7.2-16-.2-32-.2-47.9.1,0-2.5,0-4.9,0-7.4h0Z"/>
  <path class="st3" d="M.2,83.9c16,0,32,0,47.9,0,0,2.3-.1,4.6-.2,6.9-.6-1.8-1.3-3.5-1.9-5.3-14.8-.6-29.5,0-44.3.2,0,1.1,0,2.2,0,3.4,4.3,0,8.7.2,13,.9-4.7.4-9.5.7-14.2.6-1.4-1.8,0-4.5-.5-6.6h0Z"/>
  <path class="st4" d="M1.8,85.7c14.7-.2,29.5-.8,44.3-.2.6,1.8,1.2,3.5,1.9,5.3l.2.5c-15.8-.4-31.6.3-47.3-.3v-.4c4.6,0,9.4-.2,14.1-.6-4.3-.7-8.7-.9-13-.9,0-1.1,0-2.2,0-3.4h0Z"/>
  <path class="st1" d="M.2,218.2c16,.2,32,.3,48.1.2,0,2.4,0,4.7,0,7.1-16-.1-32.1-.1-48.1,0,0-2.5,0-4.9,0-7.4h0Z"/>
  <path class="st0" d="M.3,232.5c16,0,31.9.2,47.9,0-.1,2.4-.1,4.8,0,7.2-16,.1-32-.1-47.9.2,0-2.4,0-4.9.1-7.3h0Z"/>
</svg>`;

/**
 * Bake each SVG's own <style> class rules (.st0 { fill: ... }, etc.) into
 * per-element inline `style` attributes, then drop the <style> block.
 *
 * These SVGs all reuse the same generic Illustrator class names (st0, st1,
 * ...) with different colours per asset. Inlining more than one of them
 * into the same document at once (pencil + eraser + crayons, all on screen
 * together) means their <style> blocks collide globally -- the browser
 * applies whichever same-named rule appears last in the DOM to every
 * matching element, regardless of which SVG it "belongs" to. Baking to
 * inline styles sidesteps that entirely, since inline style always wins
 * and never leaks across elements.
 */
function bakeClassStyles(svgMarkup) {
  const styleMatch = svgMarkup.match(/<style>([\s\S]*?)<\/style>/);
  if (!styleMatch) return svgMarkup;
  const rules = {};
  const ruleRe = /\.([\w-]+)\s*\{([^}]*)\}/g;
  let m;
  while ((m = ruleRe.exec(styleMatch[1]))) {
    rules[m[1]] = m[2].trim().replace(/\s+/g, " ").replace(/;$/, "");
  }
  return svgMarkup
    .replace(/<defs>[\s\S]*?<\/defs>/, "")
    .replace(/class="([\w-\s]+)"/g, (_full, classAttr) => {
      const css = classAttr
        .trim()
        .split(/\s+/)
        .map((c) => rules[c])
        .filter(Boolean)
        .join(";");
      return css ? `style="${css}"` : "";
    });
}

/** Recolor only the paths inside <g id="_x3C_MainColor_x3E_"> via inline style (wins over the SVG's own class rules). */
export function recolorMainColor(svgMarkup, colorCss) {
  if (!colorCss) return svgMarkup;
  return svgMarkup.replace(
    /(<g\b[^>]*id="_x3C_MainColor_x3E_"[^>]*>)([\s\S]*?)(<\/g>)/,
    (_m, open, inner, close) => {
      const recolored = inner.replace(/<path\b([^>]*?)(\/?)>/g, (_pm, attrs, selfClose) => {
        if (/style\s*=/.test(attrs)) {
          return `<path${attrs.replace(/style="([^"]*)"/, (_sm, s) => `style="${s};fill:${colorCss}"`)}${selfClose}>`;
        }
        return `<path${attrs} style="fill:${colorCss}"${selfClose}>`;
      });
      return open + recolored + close;
    }
  );
}

/** Scale an SVG to fill its parent's height while keeping aspect ratio. */
function fitHeightSvg(svgMarkup, colorCss) {
  const recolored = recolorMainColor(bakeClassStyles(svgMarkup), colorCss);
  return recolored.replace(
    /<svg /,
    '<svg style="height:100%;width:auto;display:block;flex:none" '
  );
}

/**
 * Landscape tool art clipped on the left -- tip anchored to the right edge of
 * the button so the shaft can bleed off the sidebar.
 */
export function landscapeArtHtml(svgMarkup, colorCss) {
  return `<span class="tool-art-clip">${fitHeightSvg(svgMarkup, colorCss)}</span>`;
}

/**
 * Small, fully-contained crop of the same landscape art (tip visible, tail
 * cropped) for advanced mode's plain bordered buttons -- unlike
 * landscapeArtHtml, this never bleeds outside its own box.
 */
export function compactArtHtml(svgMarkup, colorCss) {
  return `<span class="tool-art-compact">${fitHeightSvg(svgMarkup, colorCss)}</span>`;
}

/** An upright crayon swatch sized by height, aspect ratio preserved. */
export function crayonSwatchHtml(colorCss) {
  return fitHeightSvg(CRAYON_SVG, colorCss);
}
