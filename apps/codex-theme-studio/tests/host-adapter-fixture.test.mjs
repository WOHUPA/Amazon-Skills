import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const registry = JSON.parse(await fs.readFile(path.join(root, "assets", "host-adapters.json"), "utf8"));
const renderer = await fs.readFile(path.join(root, "assets", "renderer-inject.js"), "utf8");
const fixture = JSON.parse(await fs.readFile(
  path.join(here, "fixtures", "windows-task-streaming.json"),
  "utf8",
));
const adapter = registry.adapters.find((item) => item.codexVersions.includes(fixture.codexVersion));
assert.ok(adapter, "The captured Codex version must have one exact host adapter.");

function matchIds(selectors) {
  const matches = new Set();
  for (const selector of selectors ?? []) {
    for (const id of fixture.selectorMatches[selector] ?? []) matches.add(id);
  }
  return matches;
}

const failures = [];
for (const [name, contract] of Object.entries(adapter.structureSignatures)) {
  const count = matchIds(contract.selectors).size;
  if (count < contract.min || count > contract.max) {
    failures.push(`STRUCTURE_SIGNATURE:${name}:${count}`);
  }
}

const scene = adapter.sceneContracts[fixture.scene];
assert.ok(scene, `Missing scene contract: ${fixture.scene}`);
for (const name of scene.requiredComponents) {
  const component = adapter.components[name];
  const count = matchIds(component?.selectors).size;
  if (!component || count < component.min || count > component.max) {
    failures.push(`COMPONENT_COUNT:${name}:${count}`);
  }
}

const expectedIconSlots = new Set(scene.expectedIconSlots ?? []);
for (const slot of expectedIconSlots) {
  const applied = fixture.iconsApplied.includes(slot);
  const matchingAlternates = Object.entries(adapter.iconSlotAlternates?.[slot] ?? {})
    .map(([state, contract]) => ({ state, ids: matchIds(contract) }))
    .filter((item) => item.ids.size > 0);
  if (applied && matchingAlternates.length) {
    failures.push(`ICON_PRIMARY_ALTERNATE_CONFLICT:${slot}`);
  } else if (!applied && matchingAlternates.length !== 1) {
    failures.push(`ICON_MISSING:${slot}`);
  } else if (!applied) {
    const ids = [...matchingAlternates[0].ids];
    if (ids.length !== 1) {
      failures.push(`ICON_ALTERNATE_AMBIGUOUS:${slot}`);
      continue;
    }
    const metric = fixture.iconMetrics?.[ids[0]];
    if (!metric || metric.width < 24 || metric.height < 24 || metric.pointerEvents === "none") {
      failures.push(`HIT_TARGET:${slot}`);
    }
  }
}

const sidebar = fixture.componentMetrics.sidebar;
const isClipped = (metric) => {
  const horizontalOverflow = metric.scrollWidth > metric.clientWidth + 1;
  const verticalOverflow = metric.scrollHeight > metric.clientHeight + 1;
  return (horizontalOverflow && ["hidden", "clip"].includes(metric.overflowX))
    || (verticalOverflow && ["hidden", "clip"].includes(metric.overflowY));
};
const clipped = isClipped(sidebar);
if (clipped !== sidebar.expectedClipped) failures.push(`CLIPPED_CONTENT:sidebar:${clipped}`);
assert.equal(isClipped({ ...sidebar, overflowX: "hidden" }), true,
  "Overflow hidden must remain a blocking crop.");
assert.equal(isClipped({ ...sidebar, overflowX: "auto" }), false,
  "A scrollable overflow container is not clipped content.");
if (!/horizontalClip\s*=\s*horizontalOverflow\s*&&\s*\["hidden",\s*"clip"\]\.includes\(style\.overflowX\)/.test(renderer)) {
  failures.push("RENDERER_VISIBLE_OVERFLOW_MISCLASSIFIED");
}
if (!renderer.includes('status: "native-alternate"') || !renderer.includes("clearIconSlot(slot)")) {
  failures.push("RENDERER_ICON_STATE_CONTRACT_MISSING");
}

assert.deepEqual(
  failures,
  [],
  "The live task/streaming fixture must satisfy its exact host, state, and geometry contracts.",
);

console.log("PASS: Windows task streaming fixture matches its versioned host and geometry contracts.");
