using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

namespace CodexThemeStudio.Desktop
{
    internal sealed class BundlePreview
    {
        public string BundleId;
        public string Name;
        public string SeriesId;
        public string SeriesName;
        public readonly List<string> ThemeIds = new List<string>();
        public readonly List<string> Conflicts = new List<string>();
        public long ExtractedBytes;
    }

    internal sealed class ThemeBundleManager
    {
        private const long MaxArchiveBytes = 256L * 1024L * 1024L;
        private const long MaxExtractedBytes = 512L * 1024L * 1024L;
        private const int MaxEntries = 4096;
        private const int MaxThemes = 100;
        private static readonly Regex SafeId = new Regex("^[a-z0-9]+(?:-[a-z0-9]+)*$", RegexOptions.CultureInvariant);
        private static readonly HashSet<string> ExecutableExtensions = new HashSet<string>(
            new[] { ".exe", ".dll", ".ps1", ".bat", ".cmd", ".com", ".msi", ".js", ".mjs", ".vbs", ".scr", ".lnk" },
            StringComparer.OrdinalIgnoreCase);
        private readonly string stateRoot;
        private readonly string themesRoot;
        private readonly JavaScriptSerializer serializer = new JavaScriptSerializer { MaxJsonLength = 16 * 1024 * 1024 };

        public ThemeBundleManager(string stateRoot, string themesRoot)
        {
            this.stateRoot = Path.GetFullPath(stateRoot);
            this.themesRoot = Path.GetFullPath(themesRoot);
        }

        public BundlePreview Preview(string packagePath)
        {
            string fullPath = ValidatePackagePath(packagePath);
            using (ZipArchive archive = ZipFile.OpenRead(fullPath))
                return ParseAndValidateManifest(archive);
        }

