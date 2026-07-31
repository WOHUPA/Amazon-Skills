using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

namespace CodexThemeStudio.Desktop
{
    // Minimal JSON-RPC/JSONL transport for the documented Codex app-server.  It
    // owns no theme state; callers retain all artifacts in AiThemeJobs.
    internal sealed class CodexAppServerClient : IDisposable
    {
        private readonly JavaScriptSerializer serializer = new JavaScriptSerializer();
        private readonly object sync = new object();
        private readonly Dictionary<int, WaitHandleResult> pending = new Dictionary<int, WaitHandleResult>();
        private Process process;
        private int nextId;
        public event Action<string, Dictionary<string, object>> Notification;

        public void Connect()
        {
            if (process != null && !process.HasExited) return;
            string executable = ResolveExecutable();
            ProcessStartInfo start = new ProcessStartInfo(executable, "app-server --listen stdio://") { UseShellExecute = false, RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true, CreateNoWindow = true, StandardOutputEncoding = new UTF8Encoding(false), StandardErrorEncoding = new UTF8Encoding(false) };
            process = Process.Start(start);
            process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (!string.IsNullOrWhiteSpace(e.Data)) HandleLine(e.Data); };
            process.BeginOutputReadLine(); process.BeginErrorReadLine();
            Request("initialize", new Dictionary<string, object> { { "clientInfo", new Dictionary<string, object> { { "name", "codex-theme-studio" }, { "version", "2.7.5" } } } }, 15000);
            Notify("initialized", new Dictionary<string, object>());
        }

        public Dictionary<string, object> Request(string method, object parameters, int timeoutMs)
        {
            if (process == null || process.HasExited) throw new InvalidOperationException("Codex app-server 未运行。" );
            int id = Interlocked.Increment(ref nextId); WaitHandleResult wait = new WaitHandleResult(); lock (sync) pending.Add(id, wait);
            try
            {
                Write(new Dictionary<string, object> { { "jsonrpc", "2.0" }, { "id", id }, { "method", method }, { "params", parameters } });
                if (!wait.Signal.WaitOne(timeoutMs)) throw new TimeoutException("Codex app-server 请求超时：" + method);
                if (!string.IsNullOrEmpty(wait.Error)) throw new InvalidOperationException(wait.Error);
                return wait.Result ?? new Dictionary<string, object>();
            }
            finally { lock (sync) pending.Remove(id); wait.Signal.Dispose(); }
        }

        public void Notify(string method, object parameters) { Write(new Dictionary<string, object> { { "jsonrpc", "2.0" }, { "method", method }, { "params", parameters } }); }

        private void Write(object value)
        {
            if (process == null || process.HasExited) throw new InvalidOperationException("Codex app-server 已退出。" );
            process.StandardInput.WriteLine(serializer.Serialize(value)); process.StandardInput.Flush();
        }

        private void HandleLine(string line)
        {
            try
            {
                Dictionary<string, object> message = serializer.DeserializeObject(line) as Dictionary<string, object>; if (message == null) return;
                int id;
                if (message.ContainsKey("id") && int.TryParse(Convert.ToString(message["id"]), out id))
                {
                    lock (sync) { if (!pending.ContainsKey(id)) return; WaitHandleResult wait = pending[id]; wait.Result = message.ContainsKey("result") ? message["result"] as Dictionary<string, object> : null; wait.Error = message.ContainsKey("error") ? Convert.ToString(((message["error"] as Dictionary<string, object>) ?? new Dictionary<string, object>())["message"]) : null; wait.Signal.Set(); } return;
                }
                string method = message.ContainsKey("method") ? Convert.ToString(message["method"]) : string.Empty;
                Dictionary<string, object> parameters = message.ContainsKey("params") ? message["params"] as Dictionary<string, object> : null;
                if (!string.IsNullOrEmpty(method) && Notification != null) Notification(method, parameters ?? new Dictionary<string, object>());
            }
            catch (ArgumentException) { }
        }

        private static string ResolveExecutable()
        {
            string configured = Environment.GetEnvironmentVariable("CODEX_CLI_PATH");
            if (!string.IsNullOrWhiteSpace(configured) && File.Exists(configured)) return configured;
            string[] candidates = { Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "nodejs", "node_global", "codex.cmd"), "codex.exe" };
            foreach (string candidate in candidates) if (File.Exists(candidate) || string.Equals(candidate, "codex.exe", StringComparison.OrdinalIgnoreCase)) return candidate;
            throw new FileNotFoundException("未找到 Codex CLI；请安装 codex-cli 0.144.0 或更高版本。");
        }
        public void Dispose() { try { if (process != null && !process.HasExited) process.Kill(); } catch { } if (process != null) process.Dispose(); }
        private sealed class WaitHandleResult { public readonly AutoResetEvent Signal = new AutoResetEvent(false); public Dictionary<string, object> Result; public string Error; }
    }
}
