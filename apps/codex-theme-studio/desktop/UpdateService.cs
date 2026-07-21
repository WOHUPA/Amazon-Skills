using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

namespace CodexThemeStudio.Desktop
{
    internal sealed class UpdateCheckResult
    {
        public bool Enabled;
        public bool UpdateAvailable;
        public string Version;
        public string Notes;
        public string Url;
        public string Sha256;
        public string Signature;
        public List<string> Signatures = new List<string>();
        public string Message;
        public string Repository;
    }

    internal sealed class UpdateTransaction
    {
        public int SchemaVersion { get; set; }
        public string Status { get; set; }
        public string Version { get; set; }
        public string InstallerPath { get; set; }
        public string Sha256 { get; set; }
        public string Signature { get; set; }
        public string[] Signatures { get; set; }
        public string AppPath { get; set; }
        public string EngineRoot { get; set; }
        public string CreatedAt { get; set; }
        public string StartedAt { get; set; }
        public string CompletedAt { get; set; }
        public int ExitCode { get; set; }
        public string Message { get; set; }
        public string LogPath { get; set; }
    }

    internal sealed class UpdateService
    {
        private readonly string stateRoot;
        private readonly string engineRoot;
        private readonly string currentVersion;
        private readonly JavaScriptSerializer serializer = new JavaScriptSerializer();

        public UpdateService(string stateRoot, string engineRoot, string currentVersion)
        {
            this.stateRoot = stateRoot;
            this.engineRoot = engineRoot;
            this.currentVersion = currentVersion;
            serializer.MaxJsonLength = 4 * 1024 * 1024;
        }

        public Task<UpdateCheckResult> CheckAsync()
        {
            return Task.Run(delegate { return Check(); });
        }

        public string ConsumeLastUpdateMessage()
        {
            string path = Path.Combine(stateRoot, "updates", "last-result.json");
            Dictionary<string, object> result = ReadObject(path);
            if (result == null) return string.Empty;
            try { File.Delete(path); } catch { }
            string status = GetString(result, "Status");
            string version = GetString(result, "Version");
            string message = GetString(result, "Message");
            if (string.Equals(status, "installed", StringComparison.OrdinalIgnoreCase) &&
                string.Equals(version, currentVersion, StringComparison.OrdinalIgnoreCase))
                return "已升级到 " + version + "。" + (string.IsNullOrWhiteSpace(message) ? string.Empty : " " + message);
            if (string.Equals(status, "failed", StringComparison.OrdinalIgnoreCase))
                return "上次更新失败：" + (string.IsNullOrWhiteSpace(message) ? "请查看更新日志。" : message);
            return string.Empty;
        }

