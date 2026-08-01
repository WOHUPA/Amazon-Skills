import fs from "node:fs/promises";
import path from "node:path";

const COMPLETE = "COMPLETE";
const PARTIAL = "PARTIAL";
const BLOCKED = "BLOCKED";

async function readJson(filePath) {
  return JSON.parse(await fs.readFile(filePath, "utf8"));
}

function assertObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
}

export async function loadHostAdapterRegistry(filePath) {
  const registry = await readJson(filePath);
  assertObject(registry, "host adapter registry");
  if (registry.schemaVersion !== 1 || !Array.isArray(registry.adapters)) {
    throw new Error("Unsupported host adapter registry schema");
  }
  const ids = new Set();
  for (const adapter of registry.adapters) {
    assertObject(adapter, "host adapter");
    if (typeof adapter.id !== "string" || !adapter.id || ids.has(adapter.id)) {
      throw new Error("Host adapter IDs must be unique non-empty strings");
    }
    ids.add(adapter.id);
    if (!Array.isArray(adapter.codexVersions) || adapter.codexVersions.length === 0) {
      throw new Error(`Host adapter ${adapter.id} has no exact Codex versions`);
    }
    for (const field of ["structureSignatures", "layoutMatrix", "components", "iconTargets", "sceneContracts"]) {
      assertObject(adapter[field], `host adapter ${adapter.id}.${field}`);
    }
    for (const [slot, selectors] of Object.entries(adapter.iconTargets)) {
      if (!Array.isArray(selectors) || selectors.length === 0
          || selectors.some((selector) => typeof selector !== "string" || !selector)) {
        throw new Error(`Host adapter ${adapter.id}.iconTargets.${slot} must be a non-empty selector array`);
      }
    }
    if (adapter.iconSlotAlternates !== undefined) {
      assertObject(adapter.iconSlotAlternates, `host adapter ${adapter.id}.iconSlotAlternates`);
      for (const [slot, states] of Object.entries(adapter.iconSlotAlternates)) {
        if (!Object.hasOwn(adapter.iconTargets, slot)) {
          throw new Error(`Host adapter ${adapter.id} alternate references unknown icon slot: ${slot}`);
        }
        assertObject(states, `host adapter ${adapter.id}.iconSlotAlternates.${slot}`);
        for (const [state, selectors] of Object.entries(states)) {
          if (!Array.isArray(selectors) || selectors.length === 0
              || selectors.some((selector) => typeof selector !== "string" || !selector)) {
            throw new Error(
              `Host adapter ${adapter.id}.iconSlotAlternates.${slot}.${state} must be a non-empty selector array`,
            );
          }
        }
      }
    }
  }
  return registry;
}

export function resolveHostAdapter(registry, codexVersion) {
  const version = typeof codexVersion === "string" ? codexVersion.trim() : "";
  const matches = registry.adapters.filter((adapter) => adapter.codexVersions.includes(version));
  if (matches.length !== 1) {
    return {
      status: BLOCKED,
      reason: matches.length ? "AMBIGUOUS_HOST_VERSION" : "UNKNOWN_HOST_VERSION",
      codexVersion: version || null,
      adapter: null,
      effectiveLayout: registry.fallback?.layout ?? "native",
    };
  }
  return {
    status: COMPLETE,
    reason: null,
    codexVersion: version,
    adapter: matches[0],
    effectiveLayout: "native",
  };
}

function normalizedRect(rect) {
  if (!rect || typeof rect !== "object") return null;
  const x = Number(rect.x);
  const y = Number(rect.y);
  const width = Number(rect.width);
  const height = Number(rect.height);
  if (![x, y, width, height].every(Number.isFinite)) return null;
  return {
    x,
    y,
    width,
    height,
    right: Number.isFinite(Number(rect.right)) ? Number(rect.right) : x + width,
    bottom: Number.isFinite(Number(rect.bottom)) ? Number(rect.bottom) : y + height,
  };
}

function intersects(first, second) {
  return first.x < second.right && first.right > second.x
    && first.y < second.bottom && first.bottom > second.y;
}

