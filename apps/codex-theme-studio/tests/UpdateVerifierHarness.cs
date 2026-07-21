using System;
using System.IO;
using System.Reflection;

namespace CodexThemeStudio.Desktop
{
    internal static class UpdateVerifierHarness
    {
        public static int Main(string[] args)
        {
            if (args.Length != 3)
            {
                Console.Error.WriteLine("usage: UpdateVerifierHarness <engine-root> <installer> <signature>");
                return 2;
            }

            string signature = File.ReadAllText(args[2]);
            UpdateService service = new UpdateService(Path.GetTempPath(), args[0], "0.0.0");
            MethodInfo verify = typeof(UpdateService).GetMethod("VerifyMinisign", BindingFlags.Instance | BindingFlags.NonPublic);
            if (verify == null) throw new MissingMethodException("UpdateService.VerifyMinisign");

            verify.Invoke(service, new object[] { args[1], signature });
            string tampered = Path.Combine(Path.GetTempPath(), "codex-theme-studio-tampered-" + Guid.NewGuid().ToString("N") + ".exe");
            File.Copy(args[1], tampered, false);
            try
            {
                using (FileStream stream = new FileStream(tampered, FileMode.Append, FileAccess.Write, FileShare.None))
                    stream.WriteByte(0);
                try
                {
                    verify.Invoke(service, new object[] { tampered, signature });
                    Console.Error.WriteLine("tampered installer unexpectedly passed Minisign verification");
                    return 1;
                }
                catch (TargetInvocationException ex)
                {
                    if (!(ex.InnerException is InvalidDataException)) throw;
                }
            }
            finally
            {
                try { if (File.Exists(tampered)) File.Delete(tampered); } catch { }
            }

            Console.WriteLine("PASS: signed installer accepted and tampered installer rejected.");
            return 0;
        }
    }
}
