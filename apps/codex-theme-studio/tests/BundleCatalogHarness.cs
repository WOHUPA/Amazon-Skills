using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

namespace CodexThemeStudio.Desktop
{
    internal sealed class EngineCommandResult
    {
        public int ExitCode;
        public string StandardOutput;
        public string StandardError;
    }

    internal static class BundleCatalogHarness
    {
        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer();

        private static void Main(string[] args)
        {
            if (args.Length != 1) throw new ArgumentException("Repository root is required.");
            string preset = Path.Combine(args[0], "presets", "immersive-dark");
            string root = Path.Combine(Path.GetTempPath(), "codex-theme-bundle-" + Guid.NewGuid().ToString("N"));
            try
            {
                Directory.CreateDirectory(root);
                TestCatalog(Path.Combine(root, "catalog"));
                TestBundles(root, preset);
                Console.WriteLine("PASS: Bundle security, atomic conflicts, no-auto-activation, and Catalog v1 persistence verified.");
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex.GetType().FullName);
                Console.Error.WriteLine(ex.Message);
                Console.Error.WriteLine(ex.StackTrace);
                Environment.ExitCode = 1;
            }
            finally
            {
                if (Directory.Exists(root)) Directory.Delete(root, true);
            }
        }

        private static void TestCatalog(string stateRoot)
        {
            ThemeCatalog catalog = new ThemeCatalog(stateRoot, new[] {
                "immersive-dark", "clear-light", "obsidian-gold", "doupo-test", "custom-one"
            });
            Assert(catalog.GetSeriesId("immersive-dark") == "basic", "Basic migration failed.");
            Assert(catalog.GetSeriesId("doupo-test") == "doupo", "Doupo migration failed.");
            Assert(catalog.GetSeriesId("custom-one") == ThemeCatalog.UnclassifiedSeriesId, "Unclassified migration failed.");
            catalog.RenameSeries("basic", "我的基础");
            catalog.MoveTheme("custom-one", "basic");
            catalog.MoveSeries("basic", 1);
            catalog.DeleteSeries("doupo");
            Assert(catalog.GetSeriesId("doupo-test") == ThemeCatalog.UnclassifiedSeriesId, "Deleting a series must retain its themes.");

            ThemeCatalog reopened = new ThemeCatalog(stateRoot, new[] {
                "immersive-dark", "clear-light", "obsidian-gold", "doupo-test", "custom-one"
            });
            Assert(reopened.GetSeries().Any(item => item.Id == "basic" && item.Name == "我的基础"), "Local series rename was overwritten.");
            Assert(!reopened.GetSeries().Any(item => item.Id == "doupo"), "Deleted built-in series was recreated.");
            Assert(reopened.GetSeriesId("custom-one") == "basic", "Local theme assignment was not preserved.");
        }

        private static void TestBundles(string root, string preset)
        {
            string stateRoot = Path.Combine(root, "state");
            string engineRoot = Path.Combine(root, "engine");
            CopyTheme(preset, Path.Combine(engineRoot, "presets", "immersive-dark"), "immersive-dark");
            using (NativeThemeEngine engine = new NativeThemeEngine(stateRoot, engineRoot))
            {
                string valid = CreateBundle(root, preset, "valid.codextheme", new[] { "bundle-one" }, BundleMutation.None);
                EngineCommandResult preview = Execute(engine, "preview", valid);
                Assert(preview.ExitCode == 0 && preview.StandardOutput.Contains("\"canImport\":true"), "Valid bundle preview failed.");
                EngineCommandResult imported = Execute(engine, "import", valid);
                Assert(imported.ExitCode == 0, "Valid bundle import failed: " + imported.StandardError);
                Assert(Directory.Exists(Path.Combine(stateRoot, "themes", "bundle-one")), "Imported theme is missing.");
                Assert(engine.CurrentThemeId == "immersive-dark", "Import must not auto-activate a theme.");

                EngineCommandResult duplicateImport = Execute(engine, "import", valid);
                Assert(duplicateImport.ExitCode != 0, "Existing theme conflict must block the entire bundle.");

                AssertRejected(engine, CreateBundle(root, preset, "zip-slip.codextheme", new[] { "zip-slip" }, BundleMutation.ZipSlip), "ZIP Slip");
                AssertRejected(engine, CreateBundle(root, preset, "hash.codextheme", new[] { "hash-bad" }, BundleMutation.HashMismatch), "hash mismatch");
                AssertRejected(engine, CreateBundle(root, preset, "unknown.codextheme", new[] { "unknown-field" }, BundleMutation.UnknownField), "unknown field");
                AssertRejected(engine, CreateBundle(root, preset, "executable.codextheme", new[] { "executable-file" }, BundleMutation.Executable), "executable file");
                AssertRejected(engine, CreateBundle(root, preset, "duplicate.codextheme", new[] { "duplicate-id" }, BundleMutation.DuplicateId), "duplicate ID");
                AssertRejected(engine, CreateBundle(root, preset, "svg.codextheme", new[] { "malicious-svg" }, BundleMutation.MaliciousSvg), "malicious SVG");

                string partial = CreateBundle(root, preset, "partial.codextheme", new[] { "immersive-dark", "new-in-partial" }, BundleMutation.None);
                EngineCommandResult partialResult = Execute(engine, "import", partial);
                Assert(partialResult.ExitCode != 0, "A partial conflict must block the whole bundle.");
                Assert(!Directory.Exists(Path.Combine(stateRoot, "themes", "new-in-partial")), "Partial conflict imported a subset.");
            }
        }

