# Codex Theme Studio

A Windows runtime for pure-data Theme Pack v2 packages. It applies backgrounds, semantic icons, palette, materials, and versioned allowlisted layouts over validated loopback CDP without modifying WindowsApps, `app.asar`, signatures, or authentication data. Version 2.2 fails closed: only `COMPLETE` is publishable, unknown hosts fall back to native geometry with `BLOCKED`, and missing visual evidence is `PARTIAL`.

Use `scripts/theme-studio.ps1` with `list`, `preview`, `import`, `activate`, `rollback`, `pause`, `resume`, `verify`, `restore`, `install`, or `update`. Runtime state lives below `%LOCALAPPDATA%\CodexThemeStudio`.

PR and release evidence gates use `node scripts/injector.mjs --visual-gate pr|release --evidence-dir <directory>`. Every case requires a screenshot, component rectangles, computed styles, and contrast results.
