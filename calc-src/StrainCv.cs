using System.Text.Json;
using LazerSRebirth.Sunny;
using osu.Game.Utils;

// args: <jobs.jsonl {key,path,rate,a,b}> --straincv <out.jsonl>
// 진입 배속 strain 곡선(StrainGraph.SmoothD, 100ms, 실제 시간)에서 [a+1, b-1]초 구간의 CV
public static class StrainCv
{
    public static void Run(string jobs, string outPath)
    {
        using var output = new StreamWriter(outPath) { AutoFlush = true };
        foreach (var line in File.ReadLines(jobs).Where(l => l.Trim().Length > 0))
        {
            var j = JsonDocument.Parse(line).RootElement;
            string key = j.GetProperty("key").GetString()!;
            double rate = j.GetProperty("rate").GetDouble(), a = j.GetProperty("a").GetDouble(), b = j.GetProperty("b").GetDouble();
            try
            {
                var names = new List<string>();
                if (rate > 1.0 + 1e-9) names.Add("DoubleTime"); else if (rate < 1.0 - 1e-9) names.Add("HalfTime");
                var mods = ManiaBeatmapLoader.CreateMods(names, rate);
                var playable = ManiaBeatmapLoader.ToPlayable(ManiaBeatmapLoader.DecodeFile(j.GetProperty("path").GetString()!), mods, default);
                var raw = new SunnyManiaDifficultyCalculator().GetStrainTimeline(playable, mods, default).Select(p => (p.Time / rate, p.Strain)).ToArray();
                var (times, strains) = StrainGraph.SmoothD(raw);
                var v = times.Zip(strains).Where(p => p.First >= (a + 1) * 1000 && p.First <= (b - 1) * 1000).Select(p => p.Second).ToArray();
                double mean = v.Average(), sd = Math.Sqrt(v.Select(x => (x - mean) * (x - mean)).Average());
                double max = strains.Max();
                output.WriteLine(JsonSerializer.Serialize(new { key, cv = sd / mean, mean_rel = mean / max }));
            }
            catch (Exception e) { output.WriteLine(JsonSerializer.Serialize(new { key, error = e.Message })); }
        }
    }
}
