#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";


const DEFAULT_CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const VIEWPORTS = [
  { id: "desktop", width: 1440, height: 900 },
  { id: "tablet", width: 768, height: 900 },
  { id: "mobile", width: 390, height: 844 },
];
const NAVIGATION_SETTLE_TIMEOUT_MS = 4_000;


function parseArgs(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (!argument.startsWith("--")) {
      throw new Error(`未知参数：${argument}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`参数缺少值：${argument}`);
    }
    values[argument.slice(2)] = value;
    index += 1;
  }
  if (!values.html || !values["output-dir"]) {
    throw new Error("用法：node tests/run_visual_qa.mjs --html <report.html> --output-dir <dir> [--chrome <path>]");
  }
  return {
    htmlPath: resolve(values.html),
    outputDir: resolve(values["output-dir"]),
    chromePath: resolve(values.chrome || DEFAULT_CHROME),
  };
}


async function reservePort() {
  const server = createServer();
  await new Promise((resolvePromise, rejectPromise) => {
    server.once("error", rejectPromise);
    server.listen(0, "127.0.0.1", resolvePromise);
  });
  const address = server.address();
  const port = typeof address === "object" && address ? address.port : 0;
  await new Promise((resolvePromise) => server.close(resolvePromise));
  if (!port) {
    throw new Error("无法分配 Chrome 调试端口");
  }
  return port;
}


async function removeDirectoryWithRetry(path) {
  for (let attempt = 0; attempt < 6; attempt += 1) {
    try {
      await rm(path, { recursive: true, force: true });
      return;
    } catch (error) {
      const retryable = ["EBUSY", "EPERM", "ENOTEMPTY"].includes(error?.code);
      if (!retryable || attempt === 5) throw error;
      // NOTE: Windows Crashpad can retain its metrics file briefly after Chrome exits.
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 200 * (attempt + 1)));
    }
  }
}


async function waitForJson(url, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return await response.json();
      }
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 100));
  }
  throw new Error(`Chrome 调试端点未就绪：${lastError?.message || "timeout"}`);
}


class CdpClient {
  constructor(webSocketUrl) {
    this.webSocketUrl = webSocketUrl;
    this.socket = null;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async connect() {
    this.socket = new WebSocket(this.webSocketUrl);
    this.socket.addEventListener("message", (event) => this.handleMessage(event));
    await new Promise((resolvePromise, rejectPromise) => {
      this.socket.addEventListener("open", resolvePromise, { once: true });
      this.socket.addEventListener("error", rejectPromise, { once: true });
    });
  }

  handleMessage(event) {
    const message = JSON.parse(String(event.data));
    if (message.id) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      clearTimeout(pending.timer);
      if (message.error) pending.reject(new Error(message.error.message));
      else pending.resolve(message.result || {});
      return;
    }
    if (!message.method) return;
    for (const listener of this.listeners.get(message.method) || []) {
      listener(message.params || {});
    }
  }

  send(method, params = {}, timeoutMs = 10_000) {
    const id = this.nextId;
    this.nextId += 1;
    return new Promise((resolvePromise, rejectPromise) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        rejectPromise(new Error(`CDP 超时：${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve: resolvePromise, reject: rejectPromise, timer });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) || [];
    listeners.push(listener);
    this.listeners.set(method, listeners);
    return () => {
      const current = this.listeners.get(method) || [];
      this.listeners.set(method, current.filter((candidate) => candidate !== listener));
    };
  }

  waitFor(method, timeoutMs = 10_000) {
    return new Promise((resolvePromise, rejectPromise) => {
      let timer;
      const remove = this.on(method, (params) => {
        clearTimeout(timer);
        remove();
        resolvePromise(params);
      });
      timer = setTimeout(() => {
        remove();
        rejectPromise(new Error(`CDP 事件超时：${method}`));
      }, timeoutMs);
    });
  }

  close() {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.close();
  }
}


async function openPage(port) {
  const response = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" });
  if (!response.ok) {
    throw new Error(`创建 Chrome 页面失败：HTTP ${response.status}`);
  }
  return await response.json();
}


