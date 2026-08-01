using System;
using System.Collections.Generic;

namespace CodexThemeStudio.Desktop
{
    internal sealed class NativeThemeEngine
    {
        public string GetRuntimeStatus(bool repair)
        {
            return "OFFLINE";
        }
    }

    internal static class RuntimeSupervisorHarness
    {
        private static int Main()
        {
            TestWatcherRecovery();
            TestIdentityChangeRequiresRestart();
            TestNormalCloseAndReopen();
            TestPausedAndFaultStates();
            Console.WriteLine("PASS: RuntimeSupervisor recovery, restart-consent, close, reopen, pause, and fault transitions verified.");
            return 0;
        }

        private static void TestWatcherRecovery()
        {
            List<bool> repairs = new List<bool>();
            List<string> states = new List<string>();
            using (RuntimeSupervisor supervisor = Create(
                delegate(bool repair)
                {
                    repairs.Add(repair);
                    return repair ? "HEALTHY" : "SELF_HEALING";
                },
                states))
            {
                supervisor.RunHealthCheckForTest();
            }
            Require(repairs.Count == 2 && !repairs[0] && repairs[1], "Watcher exit did not trigger one safe repair.");
            Require(states.Count == 2 && states[0] == "SELF_HEALING" && states[1] == "HEALTHY",
                "Watcher recovery did not publish self-healing then healthy.");
        }

        private static void TestIdentityChangeRequiresRestart()
        {
            int calls = 0;
            List<string> states = new List<string>();
            using (RuntimeSupervisor supervisor = Create(
                delegate(bool repair)
                {
                    calls++;
                    Require(!repair, "Identity mismatch must not silently enter the repair path.");
                    return "NEEDS_RESTART";
                },
                states))
            {
                supervisor.RunHealthCheckForTest();
            }
            Require(calls == 1 && states.Count == 1 && states[0] == "NEEDS_RESTART",
                "Restart refusal was incorrectly reported as healthy.");
        }

        private static void TestNormalCloseAndReopen()
        {
            string current = "OFFLINE";
            List<string> states = new List<string>();
            using (RuntimeSupervisor supervisor = Create(delegate(bool repair) { return current; }, states))
            {
                supervisor.RunHealthCheckForTest();
                current = "HEALTHY";
                supervisor.RunHealthCheckForTest();
            }
            Require(states.Count == 2 && states[0] == "OFFLINE" && states[1] == "HEALTHY",
                "Normal Codex close/reopen transitions were not observed.");
        }

        private static void TestPausedAndFaultStates()
        {
            List<string> paused = new List<string>();
            using (RuntimeSupervisor supervisor = Create(delegate(bool repair) { return "PAUSED"; }, paused))
                supervisor.RunHealthCheckForTest();
            Require(paused.Count == 1 && paused[0] == "PAUSED", "Pause state was lost.");

            List<string> fault = new List<string>();
            using (RuntimeSupervisor supervisor = Create(
                delegate(bool repair) { throw new InvalidOperationException("simulated"); },
                fault))
                supervisor.RunHealthCheckForTest();
            Require(fault.Count == 1 && fault[0] == "FAULT", "Fault state was hidden.");
        }

        private static RuntimeSupervisor Create(Func<bool, string> probe, List<string> states)
        {
            RuntimeSupervisor supervisor = new RuntimeSupervisor(probe, TimeSpan.FromDays(1), TimeSpan.FromDays(1));
            supervisor.HealthChanged += delegate(object sender, RuntimeHealthChangedEventArgs args) { states.Add(args.Status); };
            return supervisor;
        }

        private static void Require(bool condition, string message)
        {
            if (!condition) throw new InvalidOperationException(message);
        }
    }
}
