using System.Text.Json;
using LazerSRebirth.Dan;
using LazerSRebirth.Dan.Beatmap;
using LazerSRebirth.Dan.Classifier;
using LazerSRebirth.Dan.Msd;
using LazerSRebirth.Sunny;
using osu.Game.Beatmaps;
using osu.Game.Rulesets.Mania;
using osu.Game.Rulesets.Mania.Difficulty;
using osu.Game.Rulesets.Mods;

// args: <jobs.jsonl {id, path, rate}> --rawat <out.jsonl> → 그 배속의 primary dan(kind, raw), rc raw, vibro. 이미 있는 id는 건너뜀
public static class RawAt
{
    public static async Task Run(string jobs, string outPath)
    {
        var seen = new HashSet<string>();
        if (File.Exists(outPath)) foreach (var l in File.ReadLines(outPath)) try { seen.Add(JsonDocument.Parse(l).RootElement.GetProperty("id").GetString()!); } catch { }
        using var w = new StreamWriter(outPath, append: true) { AutoFlush = true };
        foreach (var line in File.ReadLines(jobs))
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            var j = JsonDocument.Parse(line).RootElement;
            string id = j.GetProperty("id").GetString()!; if (!seen.Add(id)) continue;
            string path = j.GetProperty("path").GetString()!; double rate = j.GetProperty("rate").GetDouble();
            try
            {
                string text = File.ReadAllText(path);
                var map = ManiaBeatmapParser.Parse(text);
                double? star = null;
                try { var r = new ManiaRuleset(); star = new ManiaDifficultyCalculator(r.RulesetInfo, new FlatWorkingBeatmap(ManiaBeatmapLoader.DecodeFile(path))).Calculate(Array.Empty<Mod>()).StarRating; } catch { }
                var msd = Msd.ComputeMsd(text, new MsdOptions { Rate = rate, KeyCount = map.KeyCount })?.Values;
                var c = await DanClassifier.ClassifyChartWithCompanellaAsync(text, new ClassifyChartInput { Rate = rate, StarRating = star, TotalLength = map.TotalLength / 1000, Version = map.Version }, msd);
                w.WriteLine(JsonSerializer.Serialize(new { id, rate, kind = c.Primary?.Kind, raw = c.Primary?.RawDan, rcRaw = c.Rc?.RawDan, vibro = c.Vibro }));
            }
            catch (Exception e) { w.WriteLine(JsonSerializer.Serialize(new { id, error = e.Message })); }
        }
    }
}