        public async Task<string> DownloadAndVerifyAsync(UpdateCheckResult update)
        {
            if (update == null || !update.UpdateAvailable) throw new InvalidOperationException("没有可安装的更新。");
            Uri uri = new Uri(update.Url, UriKind.Absolute);
            if (!string.Equals(uri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("更新包必须使用 HTTPS。");
            string expectedPrefix = "https://github.com/" + update.Repository.Trim('/') + "/releases/download/";
            if (!update.Url.StartsWith(expectedPrefix, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("更新包不属于已配置的 GitHub Releases 仓库。");

            string updateRoot = Path.Combine(stateRoot, "updates", update.Version);
            Directory.CreateDirectory(updateRoot);
            string fileName = Path.GetFileName(uri.AbsolutePath);
            if (string.IsNullOrWhiteSpace(fileName) || !fileName.EndsWith(".msi", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("更新包必须是 Windows MSI 安装程序。");
            string destination = Path.Combine(updateRoot, fileName);
            string partial = destination + ".download";

            await Task.Run(delegate { DownloadWithRetry(uri, partial); });
            string actualHash = ComputeSha256(partial);
            if (!string.Equals(actualHash, NormalizeHash(update.Sha256), StringComparison.OrdinalIgnoreCase))
            {
                File.Delete(partial);
                throw new InvalidDataException("更新包 SHA-256 校验失败。");
            }
            VerifyMinisign(partial, update.Signatures);
            if (File.Exists(destination)) File.Delete(destination);
            File.Move(partial, destination);
            return destination;
        }

        public void StartInstaller(string installerPath, UpdateCheckResult update)
        {
            if (update == null) throw new ArgumentNullException("update");
            if (!installerPath.EndsWith(".msi", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("独立更新程序只接受 MSI 安装包。");
            string actualHash = ComputeSha256(installerPath);
            if (!string.Equals(actualHash, NormalizeHash(update.Sha256), StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("更新包在安装前发生变化。");
            VerifyMinisign(installerPath, update.Signatures);

            string updateRoot = Path.GetDirectoryName(Path.GetFullPath(installerPath));
            string installedUpdater = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "CodexThemeStudio.Updater.exe");
            if (!File.Exists(installedUpdater)) throw new FileNotFoundException("独立更新程序缺失。", installedUpdater);
            if (!string.Equals(ComputeSha256(installedUpdater), UpdateTrust.UpdaterSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("独立更新程序完整性校验失败。");
            string updater = Path.Combine(updateRoot, "CodexThemeStudio.Updater.exe");
            File.Copy(installedUpdater, updater, true);
            if (!string.Equals(ComputeSha256(updater), UpdateTrust.UpdaterSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("复制后的独立更新程序完整性校验失败。");

            string transactionPath = Path.Combine(updateRoot, "transaction.json");
            UpdateTransaction transaction = new UpdateTransaction
            {
                SchemaVersion = 1,
                Status = "pending",
                Version = update.Version,
                InstallerPath = Path.GetFullPath(installerPath),
                Sha256 = update.Sha256,
                Signature = update.Signature,
                Signatures = update.Signatures.ToArray(),
                AppPath = Process.GetCurrentProcess().MainModule.FileName,
                EngineRoot = engineRoot,
                CreatedAt = DateTime.UtcNow.ToString("o"),
                Message = "等待主程序退出。"
            };
            WriteJsonAtomic(transactionPath, serializer.Serialize(transaction));

            ProcessStartInfo start = new ProcessStartInfo
            {
                FileName = updater,
                Arguments = "--transaction " + QuoteArgument(transactionPath) + " --parent-pid " + Process.GetCurrentProcess().Id,
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = updateRoot
            };
            Process.Start(start);
        }

        private UpdateCheckResult Check()
        {
            Dictionary<string, object> config = ReadObject(Path.Combine(engineRoot, "assets", "update-channel.json"));
            string endpoint = GetString(config, "endpoint");
            string repository = GetString(config, "repository");
            string platform = GetString(config, "platform");
            if (string.IsNullOrWhiteSpace(endpoint) || string.IsNullOrWhiteSpace(repository))
                return new UpdateCheckResult { Enabled = false, Message = "GitHub 更新通道尚未配置。" };
            Uri endpointUri;
            if (!Uri.TryCreate(endpoint, UriKind.Absolute, out endpointUri) || endpointUri.Scheme != Uri.UriSchemeHttps ||
                !string.Equals(endpointUri.Host, "github.com", StringComparison.OrdinalIgnoreCase))
                return new UpdateCheckResult { Enabled = false, Message = "GitHub 更新地址不安全。" };

            string json;
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            using (WebClient client = new WebClient())
            {
                client.Headers[HttpRequestHeader.UserAgent] = "Codex-Theme-Studio/" + currentVersion;
                json = client.DownloadString(endpointUri);
            }
            Dictionary<string, object> feed = serializer.DeserializeObject(json) as Dictionary<string, object>;
            if (feed == null) throw new InvalidDataException("GitHub 更新清单不是有效 JSON 对象。");
            string version = GetString(feed, "version").TrimStart('v', 'V');
            Version remote;
            Version local;
            if (!Version.TryParse(version, out remote) || !Version.TryParse(currentVersion, out local))
                throw new InvalidDataException("更新清单版本号无效。");
            if (remote <= local)
            {
                return new UpdateCheckResult
                {
                    Enabled = true,
                    UpdateAvailable = false,
                    Version = version,
                    Notes = GetString(feed, "notes"),
                    Message = "当前已是最新版本 " + currentVersion
                };
            }
            Dictionary<string, object> platforms = GetObject(feed, "platforms");
            Dictionary<string, object> package = GetObject(platforms, platform);
            string url = GetString(package, "url");
            string sha256 = GetString(package, "sha256");
            List<string> signatures = GetStrings(package, "signatures");
            string legacySignature = GetString(package, "signature");
            if (!string.IsNullOrWhiteSpace(legacySignature) && !signatures.Contains(legacySignature)) signatures.Insert(0, legacySignature);
            if (string.IsNullOrWhiteSpace(url) || NormalizeHash(sha256).Length != 64 || signatures.Count == 0 ||
                signatures.Exists(delegate(string value) { return string.IsNullOrWhiteSpace(value) || value.Length > 4096; }))
                throw new InvalidDataException("Windows 更新包缺少 URL、SHA-256 或 Minisign 签名。");
            return new UpdateCheckResult
            {
                Enabled = true,
                UpdateAvailable = remote > local,
                Version = version,
                Notes = GetString(feed, "notes"),
                Url = url,
                Sha256 = sha256,
                Signature = signatures[0],
                Signatures = signatures,
                Repository = repository,
                Message = remote > local ? "发现新版本 " + version : "当前已是最新版本 " + currentVersion
            };
        }

        private static void DownloadWithRetry(Uri uri, string partial)
        {
            Exception lastError = null;
            for (int attempt = 1; attempt <= 3; attempt++)
            {
                try
                {
                    DownloadOnce(uri, partial);
                    return;
                }
                catch (Exception ex)
                {
                    lastError = ex;
                    if (attempt < 3) Thread.Sleep(attempt * 1000);
                }
            }
            throw new IOException("更新包下载重试三次后仍然失败。", lastError);
        }

        private static void DownloadOnce(Uri uri, string partial)
        {
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            long existingLength = File.Exists(partial) ? new FileInfo(partial).Length : 0;
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(uri);
            request.UserAgent = "Codex-Theme-Studio-Updater";
            request.AllowAutoRedirect = true;
            request.Timeout = 30000;
            request.ReadWriteTimeout = 30000;
            if (existingLength > 0) request.AddRange(existingLength);
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            {
                bool append = existingLength > 0 && response.StatusCode == HttpStatusCode.PartialContent;
                using (Stream input = response.GetResponseStream())
                using (FileStream output = new FileStream(partial, append ? FileMode.Append : FileMode.Create, FileAccess.Write, FileShare.None))
                {
                    byte[] buffer = new byte[1024 * 128];
                    int read;
                    while ((read = input.Read(buffer, 0, buffer.Length)) > 0) output.Write(buffer, 0, read);
                    output.Flush(true);
                }
            }
        }

        private void VerifyMinisign(string path, IEnumerable<string> signatures)
        {
            string verifier = Path.Combine(engineRoot, "runtime", "minisign.exe");
            if (!File.Exists(verifier)) throw new InvalidDataException("更新签名验证器缺失。");
            if (!string.Equals(ComputeSha256(verifier), UpdateTrust.VerifierSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("更新签名验证器完整性校验失败。");

            foreach (string signature in signatures)
            {
                string signaturePath = path + "." + Guid.NewGuid().ToString("N") + ".minisig";
                try
                {
                    using (FileStream stream = new FileStream(signaturePath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                    using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
                        writer.Write(signature.Replace("\r\n", "\n"));
                    foreach (string publicKey in UpdateTrust.PublicKeys)
                    {
                        ProcessStartInfo start = new ProcessStartInfo
                        {
                            FileName = verifier,
                            Arguments = "-V -q -m " + QuoteArgument(path) + " -x " + QuoteArgument(signaturePath) + " -P " + QuoteArgument(publicKey),
                            UseShellExecute = false,
                            CreateNoWindow = true,
                            RedirectStandardOutput = true,
                            RedirectStandardError = true
                        };
                        using (Process process = Process.Start(start))
                        {
                            Task<string> outputTask = process.StandardOutput.ReadToEndAsync();
                            Task<string> errorTask = process.StandardError.ReadToEndAsync();
                            if (!process.WaitForExit(30000)) { try { process.Kill(); } catch { } continue; }
                            Task.WaitAll(new Task[] { outputTask, errorTask }, 2000);
                            if (process.ExitCode == 0) return;
                        }
                    }
                }
                finally
                {
                    try { if (File.Exists(signaturePath)) File.Delete(signaturePath); } catch { }
                }
            }
            throw new InvalidDataException("更新包 Minisign 签名无效。");
        }

        private static void WriteJsonAtomic(string path, string json)
        {
            string temporary = path + ".tmp";
            File.WriteAllText(temporary, json, new UTF8Encoding(false));
            if (File.Exists(path)) File.Replace(temporary, path, null); else File.Move(temporary, path);
        }

        private static string QuoteArgument(string value)
        {
            if (value == null) return "\"\"";
            if (value.Length > 0 && value.IndexOfAny(new char[] { ' ', '\t', '\n', '\v', '"' }) < 0) return value;
            StringBuilder result = new StringBuilder();
            result.Append('"');
            int slashes = 0;
            foreach (char character in value)
            {
                if (character == '\\') { slashes++; continue; }
                if (character == '"')
                {
                    result.Append('\\', slashes * 2 + 1);
                    result.Append('"');
                    slashes = 0;
                    continue;
                }
                result.Append('\\', slashes);
                slashes = 0;
                result.Append(character);
            }
            result.Append('\\', slashes * 2);
            result.Append('"');
            return result.ToString();
        }

        private Dictionary<string, object> ReadObject(string path)
        {
            if (!File.Exists(path)) return null;
            return serializer.DeserializeObject(File.ReadAllText(path, Encoding.UTF8)) as Dictionary<string, object>;
        }

        private static Dictionary<string, object> GetObject(Dictionary<string, object> source, string key)
        {
            if (source == null || !source.ContainsKey(key)) return null;
            return source[key] as Dictionary<string, object>;
        }

        private static string GetString(Dictionary<string, object> source, string key)
        {
            return source != null && source.ContainsKey(key) && source[key] != null ? Convert.ToString(source[key]) : string.Empty;
        }

        private static List<string> GetStrings(Dictionary<string, object> source, string key)
        {
            List<string> values = new List<string>();
            if (source == null || !source.ContainsKey(key)) return values;
            object[] items = source[key] as object[];
            if (items == null) return values;
            foreach (object item in items) if (item != null) values.Add(Convert.ToString(item));
            return values;
        }

        private static string ComputeSha256(string path)
        {
            using (FileStream stream = File.OpenRead(path))
            using (SHA256 hash = SHA256.Create())
                return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", string.Empty);
        }

        private static string NormalizeHash(string value)
        {
            return (value ?? string.Empty).Replace(" ", string.Empty).Replace("-", string.Empty).Trim().ToUpperInvariant();
        }
    }
}
