using System.Text.Json;
using LazerSRebirth.Dan;
using LazerSRebirth.Dan.Beatmap;
using LazerSRebirth.Dan.Classifier;
using LazerSRebirth.Dan.Msd;
using osu.Game.Beatmaps;
using LazerSRebirth.Sunny;
using osu.Game.Rulesets.Mania;
using osu.Game.Rulesets.Mania.Difficulty;
using osu.Game.Rulesets.Mods;

// args: <listfile> --danentry → 1.0x부터 0.05씩 올려 RC raw ≥ 10.5 & !vibro 인 첫 배속(최대 1.6x)과 그때의 dan
public static class DanEntry
{
    public static async Task Run(string list)
    {
        foreach (var path in File.ReadAllLines(list).Select(l => l.Trim()).Where(l => l.Length > 0))
        {
            string text = File.ReadAllText(path);
            var map = ManiaBeatmapParser.Parse(text);
            var decoded = ManiaBeatmapLoader.DecodeFile(path);
            double? star = null;
            try { var r = new ManiaRuleset(); star = new ManiaDifficultyCalculator(r.RulesetInfo, new FlatWorkingBeatmap(decoded)).Calculate(Array.Empty<Mod>()).StarRating; } catch { }
            var steps = new List<object>();
            object? entry = null;
            for (int i = 0; i <= 12 && entry == null; i++)
            {
                double rate = Math.Round(1.0 + 0.05 * i, 2);
                var msd = Msd.ComputeMsd(text, new MsdOptions { Rate = rate, KeyCount = map.KeyCount })?.Values;
                var c = await DanClassifier.ClassifyChartWithCompanellaAsync(text,
                    new ClassifyChartInput { Rate = rate, StarRating = star, TotalLength = map.TotalLength / 1000, Version = map.Version }, msd);
                var s = new { rate, kind = c.Primary?.Kind, display = c.Primary?.DisplayName, raw = c.Primary?.RawDan, rcRaw = c.Rc?.RawDan, rcDisplay = c.Rc?.DisplayName, vibro = c.Vibro };
                steps.Add(s);
                if (c.Primary?.Kind == "rc" && c.Primary.RawDan >= 10.5 && !c.Vibro) entry = s;
                if (i == 0 && c.Primary?.Kind != "rc") break; // LN 판정 맵은 배속을 올려도 RC가 되지 않는다
            }
            Console.WriteLine(JsonSerializer.Serialize(new { key = Path.GetFileNameWithoutExtension(path), entry, first = steps[0], last = steps[^1] }));
        }
    }
}