        public BundlePreview Import(string packagePath, ThemeCatalog catalog)
        {
            string fullPath = ValidatePackagePath(packagePath);
            string staging = Path.Combine(stateRoot, ".bundle-import-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(staging);
            List<string> committed = new List<string>();
            try
            {
                BundlePreview preview;
                using (ZipArchive archive = ZipFile.OpenRead(fullPath))
                {
                    preview = ParseAndValidateManifest(archive);
                    if (preview.Conflicts.Count > 0)
                        throw new InvalidOperationException("主题 ID 冲突，整包未导入：" + string.Join(", ", preview.Conflicts));
                    ExtractVerified(archive, staging, preview);
                }
                foreach (string themeId in preview.ThemeIds)
                    ThemePackageValidator.Validate(Path.Combine(staging, "themes", themeId), themeId, serializer);

                foreach (string themeId in preview.ThemeIds)
                {
                    string source = Path.Combine(staging, "themes", themeId);
                    string destination = Path.Combine(themesRoot, themeId);
                    if (Directory.Exists(destination)) throw new IOException("提交前检测到主题冲突：" + themeId);
                    Directory.Move(source, destination);
                    committed.Add(destination);
                }
                try { catalog.AssignImported(preview.SeriesId, preview.SeriesName, preview.ThemeIds); }
                catch
                {
                    foreach (string path in committed) DeleteDirectory(path);
                    throw;
                }
                return preview;
            }
            finally
            {
                DeleteDirectory(staging);
            }
        }

        private BundlePreview ParseAndValidateManifest(ZipArchive archive)
        {
            if (archive.Entries.Count > MaxEntries) throw new InvalidDataException("Bundle 文件数量超过限制。");
            ZipArchiveEntry manifestEntry = archive.GetEntry("bundle.json");
            if (manifestEntry == null || manifestEntry.Length > 1024 * 1024)
                throw new InvalidDataException("Bundle 必须包含不超过 1 MB 的 bundle.json。");
            Dictionary<string, object> manifest;
            using (StreamReader reader = new StreamReader(manifestEntry.Open(), new UTF8Encoding(false, true)))
                manifest = serializer.DeserializeObject(reader.ReadToEnd()) as Dictionary<string, object>;
            if (manifest == null) throw new InvalidDataException("bundle.json 不是有效对象。");
            RequireExactKeys(manifest, "bundle.json", "schemaVersion", "bundleId", "name", "series", "themes", "files");
            if (Convert.ToInt32(manifest["schemaVersion"]) != 1) throw new InvalidDataException("仅支持 Bundle v1。");

            BundlePreview preview = new BundlePreview {
                BundleId = RequireId(manifest, "bundleId", 80),
                Name = RequireName(manifest, "name")
            };
            Dictionary<string, object> series = manifest["series"] as Dictionary<string, object>;
            if (series == null) throw new InvalidDataException("series 必须是对象。");
            RequireExactKeys(series, "series", "id", "name");
            preview.SeriesId = RequireId(series, "id", 80);
            preview.SeriesName = RequireName(series, "name");

            object[] themes = manifest["themes"] as object[];
            if (themes == null || themes.Length == 0 || themes.Length > MaxThemes)
                throw new InvalidDataException("Bundle 必须包含 1-100 个主题。");
            HashSet<string> themeIds = new HashSet<string>(StringComparer.Ordinal);
            foreach (object raw in themes)
            {
                Dictionary<string, object> item = raw as Dictionary<string, object>;
                if (item == null) throw new InvalidDataException("themes 项必须是对象。");
                RequireExactKeys(item, "themes item", "id", "path");
                string id = RequireId(item, "id", 48);
                string path = Convert.ToString(item["path"]);
                if (!string.Equals(path, "themes/" + id, StringComparison.Ordinal))
                    throw new InvalidDataException("主题路径必须精确匹配 themes/<id>。");
                if (!themeIds.Add(id)) throw new InvalidDataException("Bundle 包含重复主题 ID：" + id);
                preview.ThemeIds.Add(id);
                if (Directory.Exists(Path.Combine(themesRoot, id))) preview.Conflicts.Add(id);
            }

            object[] files = manifest["files"] as object[];
            if (files == null || files.Length == 0 || files.Length > MaxEntries)
                throw new InvalidDataException("files 清单为空或超过限制。");
            HashSet<string> declaredPaths = new HashSet<string>(StringComparer.Ordinal);
            long total = 0;
            foreach (object raw in files)
            {
                Dictionary<string, object> item = raw as Dictionary<string, object>;
                if (item == null) throw new InvalidDataException("files 项必须是对象。");
                RequireExactKeys(item, "files item", "path", "size", "sha256");
                string path = ValidateArchivePath(Convert.ToString(item["path"]));
                if (!preview.ThemeIds.Any(id => path.StartsWith("themes/" + id + "/", StringComparison.Ordinal)))
                    throw new InvalidDataException("文件不属于清单声明的主题：" + path);
                if (ExecutableExtensions.Contains(Path.GetExtension(path)))
                    throw new InvalidDataException("Bundle 不允许可执行文件：" + path);
                long size = Convert.ToInt64(item["size"]);
                if (size < 0 || size > 80L * 1024L * 1024L) throw new InvalidDataException("文件大小超过限制：" + path);
                string hash = Convert.ToString(item["sha256"]);
                if (!Regex.IsMatch(hash ?? string.Empty, "^[a-f0-9]{64}$", RegexOptions.CultureInvariant))
                    throw new InvalidDataException("SHA-256 格式无效：" + path);
                if (!declaredPaths.Add(path)) throw new InvalidDataException("重复文件路径：" + path);
                total = checked(total + size);
                if (total > MaxExtractedBytes) throw new InvalidDataException("Bundle 解压总大小超过 512 MB。");
            }
            preview.ExtractedBytes = total;

            HashSet<string> actualPaths = new HashSet<string>(
                archive.Entries.Where(entry => !string.IsNullOrEmpty(entry.Name) && entry.FullName != "bundle.json")
                    .Select(entry => ValidateArchivePath(entry.FullName)),
                StringComparer.Ordinal);
            if (!actualPaths.SetEquals(declaredPaths))
                throw new InvalidDataException("ZIP 内容与 files 清单不一致。");
            return preview;
        }

        private void ExtractVerified(ZipArchive archive, string staging, BundlePreview preview)
        {
            Dictionary<string, Dictionary<string, object>> declarations = new Dictionary<string, Dictionary<string, object>>(StringComparer.Ordinal);
            Dictionary<string, object> manifest;
            using (StreamReader reader = new StreamReader(archive.GetEntry("bundle.json").Open(), new UTF8Encoding(false, true)))
                manifest = serializer.DeserializeObject(reader.ReadToEnd()) as Dictionary<string, object>;
            foreach (object raw in (object[])manifest["files"])
            {
                Dictionary<string, object> item = (Dictionary<string, object>)raw;
                declarations[Convert.ToString(item["path"])] = item;
            }

            string rootPrefix = Path.GetFullPath(staging).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            foreach (ZipArchiveEntry entry in archive.Entries)
            {
                if (string.IsNullOrEmpty(entry.Name) || entry.FullName == "bundle.json") continue;
                string relative = ValidateArchivePath(entry.FullName);
                Dictionary<string, object> declaration = declarations[relative];
                long expectedSize = Convert.ToInt64(declaration["size"]);
                if (entry.Length != expectedSize) throw new InvalidDataException("文件大小与清单不符：" + relative);
                if (entry.Length > 1024 * 1024 && entry.CompressedLength > 0 && entry.Length / Math.Max(1, entry.CompressedLength) > 200)
                    throw new InvalidDataException("检测到异常压缩比：" + relative);
                string destination = Path.GetFullPath(Path.Combine(staging, relative.Replace('/', Path.DirectorySeparatorChar)));
                if (!destination.StartsWith(rootPrefix, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("检测到 ZIP 路径逃逸：" + relative);
                Directory.CreateDirectory(Path.GetDirectoryName(destination));
                using (Stream input = entry.Open())
                using (FileStream output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                using (SHA256 sha = SHA256.Create())
                {
                    byte[] buffer = new byte[1024 * 1024];
                    int read;
                    long written = 0;
                    while ((read = input.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        written += read;
                        if (written > expectedSize) throw new InvalidDataException("解压大小超过清单声明：" + relative);
                        output.Write(buffer, 0, read);
                        sha.TransformBlock(buffer, 0, read, null, 0);
                    }
                    sha.TransformFinalBlock(new byte[0], 0, 0);
                    string actual = BitConverter.ToString(sha.Hash).Replace("-", string.Empty).ToLowerInvariant();
                    if (written != expectedSize || !string.Equals(actual, Convert.ToString(declaration["sha256"]), StringComparison.Ordinal))
                        throw new InvalidDataException("文件 SHA-256 校验失败：" + relative);
                }
            }
        }

        private static string ValidatePackagePath(string packagePath)
        {
            if (string.IsNullOrWhiteSpace(packagePath)) throw new InvalidDataException("未指定 .codextheme 文件。");
            string fullPath = Path.GetFullPath(packagePath);
            if (!File.Exists(fullPath)) throw new FileNotFoundException("主题 Bundle 不存在。", fullPath);
            if (!string.Equals(Path.GetExtension(fullPath), ".codextheme", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("主题 Bundle 必须使用 .codextheme 扩展名。");
            FileInfo info = new FileInfo(fullPath);
            if (info.Length <= 0 || info.Length > MaxArchiveBytes) throw new InvalidDataException("主题 Bundle 大小超过 256 MB。");
            if ((info.Attributes & FileAttributes.ReparsePoint) != 0) throw new IOException("主题 Bundle 不能是链接或重解析点。");
            return fullPath;
        }

        private static string ValidateArchivePath(string path)
        {
            if (string.IsNullOrWhiteSpace(path) || path.Contains("\\") || path.StartsWith("/", StringComparison.Ordinal) ||
                path.Split('/').Any(part => part.Length == 0 || part == "." || part == "..") || Path.IsPathRooted(path))
                throw new InvalidDataException("Bundle 包含不安全路径：" + path);
            return path;
        }

        private static string RequireId(Dictionary<string, object> item, string key, int maximum)
        {
            string value = item.ContainsKey(key) ? Convert.ToString(item[key]) : string.Empty;
            if (string.IsNullOrWhiteSpace(value) || value.Length > maximum || !SafeId.IsMatch(value))
                throw new InvalidDataException(key + " 格式无效。");
            return value;
        }

        private static string RequireName(Dictionary<string, object> item, string key)
        {
            string value = item.ContainsKey(key) ? Convert.ToString(item[key]).Trim() : string.Empty;
            if (value.Length == 0 || value.Length > 80) throw new InvalidDataException(key + " 必须为 1-80 个字符。");
            return value;
        }

        private static void RequireExactKeys(Dictionary<string, object> item, string label, params string[] expected)
        {
            HashSet<string> keys = new HashSet<string>(item.Keys, StringComparer.Ordinal);
            if (!keys.SetEquals(expected)) throw new InvalidDataException(label + " 包含未知字段或缺少必填字段。");
        }

        private static void DeleteDirectory(string path)
        {
            try { if (Directory.Exists(path)) Directory.Delete(path, true); } catch { }
        }
    }

    internal static class ThemePackageValidator
    {
        private static readonly Regex SafeId = new Regex("^[a-z0-9]+(?:-[a-z0-9]+)*$", RegexOptions.CultureInvariant);
        private static readonly string[] TopLevelKeys = {
            "schemaVersion", "id", "name", "appearance", "assets", "palette", "materials",
            "layout", "art", "compatibility", "provenance"
        };
        private static readonly string[] IconSlots = {
            "newTask", "search", "projects", "history", "attach", "send", "settings", "skills"
        };

        public static void Validate(string root, string expectedId, JavaScriptSerializer serializer)
        {
            string fullRoot = Path.GetFullPath(root);
            string metadataPath = Path.Combine(fullRoot, "theme.json");
            if (!File.Exists(metadataPath)) throw new InvalidDataException("主题包缺少 theme.json。");
            Dictionary<string, object> theme = serializer.DeserializeObject(File.ReadAllText(metadataPath, Encoding.UTF8)) as Dictionary<string, object>;
            if (theme == null) throw new InvalidDataException("theme.json 不是有效对象。");
            RequireExact(theme, TopLevelKeys);
            if (Convert.ToInt32(theme["schemaVersion"]) != 2) throw new InvalidDataException("仅支持 Theme Pack v2。");
            string id = Convert.ToString(theme["id"]);
            if (!SafeId.IsMatch(id ?? string.Empty) || id.Length > 48 || id != expectedId)
                throw new InvalidDataException("主题包 ID 与目录不一致。");
            string name = Convert.ToString(theme["name"]).Trim();
            if (name.Length == 0 || name.Length > 80) throw new InvalidDataException("主题名称无效。");
            string appearance = Convert.ToString(theme["appearance"]);
            if (appearance != "dark" && appearance != "light" && appearance != "auto")
                throw new InvalidDataException("主题 appearance 无效。");

            Dictionary<string, object> assets = RequireObject(theme, "assets");
            RequireExact(assets, "homeBackground", "taskBackground", "icons");
            ValidateAsset(fullRoot, assets["homeBackground"], false);
            ValidateAsset(fullRoot, assets["taskBackground"], false);
            Dictionary<string, object> icons = RequireObject(assets, "icons");
            RequireExact(icons, IconSlots);
            foreach (string slot in IconSlots) ValidateAsset(fullRoot, icons[slot], true);

            RequireObject(theme, "palette");
            RequireObject(theme, "materials");
            RequireObject(theme, "layout");
            RequireObject(theme, "art");
            RequireObject(theme, "compatibility");
            RequireObject(theme, "provenance");
            if (!File.Exists(Path.Combine(fullRoot, "preview.html")) || !File.Exists(Path.Combine(fullRoot, "README.md")))
                throw new InvalidDataException("主题包缺少 preview.html 或 README.md。");
            if (!File.Exists(Path.Combine(fullRoot, "native-theme.json")) && !File.Exists(Path.Combine(fullRoot, "native-theme-dark.json")))
                throw new InvalidDataException("主题包缺少原生主题输出。");
        }

        private static void ValidateAsset(string root, object raw, bool icon)
        {
            if (raw == null) return;
            string relative = Convert.ToString(raw);
            if (string.IsNullOrEmpty(relative)) return;
            if (relative.Contains("\\") || relative.StartsWith("/", StringComparison.Ordinal) ||
                relative.Split('/').Any(part => part == ".." || part == "." || part.Length == 0))
                throw new InvalidDataException("主题资源路径不安全：" + relative);
            string full = Path.GetFullPath(Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar)));
            string prefix = root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            if (!full.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) || !File.Exists(full))
                throw new InvalidDataException("主题资源不存在：" + relative);
            FileInfo info = new FileInfo(full);
            if ((info.Attributes & FileAttributes.ReparsePoint) != 0 || info.Length > (icon ? 256 * 1024 : 80L * 1024L * 1024L))
                throw new InvalidDataException("主题资源大小或类型不安全：" + relative);
            string extension = Path.GetExtension(full);
            if (icon)
            {
                if (extension.Equals(".svg", StringComparison.OrdinalIgnoreCase))
                {
                    string svg = File.ReadAllText(full, Encoding.UTF8).ToLowerInvariant();
                    string[] forbidden = { "<script", "javascript:", "foreignobject", "<image", "onload=", "onerror=", "href=\"http", "href='http", "xlink:href" };
                    if (forbidden.Any(value => svg.Contains(value))) throw new InvalidDataException("SVG 包含不安全内容：" + relative);
                }
                else if (!extension.Equals(".png", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("图标仅支持 SVG 或 PNG：" + relative);
            }
            else
            {
                if (!extension.Equals(".png", StringComparison.OrdinalIgnoreCase) &&
                    !extension.Equals(".jpg", StringComparison.OrdinalIgnoreCase) &&
                    !extension.Equals(".jpeg", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("背景仅支持 PNG 或 JPEG：" + relative);
                using (Image image = Image.FromFile(full))
                {
                    if (image.Width > 7680 || image.Height > 4320)
                        throw new InvalidDataException("背景解码尺寸超过 7680×4320：" + relative);
                }
            }
        }

        private static Dictionary<string, object> RequireObject(Dictionary<string, object> parent, string key)
        {
            Dictionary<string, object> value = parent.ContainsKey(key) ? parent[key] as Dictionary<string, object> : null;
            if (value == null) throw new InvalidDataException(key + " 必须是对象。");
            return value;
        }

        private static void RequireExact(Dictionary<string, object> item, params string[] keys)
        {
            if (!new HashSet<string>(item.Keys, StringComparer.Ordinal).SetEquals(keys))
                throw new InvalidDataException("Theme Pack v2 包含未知字段或缺少必填字段。");
        }
    }
}
