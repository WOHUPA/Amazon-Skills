((cssText, rawAssets, rawConfig, rawRuntime) => {
  const STATE_KEY = "__CODEX_DREAM_SKIN_STATE__";
  const STYLE_ID = "codex-dream-skin-style";
  const CHROME_ID = "codex-dream-skin-chrome";
  const VERSION = "2.2.8";
  const ADAPTER_PROTOCOL = "codex-theme-studio-v2";
  const COMPLETE = "COMPLETE";
  const PARTIAL = "PARTIAL";
  const BLOCKED = "BLOCKED";
  // Codex's current native sidebar controls are 21.59 CSS px at 125% scaling.
  // Keep the audit above the icon glyph size without rejecting untouched host controls.
  const MIN_NATIVE_HIT_TARGET = 20;

  const isHitTargetInteractive = (node) => {
    for (let candidate = node; candidate && candidate !== document.body; candidate = candidate.parentElement) {
      if (candidate.matches?.("button, [role=button], a[href], input, textarea, select, [tabindex]")) {
        return getComputedStyle(candidate).pointerEvents !== "none" && candidate.getAttribute("aria-disabled") !== "true";
      }
    }
    return getComputedStyle(node).pointerEvents !== "none";
  };

  const isInViewport = (rect) => rect.right > 0 && rect.bottom > 0
    && rect.x < innerWidth && rect.y < innerHeight;

  const hasUsableHitTarget = (node, rect) => !isInViewport(rect)
    || (rect.width >= MIN_NATIVE_HIT_TARGET && rect.height >= MIN_NATIVE_HIT_TARGET
      && isHitTargetInteractive(node));
  const ROOT_CLASSES = [
    "codex-dream-skin", "dream-theme-light", "dream-theme-dark",
    "dream-focus-left", "dream-focus-center", "dream-focus-right",
    "dream-safe-left", "dream-safe-center", "dream-safe-right", "dream-safe-none",
    "dream-task-ambient", "dream-task-banner", "dream-task-off",
    "studio-layout-native", "studio-layout-compact", "studio-layout-cinematic", "studio-layout-focus",
    "studio-density-compact", "studio-density-comfortable", "studio-density-spacious",
  ];
  const ROOT_PROPERTIES = [
    "--dream-art", "--dream-task-art", "--dream-art-position", "--dream-accent",
    "--dream-accent-ink", "--dream-canvas", "--dream-surface", "--dream-surface-raised",
    "--dream-sidebar", "--dream-header", "--dream-text", "--dream-muted", "--dream-line",
    "--dream-glass-panel", "--dream-glass-dialog", "--dream-composer-surface",
    "--dream-reading-surface", "--dream-panel-filter", "--dream-dialog-filter",
    "--dream-shadow", "--studio-sidebar-width", "--studio-content-max", "--studio-composer-offset",
    "--studio-radius", "--studio-home-intensity", "--studio-task-intensity",
    "--studio-home-wash", "--studio-task-wash",
    "--color-token-foreground", "--color-token-text-primary", "--color-text-foreground",
    "--color-text-foreground-secondary", "--color-text-foreground-tertiary",
    "--color-token-conversation-body", "--color-token-description-foreground",
    "--color-token-disabled-foreground", "--color-token-main-surface-primary",
    "--color-token-side-bar-background", "--vscode-sideBar-background",
    "--color-token-input-background", "--vscode-input-background",
    "--color-token-menu-background", "--vscode-menu-background",
    "--color-token-dropdown-background", "--vscode-dropdown-background",
    "--color-token-border", "--color-token-border-default", "--color-token-input-border",
    "--vscode-input-border", "--vscode-sideBar-border",
    "--color-token-list-hover-background", "--color-token-list-active-selection-background",
    "--color-token-text-preformat-background", "--color-token-text-code-block-background",
    "--color-token-button-background", "--color-token-button-foreground",
    "--vscode-foreground", "--vscode-editor-foreground",
  ];
  const ICON_CLASS = "studio-iconized";
  const ICON_NODE_CLASS = "studio-semantic-icon";
  const ICON_OVERLAY_CLASS = "studio-semantic-icon-overlay";
  const NATIVE_ICON_HIDDEN_CLASS = "studio-native-icon-hidden";
  const HOME_UTILITY_CLASS = "dream-home-utility";
  const installToken = {};
  const objectUrls = new Set();
  const materializedByDataUrl = new Map();
  const semanticObservationCache = {
    button: new Set(),
    menu: new Set(),
    composer: new Set(),
    sidebar: new Set(),
    overlay: new Set(),
  };
  const semanticStyleCache = {
    button: {},
    menu: {},
    composer: {},
    sidebar: {},
    overlay: {},
  };
  let observer = null;
  let applying = false;
  window.__CODEX_DREAM_SKIN_DISABLED__ = false;

  const clamp = (value, min, max, fallback) => {
    const number = Number(value);
    return Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : fallback;
  };
  const text = (value, fallback) => typeof value === "string" && value ? value : fallback;
  const cssColor = (value, fallback) => /^#[\da-f]{6}$/i.test(value || "") ? value : fallback;
  const runtime = rawRuntime && typeof rawRuntime === "object" ? rawRuntime : {};
  const hostAdapter = runtime.hostAdapter && typeof runtime.hostAdapter === "object"
    ? runtime.hostAdapter : null;
  const assets = rawAssets && typeof rawAssets === "object" ? rawAssets : {};
  const config = (() => {
    const value = rawConfig && typeof rawConfig === "object" ? rawConfig : {};
    const isV2 = value.schemaVersion === 2;
    const palette = value.palette && typeof value.palette === "object" ? value.palette : {};
    const materials = value.materials && typeof value.materials === "object" ? value.materials : {};
    const layout = value.layout && typeof value.layout === "object" ? value.layout : {};
    const art = value.art && typeof value.art === "object" ? value.art : {};
    const appearance = ["light", "dark", "auto"].includes(value.appearance) ? value.appearance : "auto";
    const mode = ["native", "compact", "cinematic", "focus"].includes(layout.mode)
      ? layout.mode : "native";
    return {
      id: text(value.id, "legacy-theme"),
      name: text(value.name, "Codex Theme Studio"),
      isV2,
      appearance,
      adapterRequested: isV2 && value.compatibility?.rendererFingerprint === ADAPTER_PROTOCOL,
      palette: {
        accent: cssColor(palette.accent, "#7C8CFF"),
        accentContrast: cssColor(palette.accentContrast, "#FFFFFF"),
        canvas: cssColor(palette.canvas, appearance === "light" ? "#EDF3F8" : "#090B10"),
        surface: cssColor(palette.surface, appearance === "light" ? "#FFFFFF" : "#151923"),
        elevated: cssColor(palette.surfaceElevated, appearance === "light" ? "#F8FBFD" : "#202633"),
        text: cssColor(palette.text, appearance === "light" ? "#17202B" : "#F6F8FC"),
        muted: cssColor(palette.textMuted, appearance === "light" ? "#586779" : "#AAB4C4"),
        border: cssColor(palette.border, appearance === "light" ? "#CCD7E3" : "#354052"),
        menu: cssColor(palette.menu, appearance === "light" ? "#F5F9FC" : "#111722"),
        panel: cssColor(palette.panel, appearance === "light" ? "#FFFFFF" : "#151B27"),
        composer: cssColor(palette.composer, appearance === "light" ? "#FFFFFF" : "#1A2230"),
        dialog: cssColor(palette.dialog, appearance === "light" ? "#FFFFFF" : "#202938"),
      },
      materials: {
        panelOpacity: clamp(materials.panelOpacity, 0.25, 1, 0.52),
        composerOpacity: clamp(materials.composerOpacity, 0.25, 1, 0.60),
        dialogOpacity: clamp(materials.dialogOpacity, 0.25, 1, 0.68),
        radius: clamp(materials.radius, 0, 28, 16),
        blur: clamp(materials.blur, 0, 24, 0),
        shadow: ["none", "soft", "strong"].includes(materials.shadow) ? materials.shadow : "soft",
      },
      layout: {
        mode,
        sidebarWidth: clamp(layout.sidebarWidth, 200, 320, 240),
        contentMaxWidth: clamp(layout.contentMaxWidth, 720, 1280, 920),
        composerOffset: clamp(layout.composerOffset, -48, 48, 0),
        density: ["compact", "comfortable", "spacious"].includes(layout.density)
          ? layout.density : "comfortable",
      },
      art: {
        focusX: clamp(art.focusX, 0, 1, 0.7),
        focusY: clamp(art.focusY, 0, 1, 0.4),
        safeArea: ["left", "right", "center", "none"].includes(art.safeArea)
          ? art.safeArea : "left",
        homeIntensity: clamp(art.homeIntensity, 0, 1, 1),
        taskIntensity: clamp(art.taskIntensity, 0, 1, 0.3),
      },
    };
  })();

  const previous = window[STATE_KEY];
  previous?.cleanup?.();
  window.__CODEX_DREAM_SKIN_DISABLED__ = false;
  const materializeAssetUrl = (dataUrl) => {
    if (!dataUrl) return null;
    if (typeof dataUrl !== "string") throw new Error("Theme asset must be a data URL");
    if (materializedByDataUrl.has(dataUrl)) return materializedByDataUrl.get(dataUrl);
    const match = /^data:([^;,]+);base64,([\s\S]+)$/.exec(dataUrl);
    if (!match) throw new Error("Theme asset data URL is invalid");
    const binary = atob(match[2]);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    const objectUrl = URL.createObjectURL(new Blob([bytes], { type: match[1] }));
    objectUrls.add(objectUrl);
    materializedByDataUrl.set(dataUrl, objectUrl);
    return objectUrl;
  };
  // Chromium drops multi-megabyte CSS custom-property values. Keep the CDP payload
  // self-contained, then bind short renderer-local blob URLs to the visual layer.
  const assetUrls = (() => {
    try {
      return {
        homeBackground: materializeAssetUrl(assets.homeBackground),
        taskBackground: materializeAssetUrl(assets.taskBackground),
        icons: Object.fromEntries(
          Object.entries(assets.icons || {}).map(([slot, dataUrl]) => [slot, materializeAssetUrl(dataUrl)]),
        ),
      };
    } catch (error) {
      for (const objectUrl of objectUrls) URL.revokeObjectURL(objectUrl);
      objectUrls.clear();
      materializedByDataUrl.clear();
      throw error;
    }
  })();
  const visualAssetsRequested = Boolean(
    assets.homeBackground || assets.taskBackground
      || Object.values(assets.icons || {}).some(Boolean),
  );

  const queryAll = (selectors) => {
    const nodes = new Set();
    for (const selector of Array.isArray(selectors) ? selectors : []) {
      try {
        document.querySelectorAll(selector).forEach((node) => nodes.add(node));
      } catch {
        // A malformed selector is a failed adapter signature, never a runtime escape hatch.
      }
    }
    return [...nodes];
  };
  const visibleNodes = (selectors) => queryAll(selectors).filter((node) => {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return rect.width > 0 && rect.height > 0
      && style.display !== "none" && style.visibility !== "hidden";
  });
  const rectOf = (node) => {
    const rect = node.getBoundingClientRect();
    return {
      x: Math.round(rect.x * 100) / 100,
      y: Math.round(rect.y * 100) / 100,
      width: Math.round(rect.width * 100) / 100,
      height: Math.round(rect.height * 100) / 100,
      right: Math.round(rect.right * 100) / 100,
      bottom: Math.round(rect.bottom * 100) / 100,
    };
  };
  const intersects = (first, second) => first.x < second.right && first.right > second.x
    && first.y < second.bottom && first.bottom > second.y;

  const detectAppearance = () => {
    if (config.appearance !== "auto") return config.appearance;
    const root = document.documentElement;
    const hint = `${root.className} ${root.getAttribute("data-theme") || ""}`.toLowerCase();
    if (hint.includes("dark")) return "dark";
    if (hint.includes("light")) return "light";
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };

  const adapterProbe = () => {
    if (!config.adapterRequested) {
      return { status: BLOCKED, reason: "ADAPTER_NOT_REQUESTED", supported: false, signatures: {} };
    }
    if (!hostAdapter || runtime.hostStatus !== COMPLETE) {
      return {
        status: BLOCKED,
        reason: runtime.hostReason || "UNKNOWN_HOST_VERSION",
        supported: false,
        signatures: {},
      };
    }
    const signatures = {};
    let supported = true;
    for (const [name, contract] of Object.entries(hostAdapter.structureSignatures || {})) {
      const count = visibleNodes(contract.selectors).length;
      const matched = count >= contract.min && count <= contract.max;
      signatures[name] = { count, min: contract.min, max: contract.max, matched };
      supported = supported && matched;
    }
    return {
      status: supported ? COMPLETE : PARTIAL,
      reason: supported ? null : "STRUCTURE_SIGNATURE_MISMATCH",
      supported,
      signatures,
    };
  };

  const clearIcons = () => {
    document.querySelectorAll(`.${ICON_CLASS}`).forEach((node) => node.classList.remove(ICON_CLASS));
    document.querySelectorAll(`.${NATIVE_ICON_HIDDEN_CLASS}`).forEach((node) => {
      node.classList.remove(NATIVE_ICON_HIDDEN_CLASS);
    });
    document.querySelectorAll(`.${ICON_NODE_CLASS}`).forEach((node) => node.remove());
  };

  const clearIconSlot = (slot) => {
    document.querySelectorAll(`.${ICON_NODE_CLASS}[data-studio-icon="${slot}"]`).forEach((node) => {
      const target = node.parentElement;
      target?.classList.remove(ICON_CLASS);
      target?.querySelectorAll(`svg.${NATIVE_ICON_HIDDEN_CLASS}`).forEach((nativeIcon) => {
        nativeIcon.classList.remove(NATIVE_ICON_HIDDEN_CLASS);
      });
      node.remove();
    });
  };

  const textRects = (target) => {
    const rectangles = [];
    const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.textContent?.trim() || node.parentElement?.closest(`.${ICON_NODE_CLASS}`)) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      for (const rect of range.getClientRects()) {
        if (rect.width > 0 && rect.height > 0) rectangles.push({
          x: rect.x, y: rect.y, right: rect.right, bottom: rect.bottom,
        });
      }
    }
    return rectangles;
  };

  const applyIcons = () => {
    const slots = [];
    const audit = {};
    const targets = hostAdapter?.iconTargets || {};
    for (const [slot, selectors] of Object.entries(targets)) {
      const assetUrl = assetUrls.icons?.[slot];
      if (!assetUrl) continue;
      const target = visibleNodes(selectors)[0];
      if (!target) {
        // 主动作可能被 Stop 等受信任原生互斥状态替换；审计前先恢复原生图标。
        clearIconSlot(slot);
        continue;
      }
      let icon = target.querySelector(`:scope > .${ICON_NODE_CLASS}[data-studio-icon="${slot}"]`);
      if (!icon) {
        clearIconSlot(slot);
        icon = document.createElement("span");
        icon.className = ICON_NODE_CLASS;
        icon.dataset.studioIcon = slot;
        icon.setAttribute("aria-hidden", "true");
        target.appendChild(icon);
      }
      icon.style.setProperty("--studio-icon", `url(${JSON.stringify(assetUrl)})`);
      target.classList.add(ICON_CLASS);
      const targetBounds = target.getBoundingClientRect();
      const nativeIcon = [...target.querySelectorAll("svg")].find(
        (candidate) => !candidate.closest(`.${ICON_NODE_CLASS}`),
      );
      if (nativeIcon) {
        const nativeBounds = nativeIcon.getBoundingClientRect();
        nativeIcon.classList.add(NATIVE_ICON_HIDDEN_CLASS);
        icon.classList.add(ICON_OVERLAY_CLASS);
        icon.style.setProperty("--studio-icon-left", `${nativeBounds.left - targetBounds.left}px`);
        icon.style.setProperty("--studio-icon-top", `${nativeBounds.top - targetBounds.top}px`);
        icon.style.setProperty("--studio-icon-width", `${nativeBounds.width}px`);
        icon.style.setProperty("--studio-icon-height", `${nativeBounds.height}px`);
      } else {
        icon.classList.remove(ICON_OVERLAY_CLASS);
        for (const property of [
          "--studio-icon-left", "--studio-icon-top", "--studio-icon-width", "--studio-icon-height",
        ]) icon.style.removeProperty(property);
        if (icon !== target.firstElementChild) target.prepend(icon);
      }
      const targetRect = rectOf(target);
      const iconRect = rectOf(icon);
      audit[slot] = {
        targetRect,
        iconRect,
        hitTargetOk: hasUsableHitTarget(target, targetRect),
        iconTextOverlap: textRects(target).some((item) => intersects(iconRect, item)),
      };
      slots.push(slot);
    }
    return { slots, audit };
  };

  const clearSkinDom = () => {
    const root = document.documentElement;
    root?.classList.remove(...ROOT_CLASSES);
    for (const property of ROOT_PROPERTIES) root?.style.removeProperty(property);
    document.querySelectorAll(".dream-home").forEach((node) => node.classList.remove("dream-home"));
    document.querySelectorAll(".dream-task").forEach((node) => node.classList.remove("dream-task"));
    document.querySelectorAll(".dream-home-shell").forEach((node) => node.classList.remove("dream-home-shell"));
    document.querySelectorAll(`.${HOME_UTILITY_CLASS}`).forEach((node) => node.classList.remove(HOME_UTILITY_CLASS));
    clearIcons();
    document.getElementById(STYLE_ID)?.remove();
    document.getElementById(CHROME_ID)?.remove();
  };

  const applyVariables = (root, effectiveMode, effectiveDensity) => {
    const p = config.palette;
    const m = config.materials;
    const a = config.art;
    const shadow = m.shadow === "none" ? "none"
      : m.shadow === "strong" ? "0 18px 48px rgb(0 0 0 / .34)"
        : "0 12px 36px rgb(0 0 0 / .18)";
    const assetValue = (dataUrl) => dataUrl ? `url(${JSON.stringify(dataUrl)})` : "none";
    root.style.setProperty("--dream-art", assetValue(assetUrls.homeBackground));
    root.style.setProperty("--dream-task-art", assetValue(assetUrls.taskBackground));
    root.style.setProperty("--dream-art-position", `${Math.round(a.focusX * 100)}% ${Math.round(a.focusY * 100)}%`);
    root.style.setProperty("--dream-accent", p.accent);
    root.style.setProperty("--dream-accent-ink", p.accentContrast);
    root.style.setProperty("--dream-canvas", p.canvas);
    root.style.setProperty("--dream-surface", p.surface);
    root.style.setProperty("--dream-surface-raised", p.elevated);
    root.style.setProperty("--dream-sidebar", p.menu);
    root.style.setProperty("--dream-header", p.panel);
    root.style.setProperty("--dream-text", p.text);
    root.style.setProperty("--dream-muted", p.muted);
    root.style.setProperty("--dream-line", p.border);
    root.style.setProperty("--dream-glass-panel", `color-mix(in srgb, ${p.panel} ${Math.round(m.panelOpacity * 100)}%, transparent)`);
    root.style.setProperty("--dream-glass-dialog", `color-mix(in srgb, ${p.dialog} ${Math.round(m.dialogOpacity * 100)}%, transparent)`);
    root.style.setProperty("--dream-composer-surface", `color-mix(in srgb, ${p.composer} ${Math.round(m.composerOpacity * 100)}%, transparent)`);
    const readingOpacity = config.appearance === "light"
      ? Math.max(0.90, m.dialogOpacity) : Math.max(0.84, m.dialogOpacity);
    root.style.setProperty("--dream-reading-surface", `color-mix(in srgb, ${p.canvas} ${Math.round(readingOpacity * 100)}%, transparent)`);
    root.style.setProperty("--dream-panel-filter", m.blur ? `blur(${m.blur}px)` : "none");
    root.style.setProperty("--dream-dialog-filter", m.blur ? `blur(${m.blur}px)` : "none");
    root.style.setProperty("--dream-shadow", shadow);
    root.style.setProperty("--studio-sidebar-width", `${config.layout.sidebarWidth}px`);
    root.style.setProperty("--studio-content-max", `${config.layout.contentMaxWidth}px`);
    root.style.setProperty("--studio-composer-offset", `${effectiveMode === "native" ? 0 : config.layout.composerOffset}px`);
    root.style.setProperty("--studio-radius", `${m.radius}px`);
    root.style.setProperty("--studio-home-intensity", String(a.homeIntensity));
    root.style.setProperty("--studio-task-intensity", String(a.taskIntensity));
    const semanticProperties = {
      "--color-token-foreground": p.text,
      "--color-token-text-primary": p.text,
      "--color-text-foreground": p.text,
      "--color-text-foreground-secondary": p.muted,
      "--color-text-foreground-tertiary": p.muted,
      "--color-token-conversation-body": p.muted,
      "--color-token-description-foreground": p.muted,
      "--color-token-disabled-foreground": p.muted,
      "--color-token-main-surface-primary": p.canvas,
      "--color-token-side-bar-background": p.menu,
      "--vscode-sideBar-background": p.menu,
      "--color-token-input-background": p.composer,
      "--vscode-input-background": p.composer,
      "--color-token-menu-background": p.dialog,
      "--vscode-menu-background": p.dialog,
      "--color-token-dropdown-background": p.dialog,
      "--vscode-dropdown-background": p.dialog,
      "--color-token-list-hover-background": `color-mix(in srgb, ${p.accent} 12%, transparent)`,
      "--color-token-list-active-selection-background": `color-mix(in srgb, ${p.accent} 20%, transparent)`,
      "--color-token-text-preformat-background": p.elevated,
      "--color-token-text-code-block-background": p.elevated,
      "--color-token-button-background": p.accent,
      "--color-token-button-foreground": p.accentContrast,
      "--vscode-foreground": p.text,
      "--vscode-editor-foreground": p.text,
    };
    for (const [property, value] of Object.entries(semanticProperties)) root.style.setProperty(property, value);
    for (const property of [
      "--color-token-border", "--color-token-border-default", "--color-token-input-border",
      "--vscode-input-border", "--vscode-sideBar-border",
    ]) root.style.setProperty(property, p.border);
    const homeWash = Math.round((1 - a.homeIntensity) * 100);
    const taskWash = Math.round((1 - a.taskIntensity) * 100);
    root.style.setProperty("--studio-home-wash", homeWash
      ? `linear-gradient(color-mix(in srgb, ${p.canvas} ${homeWash}%, transparent), color-mix(in srgb, ${p.canvas} ${homeWash}%, transparent))`
      : "linear-gradient(transparent, transparent)");
    root.style.setProperty("--studio-task-wash", taskWash
      ? `linear-gradient(color-mix(in srgb, ${p.canvas} ${taskWash}%, transparent), color-mix(in srgb, ${p.canvas} ${taskWash}%, transparent))`
      : "linear-gradient(transparent, transparent)");
    for (const mode of ["native", "compact", "cinematic", "focus"]) {
      root.classList.toggle(`studio-layout-${mode}`, effectiveMode === mode);
    }
    for (const density of ["compact", "comfortable", "spacious"]) {
      root.classList.toggle(`studio-density-${density}`, effectiveDensity === density);
    }
  };

  const activeScenes = () => {
    const contracts = hostAdapter?.sceneContracts || {};
    if (runtime.requestedScene) {
      return contracts[runtime.requestedScene] ? [runtime.requestedScene] : [];
    }
    const scenes = [];
    if (contracts.home && visibleNodes(contracts.home.detect).length) scenes.push("home");
    else if (contracts.task && visibleNodes(contracts.task.detect).length) scenes.push("task");
    if (contracts.dialog && visibleNodes(contracts.dialog.detect).length) scenes.push("dialog");
    if (contracts["task-sidebar"] && visibleNodes(contracts["task-sidebar"].detect).length) {
      scenes.push("task-sidebar");
    }
    return scenes;
  };

  const buildAssetAudit = (root) => {
    const backgrounds = [
      ["home", assets.homeBackground, assetUrls.homeBackground, "--dream-art"],
      ["task", assets.taskBackground, assetUrls.taskBackground, "--dream-task-art"],
    ];
    const requestedBackgrounds = backgrounds.filter(([, requested]) => Boolean(requested));
    const appliedBackgrounds = requestedBackgrounds
      .filter(([, , objectUrl, property]) =>
        Boolean(objectUrl) && root.style.getPropertyValue(property).includes(objectUrl))
      .map(([name]) => name);
    const requestedIcons = Object.entries(assets.icons || {})
      .filter(([, requested]) => Boolean(requested))
      .map(([slot]) => slot)
      .sort();
    const materializedIcons = requestedIcons.filter((slot) => Boolean(assetUrls.icons?.[slot]));
    const failures = [];
    if (appliedBackgrounds.length !== requestedBackgrounds.length) {
      failures.push("BACKGROUND_ASSET_NOT_BOUND");
    }
    if (materializedIcons.length !== requestedIcons.length) {
      failures.push("ICON_ASSET_NOT_MATERIALIZED");
    }
    return {
      status: failures.length ? BLOCKED : COMPLETE,
      requestedBackgrounds: requestedBackgrounds.map(([name]) => name),
      appliedBackgrounds,
      requestedIcons,
      materializedIcons,
      failures,
    };
  };

  const collectComponent = (name) => {
    const contract = hostAdapter?.components?.[name] || {};
    const nodes = visibleNodes(contract.selectors);
    const actionable = ["button", "menu-item"].includes(contract.kind);
    return {
      name,
      kind: contract.kind || "unknown",
      min: contract.min ?? 1,
      max: contract.max ?? Number.MAX_SAFE_INTEGER,
      count: nodes.length,
      rects: nodes.map(rectOf),
      clipped: nodes.some((node) => {
        const style = getComputedStyle(node);
        const horizontalOverflow = node.scrollWidth > node.clientWidth + 1;
        const verticalOverflow = node.scrollHeight > node.clientHeight + 1;
        const horizontalClip = horizontalOverflow
          && ["hidden", "clip"].includes(style.overflowX);
        const verticalClip = verticalOverflow
          && ["hidden", "clip"].includes(style.overflowY);
        return horizontalClip || verticalClip;
      }),
      hitTargetOk: !actionable || nodes.every((node) => {
        const rect = node.getBoundingClientRect();
        return hasUsableHitTarget(node, rect);
      }),
      styles: nodes.slice(0, 8).map((node) => {
        const style = getComputedStyle(node);
        return {
          color: style.color,
          backgroundColor: style.backgroundColor,
          borderColor: style.borderColor,
          outlineColor: style.outlineColor,
          caretColor: style.caretColor,
          zIndex: style.zIndex,
          overflowX: style.overflowX,
          overflowY: style.overflowY,
        };
      }),
    };
  };

  const collectIconSlotEvidence = (slot, iconResult) => {
    const alternates = hostAdapter?.iconSlotAlternates?.[slot] || {};
    const alternateMatches = Object.entries(alternates)
      .map(([state, selectors]) => ({ state, nodes: visibleNodes(selectors) }))
      .filter((item) => item.nodes.length > 0);
    if (iconResult.slots.includes(slot)) {
      const audit = iconResult.audit[slot] || {};
      return {
        status: alternateMatches.length ? "conflict" : "theme-icon",
        state: "default",
        targetRect: audit.targetRect ?? null,
        iconRect: audit.iconRect ?? null,
        hitTargetOk: audit.hitTargetOk !== false,
        iconTextOverlap: audit.iconTextOverlap === true,
        alternateStates: alternateMatches.map((item) => item.state),
      };
    }
    if (alternateMatches.length === 1 && alternateMatches[0].nodes.length === 1) {
      const target = alternateMatches[0].nodes[0];
      const targetRect = rectOf(target);
      return {
        status: "native-alternate",
        state: alternateMatches[0].state,
        targetRect,
        iconRect: null,
        hitTargetOk: hasUsableHitTarget(target, targetRect),
        iconTextOverlap: false,
        alternateStates: [alternateMatches[0].state],
      };
    }
    return {
      status: alternateMatches.length ? "ambiguous-alternate" : "missing",
      state: null,
      targetRect: null,
      iconRect: null,
      hitTargetOk: false,
      iconTextOverlap: false,
      alternateStates: alternateMatches.map((item) => item.state),
    };
  };

  const buildSceneAudit = (iconResult) => {
    if (!hostAdapter) {
      return { status: BLOCKED, scenes: [], errors: ["UNKNOWN_HOST_VERSION"], components: {} };
    }
    const scenes = activeScenes();
    if (!scenes.length) {
      return {
        status: PARTIAL,
        scenes: [],
        errors: [runtime.requestedScene ? "REQUESTED_SCENE_NOT_SUPPORTED" : "UNRECOGNIZED_SCENE"],
        components: {},
      };
    }
    const components = {};
    const iconSlotEvidence = {};
    const errors = [];
    const contracts = [];
    for (const scene of scenes) {
      const contract = hostAdapter.sceneContracts[scene];
      contracts.push({ scene, ...contract });
      for (const name of contract.requiredComponents) {
        components[name] ??= collectComponent(name);
        const item = components[name];
        if (item.count < item.min || item.count > item.max) {
          errors.push(`${scene}:COMPONENT_COUNT:${name}:${item.count}`);
        }
      }
      for (const slot of contract.expectedIconSlots) {
        iconSlotEvidence[slot] ??= collectIconSlotEvidence(slot, iconResult);
        const evidence = iconSlotEvidence[slot];
        if (evidence.status === "missing") errors.push(`${scene}:ICON_MISSING:${slot}`);
        else if (evidence.status === "ambiguous-alternate") {
          errors.push(`${scene}:ICON_ALTERNATE_AMBIGUOUS:${slot}`);
        } else if (evidence.status === "conflict") {
          errors.push(`${scene}:ICON_PRIMARY_ALTERNATE_CONFLICT:${slot}`);
        } else if (evidence.iconTextOverlap) errors.push(`${scene}:ICON_TEXT_OVERLAP:${slot}`);
        else if (evidence.hitTargetOk === false) errors.push(`${scene}:HIT_TARGET:${slot}`);
      }
    }
    return {
      status: errors.length ? BLOCKED : COMPLETE,
      scenes,
      errors,
      components,
      iconSlotEvidence,
      contracts,
      expectedIconSlots: [...new Set(contracts.flatMap((item) => item.expectedIconSlots))],
    };
  };

  const buildLayoutEffect = (effectiveMode, effectiveDensity, sceneAudit) => {
    if (effectiveMode === "native") {
      const safe = config.layout.composerOffset === 0 && effectiveDensity === "comfortable";
      return {
        status: safe ? COMPLETE : BLOCKED,
        mode: "native",
        inactiveByContract: ["sidebarWidth", "contentMaxWidth"],
        composerOffset: 0,
        density: effectiveDensity,
      };
    }
    const sidebar = visibleNodes(hostAdapter?.components?.sidebar?.selectors)[0];
    const composer = visibleNodes(hostAdapter?.components?.composer?.selectors)[0];
    const content = document.querySelector(".thread-scroll-container > div");
    const sidebarWidth = sidebar ? Math.round(sidebar.getBoundingClientRect().width) : null;
    const composerTranslate = composer ? getComputedStyle(composer).translate : null;
    const contentMaxWidth = content ? Number.parseFloat(getComputedStyle(content).maxWidth) : null;
    const widthMatches = sidebarWidth !== null && Math.abs(sidebarWidth - config.layout.sidebarWidth) <= 1;
    const offsetMatches = config.layout.composerOffset === 0
      ? composerTranslate === "none" || /^0px(?:\s+0px)?$/.test(String(composerTranslate))
      : String(composerTranslate).includes(`${config.layout.composerOffset}px`);
    const contentApplicable = (sceneAudit?.scenes || []).includes("task");
    const contentMatches = !contentApplicable
      || (contentMaxWidth !== null && Math.abs(contentMaxWidth - config.layout.contentMaxWidth) <= 1);
    return {
      status: widthMatches && offsetMatches && contentMatches ? COMPLETE : BLOCKED,
      mode: effectiveMode,
      sidebarWidth: { requested: config.layout.sidebarWidth, actual: sidebarWidth, matched: widthMatches },
      contentMaxWidth: {
        requested: config.layout.contentMaxWidth,
        actual: contentMaxWidth,
        applicable: contentApplicable,
        matched: contentMatches,
      },
      composerOffset: {
        requested: config.layout.composerOffset,
        actual: composerTranslate,
        matched: offsetMatches,
      },
      density: effectiveDensity,
    };
  };

  const buildGeometryAudit = (sceneAudit, layoutEffect) => {
    const failures = [];
    if (document.documentElement.scrollWidth > document.documentElement.clientWidth) {
      failures.push({ code: "HORIZONTAL_OVERFLOW", component: "document" });
    }
    const viewport = { width: innerWidth, height: innerHeight };
    for (const [name, component] of Object.entries(sceneAudit.components || {})) {
      if (component.clipped) failures.push({ code: "CLIPPED_CONTENT", component: name });
      if (component.hitTargetOk === false) failures.push({ code: "HIT_TARGET_MISALIGNED", component: name });
      for (const rect of component.rects) {
        if (rect.x < -1 || rect.y < -1 || rect.right > innerWidth + 1 || rect.bottom > innerHeight + 1) {
          failures.push({ code: "OUT_OF_BOUNDS", component: name, rect });
        }
      }
    }
    for (const contract of sceneAudit.contracts || []) {
      for (const [firstName, secondName] of contract.nonOverlapPairs || []) {
        const firstRects = sceneAudit.components[firstName]?.rects || [];
        const secondRects = sceneAudit.components[secondName]?.rects || [];
        if (firstRects.some((first) => secondRects.some((second) => intersects(first, second)))) {
          failures.push({ code: "OVERLAP", components: [firstName, secondName] });
        }
      }
    }
    if (layoutEffect.status !== COMPLETE) {
      failures.push({ code: "CONFIG_DIMENSION_NOT_EFFECTIVE", details: layoutEffect });
    }
    return {
      status: failures.length ? BLOCKED : COMPLETE,
      failures,
      viewport,
      documentOverflow: {
        x: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        y: document.documentElement.scrollHeight > document.documentElement.clientHeight,
      },
      layoutEffect,
    };
  };

  const contrastRatio = (first, second) => {
    const channels = (value) => [1, 3, 5].map((index) => parseInt(value.slice(index, index + 2), 16));
    const luminance = (value) => {
      const [red, green, blue] = channels(value).map((channel) => {
        const normalized = channel / 255;
        return normalized <= 0.04045 ? normalized / 12.92
          : ((normalized + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    };
    const [lighter, darker] = [luminance(first), luminance(second)].sort((a, b) => b - a);
    return Math.round(((lighter + 0.05) / (darker + 0.05)) * 100) / 100;
  };

  const buildContrastAudit = () => {
    const ratios = {
      textOnSurface: contrastRatio(config.palette.text, config.palette.surface),
      mutedOnSurface: contrastRatio(config.palette.muted, config.palette.surface),
      accentContrast: contrastRatio(config.palette.accentContrast, config.palette.accent),
    };
    const failures = [];
    if (ratios.textOnSurface < 4.5) failures.push("TEXT_SURFACE");
    if (ratios.mutedOnSurface < 3) failures.push("MUTED_SURFACE");
    if (ratios.accentContrast < 4.5) failures.push("ACCENT_CONTRAST");
    return { status: failures.length ? BLOCKED : COMPLETE, ratios, failures };
  };

  const buildSemanticStateEvidence = (sceneAudit) => {
    const selectors = hostAdapter?.semanticStateSelectors || {};
    const observed = {
      button: new Set(),
      menu: new Set(),
      composer: new Set(),
      sidebar: new Set(),
      overlay: new Set(),
    };
    const styleSnapshot = (node) => {
      const style = getComputedStyle(node || document.documentElement);
      return {
        color: style.color,
        backgroundColor: style.backgroundColor,
        borderColor: style.borderColor,
        outlineColor: style.outlineColor,
        caretColor: style.caretColor,
        opacity: style.opacity,
        pointerEvents: style.pointerEvents,
      };
    };
    const observe = (group, state, node) => {
      observed[group].add(state);
      semanticStyleCache[group][state] ??= styleSnapshot(node);
    };
    const buttons = visibleNodes(selectors.button);
    if (buttons.length) observe("button", "default", buttons[0]);
    let match = buttons.find((node) => node.matches(":hover"));
    if (match) observe("button", "hover", match);
    match = buttons.find((node) => node.matches(":focus-visible"));
    if (match) observe("button", "focus", match);
    match = buttons.find((node) => node.matches(":active") || node.getAttribute("aria-pressed") === "true");
    if (match) observe("button", "pressed", match);
    match = buttons.find((node) => node.disabled || node.getAttribute("aria-disabled") === "true");
    if (match) observe("button", "disabled", match);
    match = buttons.find((node) => node.querySelector(`.${ICON_NODE_CLASS}`) && node.textContent?.trim());
    if (match) observe("button", "icon-text", match);

    const menuNodes = visibleNodes(selectors.menu);
    if (menuNodes.length) observe("menu", "open", menuNodes[0]);
    match = menuNodes.find((node) => node.matches(":hover"));
    if (match) observe("menu", "hover", match);
    match = menuNodes.find((node) => node.getAttribute("aria-selected") === "true"
      || node.getAttribute("aria-current"));
    if (match) observe("menu", "selected", match);
    match = menuNodes.find((node) => node.getAttribute("aria-disabled") === "true");
    if (match) observe("menu", "disabled", match);
    match = menuNodes.find((node) => node.getAttribute("aria-haspopup"));
    if (match) observe("menu", "submenu", match);

    const composerNodes = visibleNodes(selectors.composer);
    match = composerNodes.find((node) => !(node.textContent || "").trim());
    if (match) observe("composer", "empty", match);
    match = composerNodes.find((node) => node.scrollHeight > node.clientHeight + 1
      || (node.textContent || "").includes("\n"));
    if (match) observe("composer", "multiline", match);
    match = composerNodes.find((node) => node.querySelector("[data-testid*=attachment], [class*=attachment]"));
    if (match) observe("composer", "attachment", match);
    const sendButtons = visibleNodes(hostAdapter?.iconTargets?.send);
    match = sendButtons.find((node) => !node.disabled && node.getAttribute("aria-disabled") !== "true");
    if (match) observe("composer", "send-enabled", match);
    match = sendButtons.find((node) => node.disabled || node.getAttribute("aria-disabled") === "true");
    if (match) observe("composer", "send-disabled", match);
    const stopButtons = visibleNodes(hostAdapter?.iconSlotAlternates?.send?.stop);
    if (stopButtons.length === 1) observe("composer", "streaming-stop", stopButtons[0]);

    const sidebarNodes = visibleNodes(selectors.sidebar);
    match = sidebarNodes.find((node) => node.getAttribute("aria-expanded") === "true")
      || sidebarNodes.find((node) => node.matches("aside"));
    if (match) observe("sidebar", "expanded", match);
    match = sidebarNodes.find((node) => node.getAttribute("aria-expanded") === "false");
    if (match) observe("sidebar", "collapsed", match);
    if (innerWidth <= 960) observe("sidebar", "narrow", sidebarNodes[0]);
    if (devicePixelRatio > 1) observe("sidebar", "zoomed", sidebarNodes[0]);

    const overlayNodes = visibleNodes(selectors.overlay);
    match = overlayNodes.find((node) => node.getAttribute("role") === "dialog");
    if (match) observe("overlay", "dialog", match);
    match = overlayNodes.find((node) => node.getAttribute("role") === "tooltip");
    if (match) observe("overlay", "tooltip", match);
    match = overlayNodes.find((node) => node.matches("[data-sonner-toast]"));
    if (match) observe("overlay", "toast", match);
    match = overlayNodes.find((node) => node.matches("[data-type=error]")
      || /error|错误/i.test(node.textContent || ""));
    if (match) observe("overlay", "error", match);

    for (const [group, states] of Object.entries(observed)) {
      for (const state of states) semanticObservationCache[group]?.add(state);
    }
    const required = {};
    const sceneRequirements = runtime.sceneStateRequirements || {};
    for (const scene of sceneAudit?.scenes || []) {
      for (const [group, states] of Object.entries(sceneRequirements[scene] || {})) {
        required[group] ??= [];
        const applicable = states.filter((state) => {
          if (state === "narrow") return innerWidth <= 960;
          if (state === "zoomed") return devicePixelRatio > 1;
          return true;
        });
        required[group].push(...applicable.filter((state) => !required[group].includes(state)));
      }
    }
    const missing = {};
    for (const [group, states] of Object.entries(required)) {
      const absent = states.filter((state) => !semanticObservationCache[group]?.has(state));
      if (absent.length) missing[group] = absent;
    }
    return {
      status: Object.keys(missing).length ? PARTIAL : COMPLETE,
      observed: Object.fromEntries(
        Object.entries(semanticObservationCache).map(([key, value]) => [key, [...value].sort()]),
      ),
      stateStyles: semanticStyleCache,
      required,
      missing,
    };
  };

  const ensure = (strongAudit = false) => {
    if (window.__CODEX_DREAM_SKIN_DISABLED__ || applying) return;
    applying = true;
    try {
      const root = document.documentElement;
      const shellSelectors = hostAdapter?.components?.shell?.selectors || ["main.main-surface"];
      const shellMain = queryAll(shellSelectors)[0] || document.querySelector("main") || document.querySelector("[role=main]");
      if (!root || !document.body || !shellMain) {
        clearSkinDom();
        return;
      }
      const state = window[STATE_KEY];
      const runAudit = strongAudit || !state?.auditCompleted || runtime.evidenceMode === true;
      const probe = runAudit ? adapterProbe() : {
        supported: state.adapterStatus !== BLOCKED,
        reason: state.adapterReason,
        signatures: state.structureSignatures || {},
      };
      const layoutReceipt = hostAdapter?.layoutMatrix?.[config.layout.mode];
      const layoutAllowed = runAudit
        ? probe.supported && layoutReceipt?.status === COMPLETE
        : state.layoutMode === config.layout.mode;
      const effectiveMode = layoutAllowed ? config.layout.mode : "native";
      const effectiveDensity = runAudit ? (effectiveMode === "native" ? "comfortable" : config.layout.density) : (state.density || "comfortable");
      const appearance = detectAppearance();
      root.classList.add("codex-dream-skin");
      root.classList.toggle("dream-theme-light", appearance === "light");
      root.classList.toggle("dream-theme-dark", appearance === "dark");
      for (const safe of ["left", "center", "right", "none"]) {
        root.classList.toggle(`dream-safe-${safe}`, config.art.safeArea === safe);
      }
      root.classList.add("dream-task-ambient");
      applyVariables(root, effectiveMode, effectiveDensity);
      const assetAudit = buildAssetAudit(root);

      let style = document.getElementById(STYLE_ID);
      if (!style) {
        style = document.createElement("style");
        style.id = STYLE_ID;
        (document.head || root).appendChild(style);
      }
      if (style.dataset.dreamVersion !== VERSION) {
        style.textContent = cssText;
        style.dataset.dreamVersion = VERSION;
      }

      const home = hostAdapter?.components?.home
        ? visibleNodes(hostAdapter.components.home.selectors)[0] : null;
      const candidates = visibleNodes(hostAdapter?.components?.main?.selectors || []);
      if (!candidates.length) candidates.push(shellMain);
      for (const candidate of candidates) {
        candidate.classList.toggle("dream-home", candidate === home);
        candidate.classList.toggle("dream-task", candidate !== home);
      }
      shellMain.classList.toggle("dream-home-shell", Boolean(home));
      const utilityBars = new Set(home ? home.querySelectorAll("[class*=_homeUtilityBar_]") : []);
      document.querySelectorAll(`.${HOME_UTILITY_CLASS}`).forEach((node) => {
        if (!utilityBars.has(node)) node.classList.remove(HOME_UTILITY_CLASS);
      });
      utilityBars.forEach((node) => node.classList.add(HOME_UTILITY_CLASS));

      let chrome = document.getElementById(CHROME_ID);
      if (!chrome) {
        chrome = document.createElement("div");
        chrome.id = CHROME_ID;
        chrome.setAttribute("aria-hidden", "true");
        document.body.appendChild(chrome);
      }

      const iconResult = applyIcons();
      if (!runAudit) {
        if (state?.installToken === installToken) {
          Object.assign(state, {
            iconsApplied: iconResult.slots,
            iconAudit: iconResult.audit,
            incrementalSyncAt: Date.now(),
          });
        }
        return;
      }
      const sceneAudit = buildSceneAudit(iconResult);
      const layoutEffect = buildLayoutEffect(effectiveMode, effectiveDensity, sceneAudit);
      const geometryAudit = buildGeometryAudit(sceneAudit, layoutEffect);
      const contrastAudit = buildContrastAudit();
      const semanticStates = buildSemanticStateEvidence(sceneAudit);
      const stylesEvidence = {
        status: semanticStates.status,
        semanticStates,
        components: Object.fromEntries(
          Object.entries(sceneAudit.components || {}).map(([name, item]) => [name, item.styles])
        ),
      };
      let adapterStatus = COMPLETE;
      let adapterReason = null;
      if (!hostAdapter || runtime.hostStatus !== COMPLETE) {
        adapterStatus = BLOCKED;
        adapterReason = runtime.hostReason || "UNKNOWN_HOST_VERSION";
      } else if (!probe.supported) {
        adapterStatus = PARTIAL;
        adapterReason = probe.reason;
      } else if (!layoutAllowed) {
        adapterStatus = PARTIAL;
        adapterReason = "LAYOUT_MATRIX_INCOMPLETE";
      } else if (sceneAudit.status !== COMPLETE) {
        adapterStatus = sceneAudit.status;
        adapterReason = sceneAudit.errors.join(",");
      } else if (assetAudit.status !== COMPLETE) {
        adapterStatus = BLOCKED;
        adapterReason = "VISUAL_ASSET_CONTRACT_FAILED";
      } else if (geometryAudit.status !== COMPLETE || contrastAudit.status !== COMPLETE) {
        adapterStatus = BLOCKED;
        adapterReason = "VISUAL_CONTRACT_FAILED";
      }

      if (state?.installToken === installToken) {
        Object.assign(state, {
          adapterStatus,
          adapterReason,
          layoutMode: effectiveMode,
          requestedLayoutMode: config.layout.mode,
          density: effectiveDensity,
          hostVersion: runtime.codexVersion || null,
          hostAdapterId: hostAdapter?.id || null,
          structureSignatures: probe.signatures,
          iconsApplied: iconResult.slots,
          iconAudit: iconResult.audit,
          iconSlotEvidence: sceneAudit.iconSlotEvidence,
          sceneAudit,
          geometryAudit,
          contrastAudit,
          assetAudit,
          stylesEvidence,
          visualAssetsRequested,
          evidenceMode: runtime.evidenceMode === true,
          requestedScene: runtime.requestedScene || null,
          auditCompleted: true,
        });
      }
    } finally {
      applying = false;
    }
  };

  const cleanup = () => {
    const state = window[STATE_KEY];
    if (state?.installToken !== installToken) return false;
    window.__CODEX_DREAM_SKIN_DISABLED__ = true;
    state.observer?.disconnect();
    if (state.timer) clearInterval(state.timer);
    if (state.scheduler) clearTimeout(state.scheduler);
    for (const eventName of state.interactionEvents || []) {
      document.removeEventListener(eventName, scheduleEnsure, true);
    }
    clearSkinDom();
    for (const objectUrl of objectUrls) URL.revokeObjectURL(objectUrl);
    objectUrls.clear();
    materializedByDataUrl.clear();
    delete window[STATE_KEY];
    return true;
  };
  const scheduleEnsure = () => {
    const state = window[STATE_KEY];
    if (!state || state.installToken !== installToken || state.scheduler) return;
    state.scheduler = setTimeout(() => {
      state.scheduler = null;
      ensure(false);
    }, 180);
  };

  observer = new MutationObserver(scheduleEnsure);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: [
      "class", "aria-label", "aria-disabled", "aria-selected", "aria-pressed",
      "data-theme", "data-appearance", "data-testid",
    ],
  });
  const interactionEvents = [
    "focusin", "input", "change",
  ];
  for (const eventName of interactionEvents) {
    document.addEventListener(eventName, scheduleEnsure, true);
  }
  const timer = setInterval(scheduleEnsure, 60000);
  window[STATE_KEY] = {
    ensure,
    cleanup,
    observer,
    timer,
    interactionEvents,
    scheduler: null,
    installToken,
    version: VERSION,
    themeId: config.id,
    layoutMode: "native",
    requestedLayoutMode: config.layout.mode,
    adapterStatus: BLOCKED,
    adapterReason: runtime.hostReason || "INITIALIZING",
    hostVersion: runtime.codexVersion || null,
    hostAdapterId: hostAdapter?.id || null,
    iconsApplied: [],
    iconSlotEvidence: {},
    structureSignatures: {},
    sceneAudit: { status: PARTIAL, scenes: [], errors: ["INITIALIZING"], components: {} },
    geometryAudit: { status: PARTIAL, failures: [] },
    contrastAudit: { status: PARTIAL, ratios: {}, failures: [] },
    assetAudit: { status: PARTIAL, failures: ["INITIALIZING"] },
    stylesEvidence: { status: PARTIAL, semanticStates: {}, components: {} },
    visualAssetsRequested,
    evidenceMode: runtime.evidenceMode === true,
    auditCompleted: false,
  };
  ensure(true);
  return {
    installed: true,
    version: VERSION,
    themeId: config.id,
    adapter: hostAdapter?.id || null,
    status: window[STATE_KEY]?.adapterStatus || BLOCKED,
  };
})(__DREAM_CSS_JSON__, __DREAM_ART_JSON__, __DREAM_THEME_JSON__, __DREAM_RUNTIME_JSON__)
