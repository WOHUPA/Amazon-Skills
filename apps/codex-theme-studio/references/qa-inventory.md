# QA inventory

## User-visible claims

1. The home screen paints one UI-free wallpaper continuously across sidebar and main content, with a live native heading, the real project utility/composer surface, and any suggestion cards rendered by the current Codex host.
2. Sidebar, right-side chrome, composer, dialogs, cards, and secondary surfaces use clear alpha transparency without backdrop blur or opaque fills.
3. All real Codex controls remain interactive; the skin is not a screenshot overlay.
4. The skin survives route changes and renderer reloads while the injector daemon runs.
5. The official Store package and `app.asar` remain unchanged.
6. Restore removes the injected DOM/CSS and install/restore can be repeated.
7. Restore closes the saved CDP listener before reopening Codex normally.

## Functional checks

- Home feature card: click one card and confirm the real composer is populated or the normal action occurs.
- Project selector: click the real project chip under the "选择项目" label and confirm the native project menu opens.
- Sidebar: open a real task, then return to New Task.
- Task side panel: open and close the native thread panel twice, resize the window, and repeat; the toggle must remain visible and clickable.
- Composer: type text, verify caret/readability, then clear it without sending.
- Reload: use CDP `Page.reload`, wait, and confirm the injection marker returns.
- Pet overlay: open a desktop pet and confirm its auxiliary window stays transparent with no skin background or decoration layer behind it.
- Restore/reapply cycle: remove live skin, verify marker absent, apply again, verify marker present.
- Update resilience: resolve the current `OpenAI.Codex` Appx location dynamically for launch. A versioned path saved for cleanup must be revalidated against the registered package full/family identity before any process is stopped.
- Restart consent: an existing normal Codex window is never force-closed without explicit CLI authorization or shortcut confirmation.
- Shortcut policy: installed launch, restore, tray, and tray-child commands use `RemoteSigned` without `Bypass`; Internet-zone markers are removed only from hash-verified managed PowerShell copies.
- Config safety: Chinese project names, LF/CRLF choice, quoted target keys, table-header comments, and unrelated TOML sections survive install/selective restore; ambiguous target shapes fail unchanged, exact recovery keeps a copy of the replaced current file, and install refuses both registered and state-recorded old Codex processes.
- Theme safety: empty/over-16 MB images, over-16384px/50MP dimensions, path escapes, symlinks/junctions, malformed JSON, and unsupported formats are rejected before payload construction.
- Tray lifecycle: pause/resume reflects the clicked state, bundled Xiao Yan Inferno theme is present on first install, and complete restore terminates any separately launched tray before it can reapply the skin.
- Tray performance: a real ephemeral loopback listener must be returned by the native TCP table lookup with the current process PID; live-session refresh must retain both ownership checks without blocking on CIM.

## Visual checks

- 1280x820 initial home: the declared focus stays in frame, the text-safe side remains readable, the real project utility row and composer form one coherent surface, and no horizontal scrolling appears.
- Narrower window: accept Codex's native responsive card reduction or omission; no essential control is covered and wallpaper cropping preserves the focus/safe-area contract.
- Normal task: the wallpaper is visibly quieter than home, messages keep high contrast, and composer does not overlap content.
- Transparency consistency: sidebar and right-side chrome share color family, alpha, border, and shadow language without blur; composer and dialog surfaces are also visibly translucent and unblurred, while text, icons, caret, and focus states stay fully opaque.
- Inspect the sidebar, header, wallpaper edges, native card labels when present, project utility row, composer controls, scrollbar, dialogs, and menus.
- Reject black/transparent sidebar artifacts, clipped controls, duplicated/disconnected project labels, rasterized native controls, fake UI inside the wallpaper, weak contrast, or decorations intercepting clicks.

## Strict visual publication gate

- PR profile: `immersive-dark`, `clear-light`, `obsidian-gold` across `home/task/project-menu/app-menu/dialog/task-sidebar` and all nine narrow/standard/wide × 100%/125%/150% pairwise variants. This is 162 cases and 648 required artifacts.
- Release profile: all 12 bundled themes across home/task at standard-100, totaling 24 cases and 96 required artifacts.
- Each case must have a PNG plus `rects.json`, `styles.json`, and `contrast.json`. Missing evidence is `PARTIAL`; malformed or non-`COMPLETE` evidence is `BLOCKED`; only a completely populated directory is publishable.
- `rects.json` must contain complete scene and geometry audits. `styles.json` must contain complete component styles and every required semantic state. `contrast.json` must contain complete ratios. A valid PNG signature alone does not prove a pass.
- Run `node scripts/injector.mjs --visual-gate pr --evidence-dir <目录>` for PRs and replace `pr` with `release` before publication.
- A visual defect is fixed in this order: reproduce it as a red scene fixture, update only the trusted adapter/runtime, rerun gates, then obtain human approval for the changed baseline.

## Exploratory checks

- Start when the debug port is occupied: fail with a clear message or use a caller-selected port.
- Start after Codex updates: package discovery and injection still work without patching installed files.
- Tamper `state.json` with a reused PID: if the PID is still live but its identity differs, confirm cleanup fails closed and preserves `state.json`; if the PID is gone, confirm the stale record is replaced only after confirming no process is running, without stopping an unrelated process.
- Serve a fake `app://` CDP target or remote/mismatched WebSocket URL and confirm both launcher and injector reject it. Reuse the port with a new Browser ID and confirm the existing watcher exits without reconnecting.
- Force verification failure and confirm the injector, state file, and newly launched debug session are rolled back.
- Start two operations concurrently and confirm the second fails clearly without changing config, state, or processes.
- Close Codex without restore and confirm the Browser identity anchor closes and the watcher exits without reconnecting or rapidly growing logs.

## Automated checks

- `tests/run-tests.ps1`: strict UTF-8/no-BOM writes, UTF-16 rejection, LF/CRLF preservation, concurrent-write detection, exact backup/recovery, `[desktop]`-scoped restore, ambiguous TOML rejection, non-ASCII paths, Appx/state identity, argument quoting, theme seeding/import/save/switch/pause, byte/dimension limits, junction rejection, payload construction, Browser ID, loopback URL rejection, renderer isolation for transparent auxiliary windows, exact host-adapter resolution, geometry failures, strict `PARTIAL` rejection and evidence-directory gating.
- `node --check` for the injector and renderer payload.
- Live Windows signoff remains required for Store process ownership, restart consent, screenshot, and CDP closure.