async function navigate(client, url) {
  const expectedUrl = new URL(url).href;
  const before = await evaluate(
    client,
    "({ href: location.href, timeOrigin: performance.timeOrigin })"
  );
  const navigation = await client.send("Page.navigate", { url });
  if (navigation.errorText) {
    throw new Error(`页面导航失败：${navigation.errorText}`);
  }
  const deadline = Date.now() + 15_000;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const state = await evaluate(
        client,
        "({ href: location.href, readyState: document.readyState, timeOrigin: performance.timeOrigin })"
      );
      const targetCommitted = state.href === expectedUrl;
      const newDocumentCommitted =
        !navigation.loaderId || before.href !== expectedUrl || state.timeOrigin !== before.timeOrigin;
      if (targetCommitted && newDocumentCommitted && state.readyState === "complete") return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 50));
  }
  throw new Error(`页面加载超时：${lastError?.message || "document.readyState != complete"}`);
}


async function evaluate(client, expression) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || "页面表达式执行失败");
  }
  return result.result?.value;
}


async function capture(client, outputPath, width, height) {
  const metrics = await client.send("Page.getLayoutMetrics");
  const contentHeight = Math.min(Math.ceil(metrics.cssContentSize?.height || height), 20_000);
  const result = await client.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: true,
    clip: { x: 0, y: 0, width, height: Math.max(height, contentHeight), scale: 1 },
  });
  await writeFile(outputPath, Buffer.from(result.data, "base64"));
}


async function captureViewport(client, outputPath) {
  const result = await client.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
  });
  await writeFile(outputPath, Buffer.from(result.data, "base64"));
}


async function inspectPage(client) {
  return await evaluate(
    client,
    `(() => {
      const root = document.documentElement;
      const body = document.body;
      const visualRight = (window.visualViewport?.offsetLeft || 0) +
        (window.visualViewport?.width || window.innerWidth);
      const ids = [...document.querySelectorAll('[id]')].map((node) => node.id);
      const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
      const brokenInternalLinks = [...document.querySelectorAll('a[href^="#"]')]
        .map((node) => node.getAttribute('href'))
        .filter((href) => !href || href === '#' || !document.getElementById(decodeURIComponent(href.slice(1))));
      const tableMetrics = [...document.querySelectorAll('table')].map((table, tableIndex) => {
        const container = table.closest('.table-scroll');
        const rowHeights = [...table.querySelectorAll('tbody tr')]
          .map((row) => Math.round(row.getBoundingClientRect().height * 100) / 100);
        const expandedColumns = [...table.querySelectorAll('thead th.table-col-expanded')]
          .map((header) => {
            const widthClass = [...header.classList]
              .find((className) => /^table-col-width-[0-9]+$/.test(className));
            const expectedEm = widthClass ? Number(widthClass.split('-').at(-1)) : null;
            const style = getComputedStyle(header);
            const fontSize = Number.parseFloat(style.fontSize) || 0;
            const minWidth = Number.parseFloat(style.minWidth) || 0;
            const actualWidth = header.getBoundingClientRect().width;
            return {
              widthClass,
              expectedEm,
              minWidth: Math.round(minWidth * 100) / 100,
              actualWidth: Math.round(actualWidth * 100) / 100,
              expectedPixels: expectedEm === null ? null : Math.round(expectedEm * fontSize * 100) / 100,
              whiteSpace: style.whiteSpace,
              capped: header.classList.contains('table-col-capped'),
            };
          });
        return {
          tableIndex,
          className: table.className,
          containerKeyboardReachable: Boolean(container && container.tabIndex === 0),
          overflowContained: Boolean(
            container && table.scrollWidth <= container.scrollWidth + 1 && container.clientWidth <= container.scrollWidth + 1
          ),
          containerClientWidth: container?.clientWidth || 0,
          containerScrollWidth: container?.scrollWidth || 0,
          tableScrollWidth: table.scrollWidth,
          rowHeights,
          maxRowHeight: rowHeights.length ? Math.max(...rowHeights) : 0,
          expandedColumns,
        };
      });
      return {
        title: document.title,
        h1Count: document.querySelectorAll('h1').length,
        duplicateIds: [...new Set(duplicateIds)],
        brokenInternalLinks: [...new Set(brokenInternalLinks)],
        pageOverflow: Math.max(root.scrollWidth, body?.scrollWidth || 0) > window.innerWidth + 1,
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
        visualViewportWidth: window.visualViewport?.width || window.innerWidth,
        visualViewportHeight: window.visualViewport?.height || window.innerHeight,
        visualViewportScale: window.visualViewport?.scale || 1,
        scrollWidth: Math.max(root.scrollWidth, body?.scrollWidth || 0),
        scrollHeight: Math.max(root.scrollHeight, body?.scrollHeight || 0),
        textLength: body?.innerText?.trim().length || 0,
        colorScheme: getComputedStyle(root).colorScheme,
        tableMetrics,
        overflowElements: [...document.querySelectorAll('body *')]
          .map((node) => ({ node, rect: node.getBoundingClientRect() }))
          .filter(({ rect }) => rect.right > visualRight + 1)
          .slice(0, 12)
          .map(({ node, rect }) => ({
            tag: node.tagName,
            className: String(node.className || '').slice(0, 120),
            right: Math.round(rect.right * 100) / 100,
            width: Math.round(rect.width * 100) / 100,
            scrollWidth: node.scrollWidth,
          })),
      };
    })()`
  );
}


