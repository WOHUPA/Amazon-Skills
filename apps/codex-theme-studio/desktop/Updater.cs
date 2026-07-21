using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

[assembly: System.Reflection.AssemblyTitle("Codex Theme Studio Updater")]
[assembly: System.Reflection.AssemblyDescription("Transactional MSI updater for Codex Theme Studio")]
[assembly: System.Reflection.AssemblyCompany("Codex Theme Studio")]
[assembly: System.Reflection.AssemblyProduct("Codex Theme Studio")]
[assembly: System.Reflection.AssemblyCopyright("Copyright (c) 2026")]
[assembly: System.Reflection.AssemblyVersion("2.6.0.0")]
[assembly: System.Reflection.AssemblyFileVersion("2.6.0.0")]
[assembly: System.Reflection.AssemblyInformationalVersion("2.6.0")]

namespace CodexThemeStudio.Updater
{
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

    internal static class Program
    {
        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer();

        private static int Main(string[] args)
        {
            string transactionPath = GetArgument(args, "--transaction");
            int parentPid;
            if (string.IsNullOrWhiteSpace(transactionPath) ||
                !int.TryParse(GetArgument(args, "--parent-pid"), out parentPid))
            {
                return 2;
            }

            transactionPath = Path.GetFullPath(transactionPath);
            UpdateTransaction transaction = null;
            try
            {
                transaction = ReadTransaction(transactionPath);
                ValidateTransaction(transactionPath, transaction);
                transaction.Status = "installing";
                transaction.StartedAt = DateTime.UtcNow.ToString("o");
                WriteTransaction(transactionPath, transaction);

                if (!WaitForParent(parentPid, TimeSpan.FromMinutes(2)))
                    throw new TimeoutException("主程序未能在两分钟内退出，升级已取消。");

                VerifyInstaller(transaction);
                int exitCode = InstallMsi(transaction);
                transaction.ExitCode = exitCode;
                if (exitCode != 0 && exitCode != 1641 && exitCode != 3010)
                    throw new InvalidOperationException("Windows Installer 返回错误代码 " + exitCode + "。");

                string installedVersion = FileVersionInfo.GetVersionInfo(transaction.AppPath).ProductVersion ?? string.Empty;
                if (!installedVersion.StartsWith(transaction.Version, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("安装完成后程序版本不匹配，实际版本为 " + installedVersion + "。");

                transaction.Status = "installed";
                transaction.Message = exitCode == 3010 || exitCode == 1641
                    ? "更新已安装，Windows 建议稍后重新启动。"
                    : "更新已安装并完成版本校验。";
                transaction.CompletedAt = DateTime.UtcNow.ToString("o");
                WriteTransaction(transactionPath, transaction);
                WriteLastResult(transactionPath, transaction);
                Relaunch(transaction.AppPath);
                return 0;
            }
            catch (Exception ex)
            {
                if (transaction != null)
                {
                    transaction.Status = "failed";
                    transaction.Message = ex.Message;
                    transaction.CompletedAt = DateTime.UtcNow.ToString("o");
                    try { WriteTransaction(transactionPath, transaction); } catch { }
                    try { WriteLastResult(transactionPath, transaction); } catch { }
                    Relaunch(transaction.AppPath);
                }
                return 1;
            }
        }

        private static UpdateTransaction ReadTransaction(string path)
        {
            if (!File.Exists(path)) throw new FileNotFoundException("升级事务文件不存在。", path);
            UpdateTransaction transaction = Serializer.Deserialize<UpdateTransaction>(File.ReadAllText(path, Encoding.UTF8));
            if (transaction == null) throw new InvalidDataException("升级事务文件无效。");
            return transaction;
        }

        private static void ValidateTransaction(string transactionPath, UpdateTransaction transaction)
        {
            if (transaction.SchemaVersion != 1 || string.IsNullOrWhiteSpace(transaction.Version) ||
                string.IsNullOrWhiteSpace(transaction.InstallerPath) || string.IsNullOrWhiteSpace(transaction.AppPath) ||
                string.IsNullOrWhiteSpace(transaction.EngineRoot) || NormalizeHash(transaction.Sha256).Length != 64 ||
                ((transaction.Signatures == null || transaction.Signatures.Length == 0) && string.IsNullOrWhiteSpace(transaction.Signature)))
                throw new InvalidDataException("升级事务缺少必要字段。");

            string transactionDirectory = Path.GetDirectoryName(transactionPath).TrimEnd('\\');
            string installer = Path.GetFullPath(transaction.InstallerPath);
            if (!string.Equals(Path.GetDirectoryName(installer).TrimEnd('\\'), transactionDirectory, StringComparison.OrdinalIgnoreCase) ||
                !installer.EndsWith(".msi", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("升级包必须是事务目录中的 MSI 文件。");
            if (!File.Exists(installer)) throw new FileNotFoundException("MSI 升级包不存在。", installer);
            transaction.InstallerPath = installer;
            transaction.AppPath = Path.GetFullPath(transaction.AppPath);
            transaction.EngineRoot = Path.GetFullPath(transaction.EngineRoot);
            transaction.LogPath = Path.Combine(transactionDirectory, "install.log");
        }

        private static bool WaitForParent(int parentPid, TimeSpan timeout)
        {
            try
            {
                using (Process parent = Process.GetProcessById(parentPid))
                    return parent.WaitForExit((int)timeout.TotalMilliseconds);
            }
            catch (ArgumentException)
            {
                return true;
            }
        }

        private static void VerifyInstaller(UpdateTransaction transaction)
        {
            if (!string.Equals(ComputeSha256(transaction.InstallerPath), NormalizeHash(transaction.Sha256), StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("MSI 升级包在安装前发生变化。");

            string verifier = Path.Combine(transaction.EngineRoot, "runtime", "minisign.exe");
            if (!File.Exists(verifier) ||
                !string.Equals(ComputeSha256(verifier), UpdateTrust.VerifierSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("升级签名验证器缺失或完整性校验失败。");

            List<string> signatures = new List<string>();
            if (transaction.Signatures != null) signatures.AddRange(transaction.Signatures);
            if (!string.IsNullOrWhiteSpace(transaction.Signature) && !signatures.Contains(transaction.Signature))
                signatures.Insert(0, transaction.Signature);
            foreach (string signature in signatures)
            {
                string signaturePath = transaction.InstallerPath + "." + Guid.NewGuid().ToString("N") + ".updater.minisig";
                try
                {
                    File.WriteAllText(signaturePath, signature.Replace("\r\n", "\n"), new UTF8Encoding(false));
                    foreach (string publicKey in UpdateTrust.PublicKeys)
                    {
                        ProcessStartInfo start = new ProcessStartInfo
                        {
                            FileName = verifier,
                            Arguments = "-V -q -m " + Quote(transaction.InstallerPath) + " -x " + Quote(signaturePath) + " -P " + Quote(publicKey),
                            UseShellExecute = false,
                            CreateNoWindow = true,
                            RedirectStandardOutput = true,
                            RedirectStandardError = true
                        };
                        using (Process process = Process.Start(start))
                        {
                            process.StandardOutput.ReadToEnd();
                            process.StandardError.ReadToEnd();
                            if (!process.WaitForExit(30000))
                            {
                                try { process.Kill(); } catch { }
                                continue;
                            }
                            if (process.ExitCode == 0) return;
                        }
                    }
                }
                finally
                {
                    try { if (File.Exists(signaturePath)) File.Delete(signaturePath); } catch { }
                }
            }
            throw new InvalidDataException("MSI 升级包的 Minisign 签名无效。");
        }

        private static int InstallMsi(UpdateTransaction transaction)
        {
            ProcessStartInfo start = new ProcessStartInfo
            {
                FileName = Path.Combine(Environment.SystemDirectory, "msiexec.exe"),
                Arguments = "/i " + Quote(transaction.InstallerPath) + " /passive /norestart /L*v " + Quote(transaction.LogPath) + " STUDIO_UPDATE=1",
                UseShellExecute = false,
                CreateNoWindow = true
            };
            using (Process process = Process.Start(start))
            {
                if (!process.WaitForExit((int)TimeSpan.FromMinutes(15).TotalMilliseconds))
                {
                    try { process.Kill(); } catch { }
                    throw new TimeoutException("Windows Installer 在十五分钟内未完成。");
                }
                return process.ExitCode;
            }
        }

        private static void WriteTransaction(string path, UpdateTransaction transaction)
        {
            string temporary = path + ".tmp";
            File.WriteAllText(temporary, Serializer.Serialize(transaction), new UTF8Encoding(false));
            if (File.Exists(path)) File.Replace(temporary, path, null); else File.Move(temporary, path);
        }

        private static void WriteLastResult(string transactionPath, UpdateTransaction transaction)
        {
            string updateRoot = Directory.GetParent(Path.GetDirectoryName(transactionPath)).FullName;
            WriteTransaction(Path.Combine(updateRoot, "last-result.json"), transaction);
        }

        private static void Relaunch(string appPath)
        {
            try
            {
                if (File.Exists(appPath)) Process.Start(new ProcessStartInfo { FileName = appPath, UseShellExecute = true });
            }
            catch { }
        }

        private static string GetArgument(string[] args, string name)
        {
            for (int index = 0; index < args.Length - 1; index++)
                if (string.Equals(args[index], name, StringComparison.OrdinalIgnoreCase)) return args[index + 1];
            return string.Empty;
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

        private static string Quote(string value)
        {
            return "\"" + (value ?? string.Empty).Replace("\"", "\\\"") + "\"";
        }
    }
}
