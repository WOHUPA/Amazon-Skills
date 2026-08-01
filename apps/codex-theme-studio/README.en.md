# Codex Theme Studio

A Windows runtime for pure-data Theme Pack v2 packages. It applies backgrounds, semantic icons, palette, materials, and versioned allowlisted layouts over validated loopback CDP without modifying WindowsApps, `app.asar`, signatures, or authentication data. Version 2.2 fails closed: only `COMPLETE` is publishable, unknown hosts fall back to native geometry with `BLOCKED`, and missing visual evidence is `PARTIAL`.

Use the installed `CodexThemeStudio.exe --engine <action>` interface with `--package`, `--theme`, `--confirm`, and `--result-file`. Theme Bundle v1 files use the `.codextheme` extension; imports are atomic and never auto-activate. Runtime state, Catalog v1, backups, and private thumbnails live below `%LOCALAPPDATA%\CodexThemeStudio`.

Windows releases use a WiX MSI with a transactional helper updater. A temporary Inno Setup EXE bridge remains available for upgrades from the 2.5.x install line. Update artifacts require SHA-256 and Minisign verification before Windows Installer is started.

PR and release evidence gates use `node scripts/injector.mjs --visual-gate pr|release --evidence-dir <directory>`. Every case requires a screenshot, component rectangles, computed styles, and contrast results.