async function verifyThemeToggle(client) {
  return await evaluate(
    client,
    `(() => {
      const root = document.documentElement;
      const button = document.getElementById('theme-toggle');
      if (!button) return false;
      const before = root.dataset.theme || 'system';
      button.click();
      const after = root.dataset.theme || 'system';
      root.dataset.theme = before;
      return before !== after && ['system', 'light', 'dark'].includes(after);
    })()`
  );
}


async function verifyKeyboardFocus(client) {
  await client.send("Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    key: "Tab",
    code: "Tab",
    windowsVirtualKeyCode: 9,
  });
  await client.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Tab",
    code: "Tab",
    windowsVirtualKeyCode: 9,
  });
  return await evaluate(
    client,
    `(() => {
      const active = document.activeElement;
      if (!active || active === document.body || active === document.documentElement) return false;
      return active.matches(':focus') && (active.tabIndex >= 0 || /^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(active.tagName));
    })()`
  );
}


async function inspectBackToTop(client) {
  return await evaluate(
    client,
    `(() => {
      const links = [...document.querySelectorAll('a.back-to-top')];
      const link = links[0];
      if (!link) return { count: 0, visible: false, targetCount: 0 };
      const href = link.getAttribute('href') || '';
      const targetId = href.startsWith('#') ? decodeURIComponent(href.slice(1)) : '';
      const style = getComputedStyle(link);
      const rect = link.getBoundingClientRect();
      const viewport = window.visualViewport;
      const viewportLeft = viewport?.offsetLeft || 0;
      const viewportTop = viewport?.offsetTop || 0;
      const viewportWidth = viewport?.width || window.innerWidth;
      const viewportHeight = viewport?.height || window.innerHeight;
      const withinViewport =
        rect.left >= viewportLeft &&
        rect.top >= viewportTop &&
        rect.right <= viewportLeft + viewportWidth + 1 &&
        rect.bottom <= viewportTop + viewportHeight + 1;
      return {
        count: links.length,
        href,
        label: link.getAttribute('aria-label') || link.textContent.trim(),
        targetCount: targetId ? document.querySelectorAll('#' + CSS.escape(targetId)).length : 0,
        visible:
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          Number(style.opacity || 1) > 0 &&
          rect.width > 0 &&
          rect.height > 0 &&
          withinViewport,
        display: style.display,
        visibility: style.visibility,
        opacity: style.opacity,
        rect: {
          left: rect.left,
          top: rect.top,
          right: rect.right,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height,
        },
        viewport: {
          left: viewportLeft,
          top: viewportTop,
          width: viewportWidth,
          height: viewportHeight,
          scale: viewport?.scale || 1,
        },
        withinViewport,
      };
    })()`
  );
}


