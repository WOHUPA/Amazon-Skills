using System;
using System.Threading;

namespace CodexThemeStudio.Desktop
{
    internal sealed class RuntimeHealthChangedEventArgs : EventArgs
    {
        public string Status;
        public DateTime ObservedAtUtc;
    }

    internal sealed class RuntimeSupervisor : IDisposable
    {
        private readonly Func<bool, string> statusProbe;
        private readonly Timer timer;
        private int running;
        private string lastStatus = string.Empty;

        public RuntimeSupervisor(NativeThemeEngine engine)
            : this(engine.GetRuntimeStatus, TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(2))
        {
        }

        internal RuntimeSupervisor(Func<bool, string> statusProbe, TimeSpan initialDelay, TimeSpan period)
        {
            if (statusProbe == null) throw new ArgumentNullException("statusProbe");
            this.statusProbe = statusProbe;
            timer = new Timer(Tick, null, initialDelay, period);
        }

        public event EventHandler<RuntimeHealthChangedEventArgs> HealthChanged;
        public string LastStatus { get { return lastStatus; } }

        private void Tick(object ignored)
        {
            if (Interlocked.Exchange(ref running, 1) != 0) return;
            try
            {
                string status = statusProbe(false);
                if (status == "SELF_HEALING")
                {
                    Publish(status);
                    status = statusProbe(true);
                }
                Publish(status);
            }
            catch
            {
                Publish("FAULT");
            }
            finally
            {
                Interlocked.Exchange(ref running, 0);
            }
        }

        internal void RunHealthCheckForTest()
        {
            Tick(null);
        }

        private void Publish(string status)
        {
            if (string.Equals(lastStatus, status, StringComparison.Ordinal)) return;
            lastStatus = status;
            EventHandler<RuntimeHealthChangedEventArgs> handler = HealthChanged;
            if (handler != null)
                handler(this, new RuntimeHealthChangedEventArgs { Status = status, ObservedAtUtc = DateTime.UtcNow });
        }

        public void Dispose()
        {
            timer.Dispose();
        }
    }
}
