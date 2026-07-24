using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;

namespace CodexThemeStudio.Desktop
{
    internal sealed class ThemeSeries
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public int Order { get; set; }
    }

    internal sealed class ThemeCatalog
    {
        public const string AllSeriesId = "all";
        public const string UnclassifiedSeriesId = "unclassified";
        private readonly string catalogPath;
        private readonly JavaScriptSerializer serializer = new JavaScriptSerializer();
        private readonly List<ThemeSeries> series = new List<ThemeSeries>();
        private readonly Dictionary<string, string> assignments = new Dictionary<string, string>(StringComparer.Ordinal);
        private readonly Dictionary<string, int> themeOrder = new Dictionary<string, int>(StringComparer.Ordinal);
        private readonly HashSet<string> deletedSeriesIds = new HashSet<string>(StringComparer.Ordinal);

        public ThemeCatalog(string stateRoot, IEnumerable<string> themeIds)
        {
            catalogPath = Path.Combine(Path.GetFullPath(stateRoot), "catalog.json");
            Load();
            MergeBuiltIns(themeIds ?? Enumerable.Empty<string>());
            Save();
        }

        public IList<ThemeSeries> GetSeries()
        {
            List<ThemeSeries> result = new List<ThemeSeries>();
            result.Add(new ThemeSeries { Id = AllSeriesId, Name = "全部", Order = -200 });
            result.AddRange(series.OrderBy(item => item.Order).ThenBy(item => item.Name, StringComparer.CurrentCulture));
            result.Add(new ThemeSeries { Id = UnclassifiedSeriesId, Name = "未分类", Order = int.MaxValue });
            return result;
        }

        public string GetSeriesId(string themeId)
        {
            string value;
            return assignments.TryGetValue(themeId, out value) && series.Any(item => item.Id == value)
                ? value : UnclassifiedSeriesId;
        }

        public int GetThemeOrder(string themeId)
        {
            int value;
            return themeOrder.TryGetValue(themeId, out value) ? value : int.MaxValue;
        }

        public void AssignImported(string seriesId, string seriesName, IEnumerable<string> themeIds)
        {
            ThemeSeries existing = series.FirstOrDefault(item => item.Id == seriesId);
            if (existing == null && !deletedSeriesIds.Contains(seriesId))
            {
                existing = new ThemeSeries { Id = seriesId, Name = seriesName, Order = NextSeriesOrder() };
                series.Add(existing);
            }
            string target = existing == null ? UnclassifiedSeriesId : existing.Id;
            int order = themeOrder.Count == 0 ? 0 : themeOrder.Values.Max() + 1;
            foreach (string themeId in themeIds)
            {
                assignments[themeId] = target;
                themeOrder[themeId] = order++;
            }
            Save();
        }

        public void CreateSeries(string id, string name)
        {
            ValidateIdentity(id, name);
            if (IsVirtual(id) || series.Any(item => item.Id == id))
                throw new InvalidOperationException("系列 ID 已存在：" + id);
            deletedSeriesIds.Remove(id);
            series.Add(new ThemeSeries { Id = id, Name = name.Trim(), Order = NextSeriesOrder() });
            Save();
        }

        public void RenameSeries(string id, string name)
        {
            if (string.IsNullOrWhiteSpace(name) || name.Trim().Length > 80)
                throw new InvalidDataException("系列名称必须为 1-80 个字符。");
            ThemeSeries item = RequireSeries(id);
            item.Name = name.Trim();
            Save();
        }

        public void DeleteSeries(string id)
        {
            ThemeSeries item = RequireSeries(id);
            series.Remove(item);
            deletedSeriesIds.Add(id);
            foreach (string themeId in assignments.Where(pair => pair.Value == id).Select(pair => pair.Key).ToArray())
                assignments.Remove(themeId);
            Save();
        }

        public void MoveTheme(string themeId, string seriesId)
        {
            if (!IsVirtual(seriesId)) RequireSeries(seriesId);
            if (seriesId == AllSeriesId) throw new InvalidOperationException("“全部”不是可分配系列。");
            if (seriesId == UnclassifiedSeriesId) assignments.Remove(themeId);
            else assignments[themeId] = seriesId;
            Save();
        }

        public void MoveSeries(string id, int delta)
        {
            ThemeSeries item = RequireSeries(id);
            List<ThemeSeries> ordered = series.OrderBy(value => value.Order).ToList();
            int index = ordered.IndexOf(item);
            int target = Math.Max(0, Math.Min(ordered.Count - 1, index + delta));
            if (target == index) return;
            ordered.RemoveAt(index);
            ordered.Insert(target, item);
            for (int position = 0; position < ordered.Count; position++) ordered[position].Order = position;
            Save();
        }

        private void MergeBuiltIns(IEnumerable<string> themeIds)
        {
            EnsureBuiltInSeries("basic", "基础主题", 0);
            EnsureBuiltInSeries("doupo", "斗破苍穹", 1);
            foreach (string themeId in themeIds)
            {
                if (assignments.ContainsKey(themeId)) continue;
                if (themeId == "immersive-dark" || themeId == "clear-light" || themeId == "obsidian-gold")
                    assignments[themeId] = "basic";
                else if (themeId.StartsWith("doupo-", StringComparison.Ordinal))
                    assignments[themeId] = "doupo";
            }
        }

        private void EnsureBuiltInSeries(string id, string name, int order)
        {
            if (deletedSeriesIds.Contains(id) || series.Any(item => item.Id == id)) return;
            series.Add(new ThemeSeries { Id = id, Name = name, Order = order });
        }

        private void Load()
        {
            if (!File.Exists(catalogPath)) return;
            Dictionary<string, object> root = serializer.DeserializeObject(File.ReadAllText(catalogPath, Encoding.UTF8)) as Dictionary<string, object>;
            if (root == null || Convert.ToInt32(root["schemaVersion"]) != 1) return;
            object[] rawSeries = root.ContainsKey("series") ? root["series"] as object[] : null;
            if (rawSeries != null)
            {
                foreach (object raw in rawSeries)
                {
                    Dictionary<string, object> item = raw as Dictionary<string, object>;
                    if (item == null) continue;
                    series.Add(new ThemeSeries {
                        Id = Convert.ToString(item["id"]),
                        Name = Convert.ToString(item["name"]),
                        Order = Convert.ToInt32(item["order"])
                    });
                }
            }
            Dictionary<string, object> rawAssignments = root.ContainsKey("assignments") ? root["assignments"] as Dictionary<string, object> : null;
            if (rawAssignments != null)
            {
                foreach (KeyValuePair<string, object> pair in rawAssignments)
                {
                    Dictionary<string, object> value = pair.Value as Dictionary<string, object>;
                    if (value == null) continue;
                    assignments[pair.Key] = Convert.ToString(value["seriesId"]);
                    themeOrder[pair.Key] = Convert.ToInt32(value["order"]);
                }
            }
            object[] rawDeleted = root.ContainsKey("deletedSeriesIds") ? root["deletedSeriesIds"] as object[] : null;
            if (rawDeleted != null) foreach (object value in rawDeleted) deletedSeriesIds.Add(Convert.ToString(value));
        }

        private void Save()
        {
            Dictionary<string, object> assignmentPayload = new Dictionary<string, object>(StringComparer.Ordinal);
            foreach (string themeId in assignments.Keys.Union(themeOrder.Keys).Distinct(StringComparer.Ordinal))
            {
                string seriesId;
                assignments.TryGetValue(themeId, out seriesId);
                assignmentPayload[themeId] = new Dictionary<string, object> {
                    { "seriesId", seriesId ?? UnclassifiedSeriesId },
                    { "order", GetThemeOrder(themeId) }
                };
            }
            Dictionary<string, object> root = new Dictionary<string, object> {
                { "schemaVersion", 1 },
                { "series", series.OrderBy(item => item.Order).Select(item => new Dictionary<string, object> {
                    { "id", item.Id }, { "name", item.Name }, { "order", item.Order }
                }).ToArray() },
                { "assignments", assignmentPayload },
                { "deletedSeriesIds", deletedSeriesIds.OrderBy(value => value, StringComparer.Ordinal).ToArray() }
            };
            WriteAtomic(catalogPath, serializer.Serialize(root) + Environment.NewLine);
        }

        private ThemeSeries RequireSeries(string id)
        {
            ThemeSeries item = series.FirstOrDefault(value => value.Id == id);
            if (item == null) throw new InvalidOperationException("系列不存在：" + id);
            return item;
        }

        private int NextSeriesOrder()
        {
            return series.Count == 0 ? 0 : series.Max(item => item.Order) + 1;
        }

        private static bool IsVirtual(string id)
        {
            return id == AllSeriesId || id == UnclassifiedSeriesId;
        }

        private static void ValidateIdentity(string id, string name)
        {
            if (string.IsNullOrWhiteSpace(id) || id.Length > 80 ||
                !System.Text.RegularExpressions.Regex.IsMatch(id, "^[a-z0-9]+(?:-[a-z0-9]+)*$"))
                throw new InvalidDataException("系列 ID 只能包含小写字母、数字和连字符。");
            if (string.IsNullOrWhiteSpace(name) || name.Trim().Length > 80)
                throw new InvalidDataException("系列名称必须为 1-80 个字符。");
        }

        private static void WriteAtomic(string path, string content)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            string temporary = path + ".tmp-" + Guid.NewGuid().ToString("N");
            File.WriteAllText(temporary, content, new UTF8Encoding(false));
            if (File.Exists(path)) File.Replace(temporary, path, null); else File.Move(temporary, path);
        }
    }
}