async function verifyBackToTopInteraction(client, screenshotPath) {
  const pageCanScroll = await evaluate(
    client,
    "document.documentElement.scrollHeight > window.innerHeight + 100"
  );
  if (!pageCanScroll) {
    return { pageCanScroll: false, revealed: false, returnedToTop: false };
  }
  await evaluate(client, "window.scrollTo(0, document.documentElement.scrollHeight)");
  await new Promise((resolvePromise) => setTimeout(resolvePromise, 250));
  const afterScroll = await inspectBackToTop(client);
  await captureViewport(client, screenshotPath);
  await evaluate(client, "document.querySelector('a.back-to-top')?.click()");

  let finalScrollY = Number.POSITIVE_INFINITY;
  const deadline = Date.now() + NAVIGATION_SETTLE_TIMEOUT_MS;
  while (Date.now() < deadline) {
    finalScrollY = await evaluate(client, "window.scrollY");
    if (finalScrollY <= 1) break;
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 50));
  }
  return {
    pageCanScroll: true,
    revealed: afterScroll.visible === true,
    returnedToTop: finalScrollY <= 1,
    finalScrollY,
    screenshot: screenshotPath,
    afterScroll,
  };
}


async function runScenario(client, htmlUrl, outputDir, viewport, mode) {
  const isPrint = mode === "print";
  await client.send("Emulation.setScriptExecutionDisabled", { value: false });
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: viewport.width,
    height: viewport.height,
    deviceScaleFactor: 1,
    mobile: viewport.id === "mobile",
    screenWidth: viewport.width,
    screenHeight: viewport.height,
    scale: 1,
  });
  await client.send("Emulation.setEmulatedMedia", {
    media: isPrint ? "print" : "screen",
    features: [{ name: "prefers-color-scheme", value: mode === "dark" ? "dark" : "light" }],
  });
  await navigate(client, htmlUrl);
  if (!isPrint) {
    await evaluate(client, `document.documentElement.dataset.theme = ${JSON.stringify(mode)}`);
  } else {
    await evaluate(client, "document.documentElement.dataset.theme = 'dark'");
  }
  const themeToggleWorks = isPrint ? true : await verifyThemeToggle(client);
  const inspection = await inspectPage(client);
  const backToTop = await inspectBackToTop(client);
  const backToTopScreenshot = join(outputDir, `${viewport.id}-${mode}-back-to-top.png`);
  const backToTopInteraction = isPrint
    ? { pageCanScroll: true, revealed: true, returnedToTop: true }
    : await verifyBackToTopInteraction(client, backToTopScreenshot);
  const keyboardFocus = await verifyKeyboardFocus(client);
  const screenshot = join(outputDir, `${viewport.id}-${mode}.png`);
  await capture(client, screenshot, viewport.width, viewport.height);
  const printIsLight = !isPrint || String(inspection.colorScheme).split(" ")[0] === "light";
  return {
    id: `${viewport.id}-${mode}`,
    viewport,
    mode,
    screenshot,
    inspection,
    backToTop,
    backToTopInteraction,
    keyboardFocus,
    assertions: {
      uniqueH1: inspection.h1Count === 1,
      uniqueIds: inspection.duplicateIds.length === 0,
      internalLinksValid: inspection.brokenInternalLinks.length === 0,
      noPageOverflow: !inspection.pageOverflow,
      contentPresent: inspection.textLength > 100,
      requestedViewportApplied:
        inspection.viewportWidth <= viewport.width + 1 &&
        inspection.viewportWidth >= viewport.width - 20 &&
        inspection.viewportHeight <= viewport.height + 1 &&
        inspection.visualViewportWidth <= viewport.width + 1 &&
        inspection.visualViewportWidth >= viewport.width - 20 &&
        inspection.visualViewportHeight <= viewport.height + 1,
      keyboardFocus,
      printIsLight,
      themeToggleWorks,
      backToTopContract:
        backToTop.count === 1 &&
        backToTop.href === "#report-top" &&
        backToTop.targetCount === 1 &&
        ["回到顶部", "Back to top"].includes(backToTop.label),
      backToTopPrintHidden: !isPrint || backToTop.visible === false,
      backToTopRevealsAfterScroll: isPrint || backToTopInteraction.revealed,
      backToTopReturnsToTop: isPrint || backToTopInteraction.returnedToTop,
      tableContainersKeyboardReachable:
        inspection.tableMetrics.length > 0 &&
        inspection.tableMetrics.every((table) => table.containerKeyboardReachable),
      tableOverflowContained: inspection.tableMetrics.every((table) => table.overflowContained),
      adaptiveWidthsApplied: isPrint
        ? inspection.tableMetrics
            .flatMap((table) => table.expandedColumns)
            .every((column) => column.minWidth <= 0.5 && column.whiteSpace === "normal")
        : inspection.tableMetrics
            .flatMap((table) => table.expandedColumns)
            .every(
              (column) =>
                column.expectedPixels !== null &&
                column.minWidth >= column.expectedPixels - 1 &&
                column.actualWidth >= column.expectedPixels - 1
            ),
    },
  };
}


