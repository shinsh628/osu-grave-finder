using System.Text.Json;
using LazerSRebirth.Dan;
using LazerSRebirth.Dan.Beatmap;
using LazerSRebirth.Dan.Classifier;
using LazerSRebirth.Dan.Msd;
using LazerSRebirth.Dan.Types;
using LazerSRebirth.Sunny;
using osu.Game.Beatmaps;
using osu.Game.Rulesets.Mania;
using osu.Game.Rulesets.Mania.Difficulty;
using osu.Game.Rulesets.Mods;

// 작업 폴더의 jobs.jsonl({key, path, rates[]})을 따라가며 results.jsonl에 한 줄씩 결과를 붙인다.
// crawl.done 이 생기고 남은 작업이 없으면 끝난다. 이미 결과가 있는 key는 건너뛴다(재시작 가능).
public static class Worker
{
    public static async Task Run(string dir)
    {
        string jobsPath = Path.Combine(dir, "jobs.jsonl"), resultsPath = Path.Combine(dir, "results.jsonl"), donePath = Path.Combine(dir, "crawl.done");
        var seen = new HashSet<string>();
        if (File.Exists(resultsPath))
            foreach (var line in File.ReadLines(resultsPath))
                try { seen.Add(JsonDocument.Parse(line).RootElement.GetProperty("key").GetString()!); } catch { }

        using var output = new StreamWriter(resultsPath, append: true) { AutoFlush = true };
        int processedLines = 0;

        while (true)
        {
            bool crawlDone = File.Exists(donePath);
            var lines = File.Exists(jobsPath) ? ReadAllLinesShared(jobsPath) : [];
            bool any = false;

            for (int i = processedLines; i < lines.Length; i++)
            {
                if (string.IsNullOrWhiteSpace(lines[i])) continue;
                JsonElement job;
                try { job = JsonDocument.Parse(lines[i]).RootElement; } catch { break; } // 쓰는 중인 마지막 줄
                processedLines = i + 1;
                string key = job.GetProperty("key").GetString()!;
                if (!seen.Add(key)) continue;
                any = true;
                var rates = job.GetProperty("rates").EnumerateArray().Select(r => r.GetDouble()).ToArray();
                object result;
                string path = Path.Combine(dir, "osu", Path.GetFileName(job.GetProperty("path").GetString()!)); // 수집기의 상대 경로 대신 작업 폴더 기준
                try { result = await One(key, path, rates); }
                catch (Exception e) { result = new { key, error = $"{e.GetType().Name}: {e.Message}" }; }
                output.WriteLine(JsonSerializer.Serialize(result));
            }

            if (!any)
            {
                if (crawlDone && processedLines >= lines.Count(l => !string.IsNullOrWhiteSpace(l))) break;
                await Task.Delay(3000);
            }
        }
    }

    private static string[] ReadAllLinesShared(string path)
    {
        using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
        using var sr = new StreamReader(fs);
        return sr.ReadToEnd().Split('\n');
    }

    private static async Task<object> One(string key, string path, double[] rates)
    {
        string text = File.ReadAllText(path);
        var decoded = ManiaBeatmapLoader.DecodeFile(path);
        var map = ManiaBeatmapParser.Parse(text);
        double? star = null;
        try { var r = new ManiaRuleset(); star = new ManiaDifficultyCalculator(r.RulesetInfo, new FlatWorkingBeatmap(decoded)).Calculate(Array.Empty<Mod>()).StarRating; } catch { }

        object? strainStats = null;
        var perRate = new List<object>();
        object? tags = null, hits = null, msd10 = null;
        bool vibro = false;

        foreach (double rate in rates.Distinct().OrderBy(x => x))
        {
            var sun = ChartVariantCalculator.Compute(decoded, rate, "");
            var msd = Msd.ComputeMsd(text, new MsdOptions { Rate = rate, KeyCount = map.KeyCount })?.Values;
            var c = await DanClassifier.ClassifyChartWithCompanellaAsync(text,
                new ClassifyChartInput { Rate = rate, StarRating = star, TotalLength = map.TotalLength > 0 ? map.TotalLength / 1000 : null, Version = map.Version }, msd);
            object? half(DanVerdictHalf? h) => h == null ? null : new { kind = h.Kind, display = h.DisplayName, raw = h.RawDan };
            perRate.Add(new { rate, sunny = sun?.Sr, primary = half(c.Primary), rc = half(c.Rc), ln = half(c.Ln), vibro = c.Vibro });

            if (Math.Abs(rate - 1.0) < 1e-6)
            {
                var t = ChartTags.Derive(c, msd, map.TotalLength / 1000);
                tags = new { primary = t.Primary, sub = t.SubTags };
                hits = c.Patterns.Patterns.Select(h => new { id = h.Id.ToKey(), score = h.Score }).ToList();
                msd10 = msd?.Where(kv => double.IsFinite(kv.Value)).ToDictionary(kv => kv.Key, kv => kv.Value);
                vibro = c.Vibro;
                if (sun != null) strainStats = Uniformity(sun.Strain);
            }
        }

        return new { key, keys = map.KeyCount, length_s = map.TotalLength / 1000, star, tags, hits, msd = msd10, vibro, strain = strainStats, rates = perRate };
    }

    // strain 곡선(100ms 격자) — 노트가 있는 구간의 변동계수와 쉬는 구간 비율
    private static object? Uniformity(StrainGraphData g)
    {
        var v = g.Strain.Where(double.IsFinite).ToArray();
        if (v.Length < 10) return null;
        var sorted = v.OrderBy(x => x).ToArray();
        double median = sorted[sorted.Length / 2];
        if (median <= 0) return null;
        double mean = v.Average();
        double sd = Math.Sqrt(v.Select(x => (x - mean) * (x - mean)).Average());
        double rest = v.Count(x => x < 0.25 * median) / (double)v.Length;
        double p90 = sorted[(int)(sorted.Length * 0.9)];
        return new { cv = sd / mean, rest, peak_ratio = p90 / median };
    }
}
