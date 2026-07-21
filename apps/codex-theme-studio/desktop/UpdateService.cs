using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
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
        public string Message;
        public string Repository;
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
            if (string.IsNullOrWhiteSpace(fileName) || !fileName.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("更新包必须是 Windows EXE 安装程序。");
            string destination = Path.Combine(updateRoot, fileName);
            string partial = destination + ".download";
            try { if (File.Exists(partial)) File.Delete(partial); } catch { }

            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            using (WebClient client = new WebClient())
            {
                client.Headers[HttpRequestHeader.UserAgent] = "Codex-Theme-Studio/" + currentVersion;
                await client.DownloadFileTaskAsync(uri, partial);
            }
            string actualHash = ComputeSha256(partial);
            if (!string.Equals(actualHash, NormalizeHash(update.Sha256), StringComparison.OrdinalIgnoreCase))
            {
                File.Delete(partial);
                throw new InvalidDataException("更新包 SHA-256 校验失败。");
            }
            VerifyMinisign(partial, update.Signature);
            if (File.Exists(destination)) File.Delete(destination);
            File.Move(partial, destination);
            return destination;
        }

        public void StartInstaller(string installerPath, UpdateCheckResult update)
        {
            if (update == null) throw new ArgumentNullException("update");
            string actualHash = ComputeSha256(installerPath);
            if (!string.Equals(actualHash, NormalizeHash(update.Sha256), StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("更新包在安装前发生变化。");
            VerifyMinisign(installerPath, update.Signature);
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = installerPath;
            start.Arguments = "/VERYSILENT /NORESTART /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS";
            start.UseShellExecute = true;
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
            Dictionary<string, object> platforms = GetObject(feed, "platforms");
            Dictionary<string, object> package = GetObject(platforms, platform);
            string url = GetString(package, "url");
            string sha256 = GetString(package, "sha256");
            string signature = GetString(package, "signature");
            if (string.IsNullOrWhiteSpace(url) || NormalizeHash(sha256).Length != 64 ||
                string.IsNullOrWhiteSpace(signature) || signature.Length > 4096)
                throw new InvalidDataException("Windows 更新包缺少 URL、SHA-256 或 Minisign 签名。");
            return new UpdateCheckResult
            {
                Enabled = true,
                UpdateAvailable = remote > local,
                Version = version,
                Notes = GetString(feed, "notes"),
                Url = url,
                Sha256 = sha256,
                Signature = signature,
                Repository = repository,
                Message = remote > local ? "发现新版本 " + version : "当前已是最新版本 " + currentVersion
            };
        }

        private void VerifyMinisign(string path, string signature)
        {
            string verifier = Path.Combine(engineRoot, "runtime", "minisign.exe");
            if (!File.Exists(verifier)) throw new InvalidDataException("更新签名验证器缺失。");
            if (!string.Equals(ComputeSha256(verifier), UpdateTrust.VerifierSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("更新签名验证器完整性校验失败。");
            if (string.IsNullOrWhiteSpace(signature)) throw new InvalidDataException("更新包缺少 Minisign 签名。");

            string signaturePath = path + "." + Guid.NewGuid().ToString("N") + ".minisig";
            try
            {
                using (FileStream stream = new FileStream(signaturePath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)))
                    writer.Write(signature.Replace("\r\n", "\n"));

                ProcessStartInfo start = new ProcessStartInfo();
                start.FileName = verifier;
                start.Arguments = "-V -q -m " + QuoteArgument(path) + " -x " + QuoteArgument(signaturePath) +
                    " -P " + QuoteArgument(UpdateTrust.PublicKey);
                start.UseShellExecute = false;
                start.CreateNoWindow = true;
                start.RedirectStandardOutput = true;
                start.RedirectStandardError = true;
                using (Process process = Process.Start(start))
                {
                    Task<string> standardOutputTask = process.StandardOutput.ReadToEndAsync();
                    Task<string> standardErrorTask = process.StandardError.ReadToEndAsync();
                    if (!process.WaitForExit(30000))
                    {
                        try { process.Kill(); } catch { }
                        throw new InvalidDataException("更新签名验证超时。");
                    }
                    Task.WaitAll(new Task[] { standardOutputTask, standardErrorTask }, 2000);
                    if (process.ExitCode != 0)
                    {
                        string standardOutput = standardOutputTask.IsCompleted ? standardOutputTask.Result : string.Empty;
                        string standardError = standardErrorTask.IsCompleted ? standardErrorTask.Result : string.Empty;
                        string detail = string.IsNullOrWhiteSpace(standardError) ? standardOutput : standardError;
                        detail = (detail ?? string.Empty).Trim();
                        if (detail.Length > 240) detail = detail.Substring(0, 240);
                        throw new InvalidDataException("更新包 Minisign 签名无效。" + (detail.Length == 0 ? string.Empty : " " + detail));
                    }
                }
            }
            finally
            {
                try { if (File.Exists(signaturePath)) File.Delete(signaturePath); } catch { }
            }
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