async function runNoJavaScriptScenario(client, htmlUrl, outputDir) {
  const viewport = VIEWPORTS[2];
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: viewport.width,
    height: viewport.height,
    deviceScaleFactor: 1,
    mobile: true,
    screenWidth: viewport.width,
    screenHeight: viewport.height,
    scale: 1,
  });
  await client.send("Emulation.setEmulatedMedia", {
    media: "screen",
    features: [{ name: "prefers-color-scheme", value: "light" }],
  });
  await client.send("Emulation.setScriptExecutionDisabled", { value: true });
  await navigate(client, "about:blank");
  await navigate(client, `${htmlUrl}#no-js`);
  const inspection = await inspectPage(client);
  const backToTop = await inspectBackToTop(client);
  await evaluate(client, "document.documentElement.scrollTop = document.documentElement.scrollHeight");
  await new Promise((resolvePromise) => setTimeout(resolvePromise, 250));
  const backToTopAfterScroll = await inspectBackToTop(client);
  const noJsBackToTopScreenshot = join(outputDir, "mobile-no-js-back-to-top.png");
  await captureViewport(client, noJsBackToTopScreenshot);
  if (backToTopAfterScroll.rect) {
    const clickX = (backToTopAfterScroll.rect.left + backToTopAfterScroll.rect.right) / 2;
    const clickY = (backToTopAfterScroll.rect.top + backToTopAfterScroll.rect.bottom) / 2;
    await client.send("Input.dispatchMouseEvent", {
      type: "mousePressed",
      x: clickX,
      y: clickY,
      button: "left",
      clickCount: 1,
    });
    await client.send("Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x: clickX,
      y: clickY,
      button: "left",
      clickCount: 1,
    });
  }
  let noJsScrollY = Number.POSITIVE_INFINITY;
  const noJsDeadline = Date.now() + NAVIGATION_SETTLE_TIMEOUT_MS;
  while (Date.now() < noJsDeadline) {
    noJsScrollY = await evaluate(client, "window.scrollY");
    if (noJsScrollY <= 1) break;
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 50));
  }
  const screenshot = join(outputDir, "mobile-no-js.png");
  await capture(client, screenshot, viewport.width, viewport.height);
  await client.send("Emulation.setScriptExecutionDisabled", { value: false });
  return {
    id: "mobile-no-js",
    viewport,
    mode: "no-js",
    screenshot,
    inspection,
    backToTop,
    backToTopAfterScroll,
    backToTopScreenshot: noJsBackToTopScreenshot,
    noJsScrollY,
    assertions: {
      uniqueH1: inspection.h1Count === 1,
      uniqueIds: inspection.duplicateIds.length === 0,
      internalLinksValid: inspection.brokenInternalLinks.length === 0,
      noPageOverflow: !inspection.pageOverflow,
      contentPresent: inspection.textLength > 100,
      requestedViewportApplied:
        inspection.viewportWidth <= viewport.width + 1 &&
        inspection.viewportWidth >= viewport.width - 20 &&
        inspection.viewportHeight <= viewport.height + 1 &&
        inspection.visualViewportWidth <= viewport.width + 1 &&
        inspection.visualViewportWidth >= viewport.width - 20 &&
        inspection.visualViewportHeight <= viewport.height + 1,
      backToTopNoJsVisibleAndUsable:
        backToTop.count === 1 &&
        backToTop.href === "#report-top" &&
        backToTop.targetCount === 1 &&
        backToTopAfterScroll.visible === true &&
        noJsScrollY <= 1,
      tableContainersKeyboardReachable:
        inspection.tableMetrics.length > 0 &&
        inspection.tableMetrics.every((table) => table.containerKeyboardReachable),
      tableOverflowContained: inspection.tableMetrics.every((table) => table.overflowContained),
      adaptiveWidthsApplied: inspection.tableMetrics
        .flatMap((table) => table.expandedColumns)
        .every(
          (column) =>
            column.expectedPixels !== null &&
            column.minWidth >= column.expectedPixels - 1 &&
            column.actualWidth >= column.expectedPixels - 1
        ),
    },
  };
}


