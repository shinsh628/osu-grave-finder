using System.Text.Json;
using LazerSRebirth.Dan;
using LazerSRebirth.Dan.Beatmap;
using LazerSRebirth.Dan.Classifier;
using LazerSRebirth.Dan.Msd;
using LazerSRebirth.Dan.Types;

// args: <listfile of .osu paths> --clusters  → 1.0x tags, hits, LeoBlack clusters (pattern, bpm, amount, specific types)
public static class ClusterDump
{
    public static async Task Run(string list)
    {
        foreach (var path in File.ReadAllLines(list).Select(l => l.Trim()).Where(l => l.Length > 0))
        {
            string text = File.ReadAllText(path);
            var map = ManiaBeatmapParser.Parse(text);
            var msd = Msd.ComputeMsd(text, new MsdOptions { Rate = 1.0, KeyCount = map.KeyCount })?.Values;
            var c = await DanClassifier.ClassifyChartWithCompanellaAsync(text, new ClassifyChartInput { Rate = 1.0, TotalLength = map.TotalLength / 1000, Version = map.Version }, msd);
            var t = ChartTags.Derive(c, msd, map.TotalLength / 1000);
            var rep = c.Clusters?.Report;
            Console.WriteLine(JsonSerializer.Serialize(new {
                key = Path.GetFileNameWithoutExtension(path), primary = t.Primary, sub = t.SubTags,
                hits = c.Patterns.Patterns.Select(h => new { id = h.Id.ToKey(), s = h.Score }),
                dur = rep?.Duration, category = rep?.Category,
                clusters = rep?.Clusters.Select(k => new { p = k.Pattern, bpm = k.BPM, amt = Math.Round(k.Amount), mixed = k.Mixed, spec = k.SpecificTypes.Take(3).Select(s => $"{s.Name}:{s.Ratio:F2}") })
            }));
        }
    }
}
