using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

namespace CodexThemeStudio.Desktop
{
    // Maps the public Recipe v1 model into the narrower, verified Theme Pack v2 model.
    // Recipe content is data only: it can never carry CSS, code, commands, or activation intent.
    internal sealed class RecipeThemeCompiler
    {
        private static readonly Regex SafeImageExtension = new Regex("^\\.(png|jpe?g)$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        private readonly string engineRoot;
        private readonly string themesRoot;
        private readonly JavaScriptSerializer serializer;

        public RecipeThemeCompiler(string engineRoot, string themesRoot, JavaScriptSerializer serializer)
        {
            this.engineRoot = Path.GetFullPath(engineRoot);
            this.themesRoot = Path.GetFullPath(themesRoot);
            this.serializer = serializer;
        }

        public RecipeCompilation Create(string recipePath, string imagePath)
        {
            string recipe = ValidateFile(recipePath, ".json", 1024 * 1024, "主题配方");
            string image = ValidateImage(imagePath);
            Dictionary<string, object> source = serializer.DeserializeObject(File.ReadAllText(recipe, Encoding.UTF8)) as Dictionary<string, object>;
            if (source == null) throw new InvalidDataException("主题配方必须是 JSON 对象。");
            ValidateRecipe(source);

            string name = RequireText(source, "name", 80);
            string appearance = GetNestedText(source, "paletteIntent", "appearance", "dark");
            string density = GetNestedText(source, "appearance", "density", "normal");
            if (appearance != "dark" && appearance != "light") throw new InvalidDataException("paletteIntent.appearance 必须为 dark 或 light。");
            if (density != "compact" && density != "normal" && density != "spacious") throw new InvalidDataException("appearance.density 无效。");

            string id = "recipe-" + ShortHash(File.ReadAllBytes(recipe), File.ReadAllBytes(image));
            string destination = Path.Combine(themesRoot, id);
            if (Directory.Exists(destination)) throw new InvalidOperationException("相同配方和图片已经生成主题：" + id + "。请使用不同图片或直接导入该主题。");
            string template = Path.Combine(engineRoot, "presets", appearance == "light" ? "clear-light" : "immersive-dark");
            if (!File.Exists(Path.Combine(template, "theme.json"))) throw new FileNotFoundException("缺少内置主题模板。", template);
            string staging = Path.Combine(themesRoot, ".recipe-" + Guid.NewGuid().ToString("N"));
            try
            {
                CopyDirectory(template, staging);
                string assetRelative = "assets/recipe-background" + Path.GetExtension(image).ToLowerInvariant();
                File.Copy(image, Path.Combine(staging, assetRelative.Replace('/', Path.DirectorySeparatorChar)), false);
                Dictionary<string, object> theme = serializer.DeserializeObject(File.ReadAllText(Path.Combine(staging, "theme.json"), Encoding.UTF8)) as Dictionary<string, object>;
                if (theme == null) throw new InvalidDataException("内置主题模板无效。");
                theme["id"] = id; theme["name"] = name; theme["appearance"] = appearance;
                Dictionary<string, object> assets = (Dictionary<string, object>)theme["assets"];
                assets["homeBackground"] = assetRelative; assets["taskBackground"] = assetRelative;
                Dictionary<string, object> layout = (Dictionary<string, object>)theme["layout"];
                layout["mode"] = "native"; layout["density"] = density == "normal" ? "comfortable" : density;
                Dictionary<string, object> provenance = (Dictionary<string, object>)theme["provenance"];
                provenance["source"] = "recipe-v1"; provenance["template"] = "recipe-bridge";
                File.WriteAllText(Path.Combine(staging, "theme.json"), serializer.Serialize(theme) + Environment.NewLine, new UTF8Encoding(false));
                File.WriteAllText(Path.Combine(staging, "recipe.json"), serializer.Serialize(source) + Environment.NewLine, new UTF8Encoding(false));
                File.WriteAllText(Path.Combine(staging, "README.md"), "# " + name + "\r\n\r\n由 Theme Recipe v1 编译。布局已安全映射为 native；导入后仍需单独确认激活。\r\n", new UTF8Encoding(false));
                ThemePackageValidator.Validate(staging, id, serializer);
                Directory.Move(staging, destination);
                return new RecipeCompilation { Id = id, Name = name, ThemeDirectory = destination, LayoutMappedToNative = true };
            }
            finally { if (Directory.Exists(staging)) DeleteDirectory(staging); }
        }

        private static string ValidateFile(string value, string extension, long maximumBytes, string label)
        {
            if (string.IsNullOrWhiteSpace(value)) throw new InvalidDataException("未指定" + label + "文件。");
            string full = Path.GetFullPath(value); if (!File.Exists(full)) throw new FileNotFoundException(label + "文件不存在。", full);
            FileInfo info = new FileInfo(full);
            if ((info.Attributes & FileAttributes.ReparsePoint) != 0 || info.Length < 1 || info.Length > maximumBytes) throw new InvalidDataException(label + "文件大小或路径不安全。");
            if (!string.Equals(Path.GetExtension(full), extension, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException(label + "必须使用 " + extension + " 扩展名。");
            return full;
        }

        private static string ValidateImage(string value)
        {
            if (string.IsNullOrWhiteSpace(value)) throw new InvalidDataException("未指定主题主图。");
            string full = Path.GetFullPath(value);
            if (!File.Exists(full) || !SafeImageExtension.IsMatch(Path.GetExtension(full))) throw new InvalidDataException("主题主图必须是 PNG 或 JPEG。");
            FileInfo info = new FileInfo(full);
            if ((info.Attributes & FileAttributes.ReparsePoint) != 0 || info.Length < 1 || info.Length > 80L * 1024L * 1024L) throw new InvalidDataException("主题主图大小或路径不安全。");
            using (Image image = Image.FromFile(full)) if (image.Width < 1600 || image.Height < 900 || image.Width > 7680 || image.Height > 4320) throw new InvalidDataException("主题主图尺寸必须在 1600×900 到 7680×4320 之间。");
            return full;
        }

        private static void ValidateRecipe(Dictionary<string, object> recipe)
        {
            if (!recipe.ContainsKey("schemaVersion") || Convert.ToInt32(recipe["schemaVersion"]) != 1) throw new InvalidDataException("仅支持 Theme Recipe v1。");
            RequireText(recipe, "name", 80); RequireObject(recipe, "appearance"); RequireObject(recipe, "paletteIntent");
            string layout = RequireText(recipe, "layout", 40);
            string[] layouts = { "dream-banner", "split-studio", "full-canvas", "terminal-grid", "paper-board", "minimal-focus", "retro-messenger", "silk-scroll" };
            if (!layouts.Contains(layout)) throw new InvalidDataException("Theme Recipe layout 无效。");
        }

        private static Dictionary<string, object> RequireObject(Dictionary<string, object> parent, string key)
        {
            Dictionary<string, object> value = parent.ContainsKey(key) ? parent[key] as Dictionary<string, object> : null;
            if (value == null) throw new InvalidDataException(key + " 必须是对象。"); return value;
        }

        private static string RequireText(Dictionary<string, object> parent, string key, int maximum)
        {
            string value = parent.ContainsKey(key) ? Convert.ToString(parent[key]).Trim() : string.Empty;
            if (value.Length == 0 || value.Length > maximum) throw new InvalidDataException(key + " 必须为 1-" + maximum + " 个字符。"); return value;
        }

        private static string GetNestedText(Dictionary<string, object> parent, string objectKey, string key, string fallback)
        {
            Dictionary<string, object> nested = RequireObject(parent, objectKey);
            return nested.ContainsKey(key) ? Convert.ToString(nested[key]).Trim() : fallback;
        }

        private static string ShortHash(byte[] first, byte[] second)
        {
            using (SHA256 hash = SHA256.Create()) { hash.TransformBlock(first, 0, first.Length, null, 0); hash.TransformFinalBlock(second, 0, second.Length); return BitConverter.ToString(hash.Hash).Replace("-", string.Empty).ToLowerInvariant().Substring(0, 16); }
        }

        private static void CopyDirectory(string source, string destination)
        {
            Directory.CreateDirectory(destination);
            foreach (string file in Directory.GetFiles(source)) File.Copy(file, Path.Combine(destination, Path.GetFileName(file)), false);
            foreach (string directory in Directory.GetDirectories(source)) CopyDirectory(directory, Path.Combine(destination, Path.GetFileName(directory)));
        }

        private static void DeleteDirectory(string path) { try { Directory.Delete(path, true); } catch { } }
    }

    internal sealed class RecipeCompilation { public string Id; public string Name; public string ThemeDirectory; public bool LayoutMappedToNative; }
}