export function evaluateSceneGeometry(input) {
  const failures = [];
  const viewport = input?.viewport ?? {};
  const viewportWidth = Number(viewport.width);
  const viewportHeight = Number(viewport.height);
  if (!Number.isFinite(viewportWidth) || !Number.isFinite(viewportHeight)
      || viewportWidth <= 0 || viewportHeight <= 0) {
    failures.push({ code: "INVALID_VIEWPORT", component: null });
  }
  if (input?.documentOverflow?.x) {
    failures.push({ code: "HORIZONTAL_OVERFLOW", component: "document" });
  }

  const components = input?.components && typeof input.components === "object" ? input.components : {};
  for (const [name, component] of Object.entries(components)) {
    const minimum = Number.isInteger(component?.min) ? component.min : 1;
    const maximum = Number.isInteger(component?.max) ? component.max : Number.POSITIVE_INFINITY;
    const count = Number.isInteger(component?.count) ? component.count : 0;
    if (count < minimum) failures.push({ code: "MISSING_COMPONENT", component: name, expected: minimum, actual: count });
    if (count > maximum) failures.push({ code: "UNEXPECTED_COMPONENT_COUNT", component: name, expected: maximum, actual: count });
    if (component?.clipped) failures.push({ code: "CLIPPED_CONTENT", component: name });
    if (component?.hitTargetOk === false) failures.push({ code: "HIT_TARGET_MISALIGNED", component: name });
    if (component?.iconTextOverlap) failures.push({ code: "ICON_TEXT_OVERLAP", component: name });
    for (const rawRect of component?.rects ?? []) {
      const rect = normalizedRect(rawRect);
      if (!rect) {
        failures.push({ code: "INVALID_RECT", component: name });
        continue;
      }
      if (rect.width <= 0 || rect.height <= 0) failures.push({ code: "ZERO_SIZE", component: name });
      if (Number.isFinite(viewportWidth) && Number.isFinite(viewportHeight)
          && (rect.x < -1 || rect.y < -1 || rect.right > viewportWidth + 1 || rect.bottom > viewportHeight + 1)) {
        failures.push({ code: "OUT_OF_BOUNDS", component: name, rect });
      }
    }
  }

  for (const pair of input?.nonOverlapPairs ?? []) {
    if (!Array.isArray(pair) || pair.length !== 2) continue;
    const [firstName, secondName] = pair;
    const firstRects = (components[firstName]?.rects ?? []).map(normalizedRect).filter(Boolean);
    const secondRects = (components[secondName]?.rects ?? []).map(normalizedRect).filter(Boolean);
    if (firstRects.some((first) => secondRects.some((second) => intersects(first, second)))) {
      failures.push({ code: "OVERLAP", components: [firstName, secondName] });
    }
  }

  if (input?.layoutEffect?.status && input.layoutEffect.status !== COMPLETE) {
    failures.push({ code: "CONFIG_DIMENSION_NOT_EFFECTIVE", details: input.layoutEffect });
  }
  return { status: failures.length ? BLOCKED : COMPLETE, failures };
}

export function evaluateLiveVerification(result) {
  const failures = [];
  if (!result?.installed) failures.push("SKIN_NOT_INSTALLED");
  if (!result?.versionMatches) failures.push("VERSION_MISMATCH");
  if (!result?.stylePresent) failures.push("STYLE_MISSING");
  if (!result?.chromePresent || result?.chromePointerEvents !== "none") failures.push("CHROME_INTERCEPTS_INPUT");
  if (result?.adapterStatus !== COMPLETE) failures.push(`ADAPTER_${result?.adapterStatus ?? "MISSING"}`);
  if (result?.sceneAudit?.status !== COMPLETE) failures.push("SCENE_CONTRACT_FAILED");
  if (result?.geometryAudit?.status !== COMPLETE) failures.push("GEOMETRY_CONTRACT_FAILED");
  if (result?.contrastAudit?.status && result.contrastAudit.status !== COMPLETE) failures.push("CONTRAST_CONTRACT_FAILED");
  if (result?.visualAssetsRequested && result?.assetAudit?.status !== COMPLETE) {
    failures.push("VISUAL_ASSET_BINDING_FAILED");
  }
  if (result?.requireSemanticEvidence && result?.stylesEvidence?.status !== COMPLETE) {
    failures.push("SEMANTIC_STATE_EVIDENCE_INCOMPLETE");
  }
  return { ...result, pass: failures.length === 0, verificationFailures: failures };
}

export function evaluateRuntimeAcceptance(result) {
  const strict = evaluateLiveVerification(result);
  if (strict.pass) {
    return {
      ...strict,
      runtimeAccepted: true,
      runtimeStatus: COMPLETE,
      runtimeAcceptanceReason: null,
    };
  }

  const sceneErrors = Array.isArray(strict?.sceneAudit?.errors)
    ? strict.sceneAudit.errors : [];
  const compatibleNative = strict?.installed === true
    && strict?.versionMatches === true
    && strict?.stylePresent === true
    && strict?.chromePresent === true
    && strict?.chromePointerEvents === "none"
    && strict?.requestedLayoutMode === "native"
    && strict?.layoutMode === "native"
    && strict?.adapterStatus === BLOCKED
    && strict?.adapterReason === "UNKNOWN_HOST_VERSION"
    && strict?.sceneAudit?.status === BLOCKED
    && sceneErrors.length === 1
    && sceneErrors[0] === "UNKNOWN_HOST_VERSION"
    && strict?.geometryAudit?.status === COMPLETE
    && strict?.contrastAudit?.status === COMPLETE
    && strict?.visualAssetsRequested !== true
    && strict?.requireSemanticEvidence !== true
    && strict.verificationFailures.every((failure) =>
      failure === "ADAPTER_BLOCKED" || failure === "SCENE_CONTRACT_FAILED");

  return {
    ...strict,
    runtimeAccepted: compatibleNative,
    runtimeStatus: compatibleNative ? "COMPATIBLE_NATIVE" : BLOCKED,
    runtimeAcceptanceReason: compatibleNative ? "UNKNOWN_HOST_VERSION" : null,
  };
}