async function main() {
  const args = parseArgs(process.argv.slice(2));
  await mkdir(args.outputDir, { recursive: true });
  const port = await reservePort();
  const profileDir = await mkdtemp(join(tmpdir(), "amazon-html-visual-qa-"));
  const chrome = spawn(
    args.chromePath,
    [
      "--headless=new",
      "--remote-debugging-address=127.0.0.1",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profileDir}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-background-networking",
      "--disable-component-update",
      "--disable-sync",
      "--metrics-recording-only",
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"], windowsHide: true }
  );
  let browserStderr = "";
  chrome.stderr.on("data", (chunk) => {
    browserStderr += String(chunk);
  });

  let client;
  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`);
    const page = await openPage(port);
    client = new CdpClient(page.webSocketDebuggerUrl);
    await client.connect();
    await Promise.all([
      client.send("Page.enable"),
      client.send("Runtime.enable"),
      client.send("Log.enable"),
      client.send("Network.enable"),
    ]);

    const consoleIssues = [];
    const pageExceptions = [];
    const externalRequests = [];
    client.on("Runtime.consoleAPICalled", (event) => {
      if (["error", "warning"].includes(event.type)) consoleIssues.push(event.type);
    });
    client.on("Runtime.exceptionThrown", (event) => {
      pageExceptions.push(event.exceptionDetails?.text || "exception");
    });
    client.on("Network.requestWillBeSent", (event) => {
      const url = event.request?.url || "";
      if (!/^(?:file:|data:|about:|devtools:)/i.test(url)) externalRequests.push(url);
    });

    const htmlUrl = pathToFileURL(args.htmlPath).href;
    const scenarios = [];
    for (const viewport of VIEWPORTS) {
      for (const mode of ["light", "dark", "print"]) {
        scenarios.push(await runScenario(client, htmlUrl, args.outputDir, viewport, mode));
      }
    }
    scenarios.push(await runNoJavaScriptScenario(client, htmlUrl, args.outputDir));

    const scenarioPass = scenarios.every((scenario) =>
      Object.values(scenario.assertions).every(Boolean)
    );
    const receipt = {
      runner: "tests/run_visual_qa.mjs",
      input: basename(args.htmlPath),
      status:
        scenarioPass && consoleIssues.length === 0 && pageExceptions.length === 0 && externalRequests.length === 0
          ? "PASS"
          : "FAIL",
      scenarios,
      consoleIssues,
      pageExceptions,
      externalRequests: [...new Set(externalRequests)],
    };
    const receiptPath = join(args.outputDir, "visual-qa-receipt.json");
    await writeFile(receiptPath, JSON.stringify(receipt, null, 2) + "\n", "utf8");
    process.stdout.write(
      JSON.stringify({ ok: receipt.status === "PASS", status: receipt.status, receipt: receiptPath }) + "\n"
    );
    return receipt.status === "PASS" ? 0 : 1;
  } finally {
    client?.close();
    chrome.kill();
    await new Promise((resolvePromise) => {
      const timer = setTimeout(resolvePromise, 2_000);
      chrome.once("exit", () => {
        clearTimeout(timer);
        resolvePromise();
      });
    });
    await removeDirectoryWithRetry(profileDir);
    if (browserStderr && process.env.VISUAL_QA_DEBUG === "1") {
      process.stderr.write(browserStderr);
    }
  }
}


main()
  .then((exitCode) => {
    process.exitCode = exitCode;
  })
  .catch((error) => {
    process.stdout.write(JSON.stringify({ ok: false, status: "ERROR", error: error.message }) + "\n");
    process.exitCode = 2;
  });