        private static void AssertRejected(NativeThemeEngine engine, string package, string label)
        {
            EngineCommandResult result = Execute(engine, "import", package);
            Assert(result.ExitCode != 0, label + " bundle was accepted.");
        }

        private static EngineCommandResult Execute(NativeThemeEngine engine, params string[] arguments)
        {
            return engine.ExecuteAsync(arguments, CancellationToken.None, TimeSpan.FromSeconds(20)).GetAwaiter().GetResult();
        }

        private static string CreateBundle(
            string root,
            string preset,
            string fileName,
            string[] themeIds,
            BundleMutation mutation)
        {
            string sourceRoot = Path.Combine(root, ".bundle-source-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(sourceRoot);
            try
            {
                foreach (string id in themeIds)
                    CopyTheme(preset, Path.Combine(sourceRoot, "themes", id), id);
                if (mutation == BundleMutation.MaliciousSvg)
                {
                    string svg = Path.Combine(sourceRoot, "themes", themeIds[0], "assets", "icons", "newTask.svg");
                    File.WriteAllText(svg, "<svg xmlns=\"http://www.w3.org/2000/svg\"><script>alert(1)</script></svg>", new UTF8Encoding(false));
                }
                if (mutation == BundleMutation.Executable)
                    File.WriteAllBytes(Path.Combine(sourceRoot, "themes", themeIds[0], "tool.exe"), new byte[] { 77, 90, 0, 0 });

                List<Dictionary<string, object>> files = new List<Dictionary<string, object>>();
                foreach (string file in Directory.GetFiles(Path.Combine(sourceRoot, "themes"), "*", SearchOption.AllDirectories))
                {
                    string relative = file.Substring(sourceRoot.Length + 1).Replace('\\', '/');
                    files.Add(new Dictionary<string, object> {
                        { "path", relative },
                        { "size", new FileInfo(file).Length },
                        { "sha256", Sha256(file) }
                    });
                }
                if (mutation == BundleMutation.HashMismatch) files[0]["sha256"] = new string('0', 64);
                List<Dictionary<string, object>> themes = themeIds.Select(id => new Dictionary<string, object> {
                    { "id", id }, { "path", "themes/" + id }
                }).ToList();
                if (mutation == BundleMutation.DuplicateId)
                    themes.Add(new Dictionary<string, object> { { "id", themeIds[0] }, { "path", "themes/" + themeIds[0] } });
                Dictionary<string, object> manifest = new Dictionary<string, object> {
                    { "schemaVersion", 1 },
                    { "bundleId", "test-" + themeIds[0] },
                    { "name", "测试 Bundle" },
                    { "series", new Dictionary<string, object> { { "id", "test-series" }, { "name", "测试系列" } } },
                    { "themes", themes.ToArray() },
                    { "files", files.OrderBy(item => Convert.ToString(item["path"]), StringComparer.Ordinal).ToArray() }
                };
                if (mutation == BundleMutation.UnknownField) manifest["runtime"] = "forbidden";

                string package = Path.Combine(root, fileName);
                using (ZipArchive archive = ZipFile.Open(package, ZipArchiveMode.Create))
                {
                    ZipArchiveEntry manifestEntry = archive.CreateEntry("bundle.json", CompressionLevel.Optimal);
                    using (StreamWriter writer = new StreamWriter(manifestEntry.Open(), new UTF8Encoding(false)))
                        writer.Write(Serializer.Serialize(manifest));
                    foreach (Dictionary<string, object> item in files)
                    {
                        string relative = Convert.ToString(item["path"]);
                        string source = Path.Combine(sourceRoot, relative.Replace('/', Path.DirectorySeparatorChar));
                        archive.CreateEntryFromFile(source, relative, CompressionLevel.Optimal);
                    }
                    if (mutation == BundleMutation.ZipSlip)
                    {
                        ZipArchiveEntry escape = archive.CreateEntry("../escape.txt");
                        using (StreamWriter writer = new StreamWriter(escape.Open())) writer.Write("escape");
                    }
                }
                return package;
            }
            finally
            {
                if (Directory.Exists(sourceRoot)) Directory.Delete(sourceRoot, true);
            }
        }

        private static void CopyTheme(string source, string destination, string id)
        {
            CopyDirectory(source, destination);
            string metadataPath = Path.Combine(destination, "theme.json");
            Dictionary<string, object> metadata = Serializer.DeserializeObject(File.ReadAllText(metadataPath, Encoding.UTF8)) as Dictionary<string, object>;
            metadata["id"] = id;
            metadata["name"] = id;
            File.WriteAllText(metadataPath, Serializer.Serialize(metadata), new UTF8Encoding(false));
        }

        private static void CopyDirectory(string source, string destination)
        {
            Directory.CreateDirectory(destination);
            foreach (string file in Directory.GetFiles(source))
                File.Copy(file, Path.Combine(destination, Path.GetFileName(file)), true);
            foreach (string directory in Directory.GetDirectories(source))
                CopyDirectory(directory, Path.Combine(destination, Path.GetFileName(directory)));
        }

        private static string Sha256(string path)
        {
            using (SHA256 sha = SHA256.Create())
            using (FileStream stream = File.OpenRead(path))
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", string.Empty).ToLowerInvariant();
        }

        private static void Assert(bool condition, string message)
        {
            if (!condition) throw new InvalidOperationException(message);
        }

        private enum BundleMutation
        {
            None,
            ZipSlip,
            HashMismatch,
            UnknownField,
            Executable,
            DuplicateId,
            MaliciousSvg
        }
    }
}
