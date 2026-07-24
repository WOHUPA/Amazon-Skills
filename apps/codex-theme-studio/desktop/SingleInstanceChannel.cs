using System;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Threading;

namespace CodexThemeStudio.Desktop
{
    internal sealed class SingleInstanceChannel : IDisposable
    {
        private readonly string pipeName;
        private readonly CancellationTokenSource cancellation = new CancellationTokenSource();
        private Thread serverThread;

        public SingleInstanceChannel(string userSid)
        {
            pipeName = "CodexThemeStudio." + userSid.Replace("-", string.Empty) + ".Commands";
        }

        public void Start(Action<string> received)
        {
            serverThread = new Thread(new ThreadStart(delegate
            {
                while (!cancellation.IsCancellationRequested)
                {
                    try
                    {
                        using (NamedPipeServerStream server = new NamedPipeServerStream(
                            pipeName, PipeDirection.In, 1, PipeTransmissionMode.Message, PipeOptions.None))
                        {
                            server.WaitForConnection();
                            using (StreamReader reader = new StreamReader(server, new UTF8Encoding(false), false, 4096, true))
                            {
                                string command = reader.ReadLine();
                                if (!string.IsNullOrWhiteSpace(command)) received(command);
                            }
                        }
                    }
                    catch { if (!cancellation.IsCancellationRequested) Thread.Sleep(250); }
                }
            }));
            serverThread.IsBackground = true;
            serverThread.Name = "Codex Theme Studio command pipe";
            serverThread.Start();
        }

        public bool TrySend(string command, int timeoutMilliseconds)
        {
            try
            {
                using (NamedPipeClientStream client = new NamedPipeClientStream(".", pipeName, PipeDirection.Out))
                {
                    client.Connect(timeoutMilliseconds);
                    using (StreamWriter writer = new StreamWriter(client, new UTF8Encoding(false), 4096, true))
                    {
                        writer.WriteLine(command);
                        writer.Flush();
                    }
                }
                return true;
            }
            catch { return false; }
        }

        public void Dispose()
        {
            cancellation.Cancel();
            // Wake a blocked server so its background thread can observe cancellation.
            TrySend("__EXIT__", 100);
            if (serverThread != null) serverThread.Join(500);
            cancellation.Dispose();
        }
    }
}
