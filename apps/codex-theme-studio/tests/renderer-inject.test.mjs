import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const renderer = await fs.readFile(path.join(root, "assets", "renderer-inject.js"), "utf8");
const css = await fs.readFile(path.join(root, "assets", "dream-skin.css"), "utf8");
const hostAdapters = JSON.parse(await fs.readFile(path.join(root, "assets", "host-adapters.json"), "utf8"));
const injectorSource = await fs.readFile(path.join(root, "scripts", "injector.mjs"), "utf8");
const injector = path.join(root, "scripts", "injector.mjs");

assert.match(renderer, /const VERSION = "2\.2\.8"/);
assert.match(renderer, /const ADAPTER_PROTOCOL = "codex-theme-studio-v2"/);
assert.match(renderer, /--dream-reading-surface/,
  "Task readability must remain enforced by the trusted runtime.");
assert.doesNotMatch(renderer, /const ICON_TARGETS/,
  "Host selectors must live in the trusted versioned adapter registry.");
assert.ok(hostAdapters.adapters.some((item) => item.codexVersions.includes("26.715.8383.0")));
assert.ok(hostAdapters.adapters.some((item) => item.codexVersions.includes("26.721.4979.0")));
assert.ok(hostAdapters.adapters.some((item) => item.codexVersions.includes("26.727.4816.0")));
assert.ok(hostAdapters.adapters.every((item) => item.structureSignatures && item.sceneContracts));
assert.ok(hostAdapters.adapters.every((item) => item.structureSignatures.main.selectors
  .includes("[data-app-shell-main-content-layout]")),
"The main signature must use the verified stable Codex layout marker.");
assert.ok(hostAdapters.adapters.every((item) => item.structureSignatures.shell.selectors
  .includes("[data-app-shell-main-surface]")),
"The shell signature must accept the stable Codex 26.727 surface marker.");
assert.ok(hostAdapters.adapters.every((item) => !item.components.taskSidebar.selectors
  .includes("aside:not(.app-shell-left-panel)")),
"Generic asides must not be mistaken for the task sidebar on Codex 26.727.");
assert.match(css, /thread-scroll-container > div\.flex\.min-h-full\.shrink-0\.flex-col/,
  "The task reading plane must stay bound to the versioned thread adapter.");
assert.match(css, /button:hover:not\(:disabled\):not\(\[aria-disabled="true"\]\)/,
  "Every enabled native button needs a theme-owned hover state.");
assert.match(css, /button\[class~="bg-token-foreground"\]:hover/,
  "Primary actions need a distinct hover state instead of inheriting the neutral button color.");
assert.doesNotMatch(renderer, /alignHomePrompt|homePromptStates/,
  "Theme Studio must not dynamically translate the native home prompt.");
assert.doesNotMatch(renderer, /\.style\.setProperty\(["']translate["']/,
  "Native layout changes must come only from the versioned CSS adapter.");

for (const slot of ["newTask", "search", "projects", "history", "attach", "send", "settings", "skills"]) {
  assert.ok(hostAdapters.adapters.every((item) => Array.isArray(item.iconTargets[slot])),
    `Missing versioned semantic adapter for ${slot}`);
}
assert.ok(hostAdapters.adapters.every((item) => item.iconSlotAlternates?.send?.stop?.length),
  "Streaming Stop must be an explicit native alternate of the send semantic slot.");
assert.match(renderer, /status: "native-alternate"/,
  "Native alternate icon states must be auditable without theme-icon substitution.");
assert.match(renderer, /clearIconSlot\(slot\)/,
  "A disappearing primary icon target must restore its hidden native SVG.");
assert.match(renderer, /const effectiveMode = layoutAllowed \? config\.layout\.mode : "native"/,
  "Unknown hosts and incomplete layout receipts must downgrade to native.");
assert.doesNotMatch(injectorSource, /\['COMPLETE', 'PARTIAL'\]\.includes/,
  "PARTIAL must never be accepted as a successful live verification.");
assert.match(renderer, /URL\.createObjectURL\(new Blob/,
  "Large background and icon data URLs must be materialized as short renderer-local blob URLs.");
assert.match(renderer, /URL\.revokeObjectURL\(objectUrl\)/,
  "Renderer-local asset URLs must be revoked during cleanup.");
assert.match(renderer, /assetValue\(assetUrls\.homeBackground\)/);
assert.match(renderer, /assetValue\(assetUrls\.taskBackground\)/);
assert.doesNotMatch(renderer, /assetValue\(assets\.(?:homeBackground|taskBackground)\)/,
  "Multi-megabyte data URLs must never be stored directly in CSS custom properties.");
assert.match(renderer, /const assetAudit = buildAssetAudit\(root\)/,
  "Background binding must have live renderer evidence before apply can report success.");

const nativeVisualProperties = new Set([
  "color", "color-scheme", "accent-color", "caret-color", "background", "background-color",
  "background-image", "background-position", "background-size", "background-repeat", "background-attachment",
  "border-color", "border-top-color", "border-right-color", "border-bottom-color", "border-left-color",
  "border-radius", "box-shadow", "text-shadow", "filter", "backdrop-filter", "-webkit-backdrop-filter",
  "fill", "stroke", "outline-color", "text-decoration-color",
]);
const violations = [];
for (const block of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
  const selector = block[1].trim();
  const adapterOwned = /studio-layout-|studio-density-|studio-iconized|studio-semantic-icon|#codex-dream-skin-chrome/.test(selector);
  for (const declaration of block[2].matchAll(/(?:^|;)\s*([\w-]+)\s*:/g)) {
    const property = declaration[1].toLowerCase();
    if (!property.startsWith("--") && !nativeVisualProperties.has(property) && !adapterOwned) {
      violations.push(`${selector} -> ${property}`);
    }
  }
}
assert.deepEqual(violations, [], "Native layout properties must be confined to the allowlisted adapter selectors.");

const check = execFileSync(process.execPath, [
  injector,
  "--check-payload",
  "--codex-version", "26.715.8383.0",
  "--theme-dir", path.join(root, "presets", "immersive-dark"),
], { encoding: "utf8" });
const report = JSON.parse(check.trim());
assert.equal(report.pass, true);
assert.equal(report.version, "2.2.8");
assert.equal(report.themeId, "immersive-dark");
assert.equal(report.hostStatus, "COMPLETE");
assert.equal(report.hostAdapterId, "windows-26.715.8383.0");

const currentCheck = execFileSync(process.execPath, [
  injector,
  "--check-payload",
  "--codex-version", "26.721.4979.0",
  "--theme-dir", path.join(root, "presets", "immersive-dark"),
], { encoding: "utf8" });
const currentReport = JSON.parse(currentCheck.trim());
assert.equal(currentReport.pass, true);
assert.equal(currentReport.version, "2.2.8");
assert.equal(currentReport.hostStatus, "COMPLETE");
assert.equal(currentReport.hostAdapterId, "windows-26.715.8383.0");

const latestCheck = execFileSync(process.execPath, [
  injector,
  "--check-payload",
  "--codex-version", "26.727.4816.0",
  "--theme-dir", path.join(root, "presets", "immersive-dark"),
], { encoding: "utf8" });
const latestReport = JSON.parse(latestCheck.trim());
assert.equal(latestReport.pass, true);
assert.equal(latestReport.version, "2.2.8");
assert.equal(latestReport.hostStatus, "COMPLETE");
assert.equal(latestReport.hostAdapterId, "windows-26.715.8383.0");

console.log("PASS: Theme Pack payload, versioned host adapters, strict native fallback, and layout allowlist verified.");