export function evidenceBaseName(profile, theme, scene, variant) {
  return `${profile}__${theme}__${scene}__${variant}`;
}

function buildCases(profileName, profile) {
  const cases = [];
  for (const theme of profile.themes ?? []) {
    for (const scene of profile.scenes ?? []) {
      for (const variant of profile.variants ?? []) {
        cases.push({ profile: profileName, theme, scene, variant: variant.id });
      }
    }
  }
  return cases;
}

function validateSemanticStateMatrix(matrix) {
  assertObject(matrix.semanticStateRequirements, "semanticStateRequirements");
  assertObject(matrix.sceneStateRequirements, "sceneStateRequirements");
  const covered = {};
  for (const sceneRequirements of Object.values(matrix.sceneStateRequirements)) {
    assertObject(sceneRequirements, "scene state requirements");
    for (const [group, states] of Object.entries(sceneRequirements)) {
      if (!Array.isArray(states)) throw new Error(`Semantic states for ${group} must be an array`);
      covered[group] ??= new Set();
      for (const state of states) covered[group].add(state);
    }
  }
  for (const [group, states] of Object.entries(matrix.semanticStateRequirements)) {
    if (!Array.isArray(states)) throw new Error(`Semantic states for ${group} must be an array`);
    const missing = states.filter((state) => !covered[group]?.has(state));
    if (missing.length) {
      throw new Error(`Semantic state matrix does not cover ${group}: ${missing.join(", ")}`);
    }
  }
}

async function validateArtifact(filePath, suffix) {
  try {
    const bytes = await fs.readFile(filePath);
    if (suffix === "png") {
      const signature = bytes.subarray(0, 8).toString("hex");
      return signature === "89504e470d0a1a0a" ? null : "INVALID_PNG";
    }
    const parsed = JSON.parse(bytes.toString("utf8"));
    if (!parsed || typeof parsed !== "object" || parsed.status !== COMPLETE) return "NON_COMPLETE_JSON";
    if (suffix === "rects.json"
        && (parsed.sceneAudit?.status !== COMPLETE || parsed.geometryAudit?.status !== COMPLETE)) {
      return "INCOMPLETE_GEOMETRY_EVIDENCE";
    }
    if (suffix === "styles.json"
        && (parsed.stylesEvidence?.status !== COMPLETE
          || parsed.stylesEvidence?.semanticStates?.status !== COMPLETE
          || !parsed.stylesEvidence?.semanticStates?.stateStyles
          || !parsed.stylesEvidence?.components)) {
      return "INCOMPLETE_STYLE_EVIDENCE";
    }
    if (suffix === "contrast.json"
        && (parsed.contrastAudit?.status !== COMPLETE || !parsed.contrastAudit?.ratios)) {
      return "INCOMPLETE_CONTRAST_EVIDENCE";
    }
    return null;
  } catch (error) {
    if (error?.code === "ENOENT") return "MISSING";
    return "INVALID_ARTIFACT";
  }
}

export async function validateEvidenceDirectory({ evidenceDir, matrixPath, profile }) {
  const matrix = await readJson(matrixPath);
  if (matrix.schemaVersion !== 1 || !matrix.profiles?.[profile]) {
    throw new Error(`Unknown visual regression profile: ${profile}`);
  }
  validateSemanticStateMatrix(matrix);
  for (const scene of matrix.profiles[profile].scenes ?? []) {
    if (!matrix.sceneStateRequirements[scene]) {
      throw new Error(`Visual scene has no semantic-state contract: ${scene}`);
    }
  }
  const missing = [];
  const invalid = [];
  const cases = buildCases(profile, matrix.profiles[profile]);
  for (const item of cases) {
    const base = evidenceBaseName(item.profile, item.theme, item.scene, item.variant);
    for (const suffix of matrix.artifactSuffixes ?? []) {
      const filePath = path.join(evidenceDir, `${base}.${suffix}`);
      const issue = await validateArtifact(filePath, suffix);
      if (issue === "MISSING") missing.push(path.basename(filePath));
      else if (issue) invalid.push({ file: path.basename(filePath), issue });
    }
  }
  const status = invalid.length ? BLOCKED : missing.length ? PARTIAL : COMPLETE;
  return {
    schemaVersion: 1,
    reportType: "codex-theme-visual-gate",
    profile,
    status,
    publishable: status === COMPLETE,
    expectedCases: cases.length,
    expectedArtifacts: cases.length * (matrix.artifactSuffixes?.length ?? 0),
    missing,
    invalid,
  };
}

export { BLOCKED, COMPLETE, PARTIAL };
