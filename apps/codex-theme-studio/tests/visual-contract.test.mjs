import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  evaluateLiveVerification,
  evaluateSceneGeometry,
  loadHostAdapterRegistry,
  resolveHostAdapter,
  validateEvidenceDirectory,
} from "../scripts/visual-contract.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const registryPath = path.join(root, "assets", "host-adapters.json");
const matrixPath = path.join(root, "references", "visual-regression-matrix.json");

const registry = await loadHostAdapterRegistry(registryPath);
const known = resolveHostAdapter(registry, "26.715.8383.0");
assert.equal(known.status, "COMPLETE");
assert.equal(known.adapter.id, "windows-26.715.8383.0");
assert.equal(known.adapter.layoutMatrix.native.status, "COMPLETE");
for (const mode of ["compact", "cinematic", "focus"]) {
  assert.notEqual(known.adapter.layoutMatrix[mode].status, "COMPLETE",
    `${mode} must remain experimental until every required scene is signed off.`);
}

const unknown = resolveHostAdapter(registry, "26.999.1.0");
assert.equal(unknown.status, "BLOCKED");
assert.equal(unknown.effectiveLayout, "native");

const safeRect = { x: 10, y: 10, width: 80, height: 32, right: 90, bottom: 42 };
const overlap = evaluateSceneGeometry({
  viewport: { width: 800, height: 600 },
  documentOverflow: { x: false, y: false },
  components: {
    icon: { count: 1, rects: [{ ...safeRect, x: 20, right: 60, width: 40 }] },
    label: { count: 1, rects: [{ ...safeRect, x: 40, right: 100, width: 60 }] },
  },
  nonOverlapPairs: [["icon", "label"]],
});
assert.equal(overlap.status, "BLOCKED");
assert.ok(overlap.failures.some((item) => item.code === "OVERLAP"));

for (const fixture of [
  { name: "horizontal overflow", documentOverflow: { x: true, y: false }, component: safeRect },
  { name: "out of bounds", documentOverflow: { x: false, y: false }, component: { ...safeRect, x: -3, right: 77 } },
  { name: "cropped", documentOverflow: { x: false, y: false }, component: safeRect, clipped: true },
]) {
  const report = evaluateSceneGeometry({
    viewport: { width: 800, height: 600 },
    documentOverflow: fixture.documentOverflow,
    components: { target: { count: 1, rects: [fixture.component], clipped: fixture.clipped ?? false } },
    nonOverlapPairs: [],
  });
  assert.equal(report.status, "BLOCKED", fixture.name);
}

const sceneMismatch = evaluateSceneGeometry({
  viewport: { width: 800, height: 600 },
  documentOverflow: { x: false, y: false },
  components: {
    composer: { count: 0, min: 1, max: 2, rects: [] },
  },
  nonOverlapPairs: [],
});
assert.equal(sceneMismatch.status, "BLOCKED");
assert.ok(sceneMismatch.failures.some((item) => item.code === "MISSING_COMPONENT"));

const ineffectiveLayout = evaluateSceneGeometry({
  viewport: { width: 800, height: 600 },
  documentOverflow: { x: false, y: false },
  components: { target: { count: 1, rects: [safeRect] } },
  nonOverlapPairs: [],
  layoutEffect: { status: "PARTIAL", expected: 240, actual: 275 },
});
assert.equal(ineffectiveLayout.status, "BLOCKED");
assert.ok(ineffectiveLayout.failures.some(
  (item) => item.code === "CONFIG_DIMENSION_NOT_EFFECTIVE",
));

const partial = evaluateLiveVerification({
  installed: true,
  versionMatches: true,
  stylePresent: true,
  chromePresent: true,
  chromePointerEvents: "none",
  adapterStatus: "PARTIAL",
  sceneAudit: { status: "COMPLETE" },
  geometryAudit: { status: "COMPLETE", failures: [] },
});
assert.equal(partial.pass, false, "PARTIAL can never be a publish-success state.");

const incompleteEvidenceMode = evaluateLiveVerification({
  installed: true,
  versionMatches: true,
  stylePresent: true,
  chromePresent: true,
  chromePointerEvents: "none",
  adapterStatus: "COMPLETE",
  sceneAudit: { status: "COMPLETE" },
  geometryAudit: { status: "COMPLETE", failures: [] },
  contrastAudit: { status: "COMPLETE", failures: [] },
  requireSemanticEvidence: true,
  stylesEvidence: { status: "PARTIAL" },
});
assert.equal(incompleteEvidenceMode.pass, false);
assert.ok(incompleteEvidenceMode.verificationFailures.includes(
  "SEMANTIC_STATE_EVIDENCE_INCOMPLETE",
));

const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "codex-theme-evidence-"));
try {
  const invalidRegistry = JSON.parse(JSON.stringify(registry));
  invalidRegistry.adapters[0].iconSlotAlternates.send.stop = [];
  const invalidRegistryPath = path.join(temporary, "invalid-host-adapters.json");
  await fs.writeFile(invalidRegistryPath, JSON.stringify(invalidRegistry), "utf8");
  await assert.rejects(
    loadHostAdapterRegistry(invalidRegistryPath),
    /must be a non-empty selector array/,
    "空的原生互斥状态 selector 不得进入受信任适配器。",
  );

  const missing = await validateEvidenceDirectory({
    evidenceDir: temporary,
    matrixPath,
    profile: "pr",
  });
  assert.equal(missing.status, "PARTIAL");
  assert.equal(missing.publishable, false);
  assert.ok(missing.missing.length > 0);

  await fs.writeFile(
    path.join(temporary, "pr__immersive-dark__home__narrow-100.png"),
    "not a png",
  );
  const invalid = await validateEvidenceDirectory({
    evidenceDir: temporary,
    matrixPath,
    profile: "pr",
  });
  assert.equal(invalid.status, "BLOCKED");
  assert.equal(invalid.publishable, false);
  assert.ok(invalid.invalid.some((item) => item.issue === "INVALID_PNG"));
} finally {
  await fs.rm(temporary, { recursive: true, force: true });
}

console.log("PASS: strict host, geometry, scene, and evidence contracts reject every fake-green state.");
