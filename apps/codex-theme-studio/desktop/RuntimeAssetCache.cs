using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace CodexThemeStudio.Desktop
{
    internal sealed class RuntimeAssetCache
    {
        private readonly string thumbnailRoot;
        private readonly object sync = new object();

        public RuntimeAssetCache(string stateRoot)
        {
            thumbnailRoot = Path.Combine(Path.GetFullPath(stateRoot), "cache", "thumbnails");
            Directory.CreateDirectory(thumbnailRoot);
        }

        public string GetThumbnail(string sourcePath)
        {
            if (string.IsNullOrWhiteSpace(sourcePath) || !File.Exists(sourcePath)) return sourcePath;
            FileInfo source = new FileInfo(sourcePath);
            string identity = source.FullName + "|" + source.Length + "|" + source.LastWriteTimeUtc.Ticks;
            string cachePath = Path.Combine(thumbnailRoot, Hash(identity) + ".jpg");
            if (File.Exists(cachePath))
            {
                try { File.SetLastAccessTimeUtc(cachePath, DateTime.UtcNow); } catch { }
                return cachePath;
            }
            lock (sync)
            {
                if (File.Exists(cachePath)) return cachePath;
                string temporary = cachePath + ".tmp-" + Guid.NewGuid().ToString("N");
                using (Image input = Image.FromFile(sourcePath))
                {
                    int targetWidth = 480;
                    int targetHeight = 270;
                    using (Bitmap output = new Bitmap(targetWidth, targetHeight, PixelFormat.Format24bppRgb))
                    using (Graphics graphics = Graphics.FromImage(output))
                    {
                        graphics.Clear(Color.FromArgb(10, 12, 16));
                        graphics.CompositingQuality = CompositingQuality.HighQuality;
                        graphics.InterpolationMode = InterpolationMode.HighQualityBicubic;
                        graphics.SmoothingMode = SmoothingMode.HighQuality;
                        double scale = Math.Max(targetWidth / (double)input.Width, targetHeight / (double)input.Height);
                        int width = (int)Math.Ceiling(input.Width * scale);
                        int height = (int)Math.Ceiling(input.Height * scale);
                        graphics.DrawImage(input, (targetWidth - width) / 2, (targetHeight - height) / 2, width, height);
                        output.Save(temporary, ImageFormat.Jpeg);
                    }
                }
                File.Move(temporary, cachePath);
                Trim();
                return cachePath;
            }
        }

        private void Trim()
        {
            FileInfo[] files = new DirectoryInfo(thumbnailRoot).GetFiles("*.jpg")
                .OrderByDescending(item => item.LastAccessTimeUtc)
                .ToArray();
            foreach (FileInfo file in files.Skip(128))
            {
                try { file.Delete(); } catch { }
            }
        }

        private static string Hash(string value)
        {
            using (SHA256 sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(value))).Replace("-", string.Empty).ToLowerInvariant();
        }
    }
}
