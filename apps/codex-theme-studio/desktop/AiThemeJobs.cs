using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

namespace CodexThemeStudio.Desktop
{
    // Persistent local work queue for AI-created themes. It deliberately stores only
    // prompts and validated artifact paths: activation remains an explicit later step.
    internal sealed class AiThemeJobs
    {
        private readonly string root;
        private readonly JavaScriptSerializer serializer;

        public AiThemeJobs(string stateRoot, JavaScriptSerializer serializer)
        {
            root = Path.Combine(Path.GetFullPath(stateRoot), "ai-jobs");
            this.serializer = serializer;
            Directory.CreateDirectory(root);
        }

        public AiThemeJob Create(string prompt)
        {
            prompt = (prompt ?? string.Empty).Trim();
            if (prompt.Length < 12 || prompt.Length > 1600) throw new InvalidDataException("创作描述需为 12-1600 个字符。" );
            string id = "job-" + DateTime.UtcNow.ToString("yyyyMMddHHmmss") + "-" + Guid.NewGuid().ToString("N").Substring(0, 8);
            AiThemeJob job = new AiThemeJob { Id = id, Prompt = prompt, Stage = "awaiting-candidate", CreatedAtUtc = DateTime.UtcNow.ToString("o"), UpdatedAtUtc = DateTime.UtcNow.ToString("o") };
            Directory.CreateDirectory(JobRoot(id));
            File.WriteAllText(Path.Combine(JobRoot(id), "prompt.md"), "# Codex Theme 创作任务\r\n\r\n" + prompt + "\r\n", new UTF8Encoding(false));
            Write(job);
            return job;
        }

        public AiThemeJob Latest()
        {
            string[] files = Directory.GetFiles(root, "job.json", SearchOption.AllDirectories);
            AiThemeJob latest = null;
            foreach (string file in files)
            {
                try
                {
                    AiThemeJob candidate = serializer.Deserialize<AiThemeJob>(File.ReadAllText(file, Encoding.UTF8));
                    if (candidate != null && (latest == null || string.CompareOrdinal(candidate.CreatedAtUtc, latest.CreatedAtUtc) > 0)) latest = candidate;
                }
                catch (ArgumentException) { }
                catch (IOException) { }
            }
            return latest;
        }

        public AiThemeRevision AddCandidate(string jobId, string recipePath, string imagePath)
        {
            AiThemeJob job = Read(jobId);
            string recipe = ValidatePath(recipePath, ".json", "Theme Recipe");
            string image = ValidateImagePath(imagePath);
            int number = job.Revisions == null ? 1 : job.Revisions.Count + 1;
            string revisionRoot = Path.Combine(JobRoot(job.Id), "revisions", "v" + number.ToString());
            Directory.CreateDirectory(revisionRoot);
            string savedRecipe = Path.Combine(revisionRoot, "recipe.json");
            string savedImage = Path.Combine(revisionRoot, "background" + Path.GetExtension(image).ToLowerInvariant());
            File.Copy(recipe, savedRecipe, false); File.Copy(image, savedImage, false);
            AiThemeRevision revision = new AiThemeRevision { Number = number, RecipePath = savedRecipe, ImagePath = savedImage, CreatedAtUtc = DateTime.UtcNow.ToString("o") };
            if (job.Revisions == null) job.Revisions = new List<AiThemeRevision>();
            job.Revisions.Add(revision); job.CurrentRevision = number; job.Stage = "candidate-ready"; job.UpdatedAtUtc = DateTime.UtcNow.ToString("o");
            Write(job); return revision;
        }

        public AiThemeRevision CurrentCandidate(string jobId)
        {
            AiThemeJob job = Read(jobId);
            if (job.Revisions == null || job.CurrentRevision < 1 || job.CurrentRevision > job.Revisions.Count) throw new InvalidOperationException("当前创作任务没有可编译的候选版本。" );
            return job.Revisions[job.CurrentRevision - 1];
        }

        public void SetThread(string jobId, string threadId)
        {
            AiThemeJob job = Read(jobId);
            if (string.IsNullOrWhiteSpace(threadId) || threadId.Length > 160) throw new InvalidDataException("Codex thread ID 无效。" );
            job.ThreadId = threadId; job.Stage = "server-ready"; job.UpdatedAtUtc = DateTime.UtcNow.ToString("o"); Write(job);
        }

        public string AddGeneratedImage(string jobId, string sourcePath)
        {
            AiThemeJob job = Read(jobId); string image = ValidateImagePath(sourcePath);
            string folder = Path.Combine(JobRoot(job.Id), "generated"); Directory.CreateDirectory(folder);
            string target = Path.Combine(folder, "candidate-" + ((job.GeneratedImagePaths == null ? 0 : job.GeneratedImagePaths.Count) + 1) + Path.GetExtension(image).ToLowerInvariant());
            File.Copy(image, target, false);
            if (job.GeneratedImagePaths == null) job.GeneratedImagePaths = new List<string>();
            job.GeneratedImagePaths.Add(target); job.Stage = "image-ready"; job.UpdatedAtUtc = DateTime.UtcNow.ToString("o"); Write(job); return target;
        }

        public string JobDirectory(string jobId) { return JobRoot(jobId); }

        private AiThemeJob Read(string id)
        {
            if (string.IsNullOrWhiteSpace(id) || id.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 || id.IndexOf("..", StringComparison.Ordinal) >= 0) throw new InvalidDataException("创作任务 ID 不合法。" );
            string path = Path.Combine(JobRoot(id), "job.json");
            if (!File.Exists(path)) throw new FileNotFoundException("未找到创作任务。", path);
            AiThemeJob job = serializer.Deserialize<AiThemeJob>(File.ReadAllText(path, Encoding.UTF8));
            if (job == null || !string.Equals(job.Id, id, StringComparison.Ordinal)) throw new InvalidDataException("创作任务记录无效。" );
            return job;
        }

        private void Write(AiThemeJob job)
        {
            string path = Path.Combine(JobRoot(job.Id), "job.json"); string temp = path + ".tmp-" + Guid.NewGuid().ToString("N");
            File.WriteAllText(temp, serializer.Serialize(job) + Environment.NewLine, new UTF8Encoding(false));
            if (File.Exists(path)) File.Replace(temp, path, null); else File.Move(temp, path);
        }

        private string JobRoot(string id) { return Path.Combine(root, id); }
        private static string ValidatePath(string value, string extension, string label)
        {
            if (string.IsNullOrWhiteSpace(value)) throw new InvalidDataException("未指定 " + label + "。" );
            string full = Path.GetFullPath(value); if (!File.Exists(full) || !string.Equals(Path.GetExtension(full), extension, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException(label + " 文件无效。" );
            return full;
        }
        private static string ValidateImagePath(string value)
        {
            string full = ValidatePath(value, Path.GetExtension(value), "候选主图");
            string extension = Path.GetExtension(full); if (!string.Equals(extension, ".png", StringComparison.OrdinalIgnoreCase) && !string.Equals(extension, ".jpg", StringComparison.OrdinalIgnoreCase) && !string.Equals(extension, ".jpeg", StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("候选主图必须是 PNG 或 JPEG。" );
            return full;
        }
    }

    internal sealed class AiThemeJob { public string Id; public string Prompt; public string Stage; public string CreatedAtUtc; public string UpdatedAtUtc; public string ThreadId; public List<string> GeneratedImagePaths; public int CurrentRevision; public List<AiThemeRevision> Revisions; }
    internal sealed class AiThemeRevision { public int Number; public string RecipePath; public string ImagePath; public string CreatedAtUtc; }
}
