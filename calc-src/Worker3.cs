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
using osu.Game.Utils;

// 3단계 워커: args <dir> --worker3 <shard> <nshards>
// dir/jobs3.jsonl({key, rates[]}) 중 내 몫을 순서대로, dir/osu/<key>.osu가 생기면 계산한다(다운로드와 동시 진행).
// dir/dl.log에 DONE이 있으면 없는 파일은 건너뛰고 끝낸다. 결과: dir/res3_<shard>.jsonl (재시작 가능)
// 배속을 오름차순으로 재다가 RC raw ≥ DAN_PASS & !vibro인 첫 배속(진입 배속)에서 멈추고, 그 배속의 구간 타이머(실제 시간)를 잰다.
// 환경 변수(모두 선택): DAN_PASS(기본 10.5), PROBE_RATE(1.35), CURVE_RATES("0.9,1.0,...,1.5"),
//   TAG_PRIMARY("stream,tech"), TAG_SUB("dumpstream,speedjack") — 1.0x 태그가 둘 중 하나에 맞아야 배속 계산. 둘 다 "*"면 태그 무시.
public record StepOut(double rate, string? kind, string? display, double? raw, double? rcRaw, bool vibro);

public static class Worker3
{
    static string Env(string k, string d) => Environment.GetEnvironmentVariable(k) is { Length: > 0 } v ? v : d;
    static double[] Nums(string s) => s.Split(',', StringSplitOptions.RemoveEmptyEntries).Select(x => double.Parse(x, System.Globalization.CultureInfo.InvariantCulture)).ToArray();
    static readonly double Pass = Nums(Env("DAN_PASS", "10.5"))[0];
    static readonly double Probe = Nums(Env("PROBE_RATE", "1.35"))[0];
    static readonly double[] Curve = Nums(Env("CURVE_RATES", "0.9,1.0,1.1,1.2,1.3,1.4,1.5"));
    static readonly string[] TagP = Env("TAG_PRIMARY", "stream,tech").Split(',', StringSplitOptions.RemoveEmptyEntries);
    static readonly string[] TagS = Env("TAG_SUB", "dumpstream,speedjack").Split(',', StringSplitOptions.RemoveEmptyEntries);

    public static async Task Run(string dir, int shard, int n)
    {
        string outPath = Path.Combine(dir, $"res3_{shard}.jsonl");
        var seen = new HashSet<string>();
        foreach (var f in Directory.GetFiles(dir, "res3_*.jsonl")) // 샤드 수가 바뀌어도 이어서 돌도록 모든 샤드 결과를 본다
            foreach (var l in ReadShared(f))
                try { seen.Add(JsonDocument.Parse(l).RootElement.GetProperty("key").GetString()!); } catch { }
        var jobs = File.ReadLines(Path.Combine(dir, "jobs3.jsonl")).Where(l => l.Trim().Length > 0)
            .Select(l => JsonDocument.Parse(l).RootElement).Where((_, i) => i % n == shard).ToList();
        using var output = new StreamWriter(outPath, append: true) { AutoFlush = true };
        foreach (var job in jobs)
        {
            string key = job.GetProperty("key").GetString()!;
            if (seen.Contains(key)) continue;
            string path = Path.Combine(dir, "osu", key + ".osu");
            while (!File.Exists(path))
            {
                string log = Path.Combine(dir, "dl.log");
                if (DlDone(log)) break;
                await Task.Delay(2000);
            }
            if (!File.Exists(path)) { output.WriteLine(JsonSerializer.Serialize(new { key, error = "no file" })); continue; }
            await Task.Delay(200);
            object result;
            var rates = job.GetProperty("rates").EnumerateArray().Select(r => r.GetDouble()).Distinct().OrderBy(x => x).ToArray();
            try { result = await One(key, path, rates); }
            catch (Exception e) { result = new { key, error = $"{e.GetType().Name}: {e.Message}" }; }
            output.WriteLine(JsonSerializer.Serialize(result));
        }
    }

    // s3_score.py sv_triggers와 같은 규칙: 체감 스크롤 = SV × BPM / 지배 BPM, 1% 넘는 변화 트리거 중 새 값이 1.0±10% 밖인 횟수
    private static int SvMajor(string text)
    {
        var ts = new List<double>();
        var tps = new List<(double t, double bl, bool red)>();
        string? sec = null;
        foreach (var raw in text.Split('\n'))
        {
            var line = raw.Trim();
            if (line.StartsWith('[')) { sec = line; continue; }
            var p = line.Split(',');
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            if (sec == "[HitObjects]" && p.Length >= 4 && double.TryParse(p[2], System.Globalization.NumberStyles.Float, inv, out var ht)) ts.Add(Math.Floor(ht));
            else if (sec == "[TimingPoints]" && p.Length >= 2 && double.TryParse(p[0], System.Globalization.NumberStyles.Float, inv, out var t0)
                     && double.TryParse(p[1], System.Globalization.NumberStyles.Float, inv, out var bl))
                tps.Add((t0, bl, p.Length > 6 ? p[6].Trim() == "1" : true));
        }
        if (ts.Count == 0 || tps.Count == 0) return 0;
        ts.Sort();
        tps = tps.OrderBy(x => x.t).ThenBy(x => x.red ? 0 : 1).ToList();
        double end = ts[^1], start = ts[0];
        var reds = tps.Where(x => x.red && x.bl > 0).Select(x => (x.t, bpm: 60000 / x.bl)).ToList();
        if (reds.Count == 0) return 0;
        var dur = new Dictionary<double, double>();
        for (int i = 0; i < reds.Count; i++)
        {
            double t1 = i + 1 < reds.Count ? reds[i + 1].t : end;
            double k = Math.Round(reds[i].bpm, 3);
            dur[k] = dur.GetValueOrDefault(k) + Math.Max(0, Math.Min(t1, end) - Math.Max(reds[i].t, start));
        }
        double dom = dur.MaxBy(kv => kv.Value).Key;
        if (dom <= 0) dom = reds[0].bpm;
        var states = new List<(double t, double v)>();
        double bpm = reds[0].bpm, sv = 1.0;
        foreach (var (t0, bl, red) in tps)
        {
            if (red) { if (bl > 0) bpm = 60000 / bl; sv = 1.0; }
            else if (bl < 0) sv = Math.Min(10.0, Math.Max(0.01, -100 / bl));
            if (states.Count > 0 && Math.Abs(states[^1].t - t0) < 1) states[^1] = (t0, bpm * sv / dom);
            else states.Add((t0, bpm * sv / dom));
        }
        int major = 0; double prev = 1.0;
        foreach (var (t0, v) in states)
        {
            if (t0 > end) break;
            if (Math.Abs(v - prev) > 0.01 * prev)
            {
                if (t0 >= start - 1 && Math.Abs(v - 1) > 0.10) major++;
                prev = v;
            }
            else if (t0 < start) prev = v;
        }
        return major;
    }

    private static string[] ReadShared(string path)
    {
        using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        using var sr = new StreamReader(fs);
        return sr.ReadToEnd().Split('\n', StringSplitOptions.RemoveEmptyEntries);
    }

    // 다운로더가 열어 둔 채 쓰는 파일이라 공유 모드로 읽는다
    private static bool DlDone(string log)
    {
        try
        {
            if (!File.Exists(log)) return false;
            using var fs = new FileStream(log, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            using var sr = new StreamReader(fs);
            return sr.ReadToEnd().Contains("DONE");
        }
        catch (IOException) { return false; }
    }

    private static async Task<object> One(string key, string path, double[] rates)
    {
        string text = File.ReadAllText(path);
        var decoded = ManiaBeatmapLoader.DecodeFile(path);
        var map = ManiaBeatmapParser.Parse(text);
        double? star = null;
        try { var r = new ManiaRuleset(); star = new ManiaDifficultyCalculator(r.RulesetInfo, new FlatWorkingBeatmap(decoded)).Calculate(Array.Empty<Mod>()).StarRating; } catch { }

        object? tags = null, hits = null, entry = null, sections = null;
        bool vibro10 = false, tagOk = false;
        // 레이트 모드 탐색(배속 세트 여부 무관): 1.0x(태그) → 1.35x 통과 확인 → 0.9~1.5 7배속 raw → 첫 통과 배속이 진입 배속
        var cache = new Dictionary<double, (StepOut s, bool pass)>();
        async Task<(StepOut s, bool pass)> At(double rate)
        {
            if (cache.TryGetValue(rate, out var v)) return v;
            var msd = Msd.ComputeMsd(text, new MsdOptions { Rate = rate, KeyCount = map.KeyCount })?.Values;
            var c = await DanClassifier.ClassifyChartWithCompanellaAsync(text,
                new ClassifyChartInput { Rate = rate, StarRating = star, TotalLength = map.TotalLength > 0 ? map.TotalLength / 1000 : null, Version = map.Version }, msd);
            var s = new StepOut(rate, c.Primary?.Kind, c.Primary?.DisplayName, c.Primary?.RawDan, c.Rc?.RawDan, c.Vibro);
            if (Math.Abs(rate - 1.0) < 1e-6)
            {
                var t = ChartTags.Derive(c, msd, map.TotalLength / 1000);
                tags = new { primary = t.Primary, sub = t.SubTags };
                hits = c.Patterns.Patterns.Select(h => new { id = h.Id.ToKey(), score = h.Score }).ToList();
                vibro10 = c.Vibro;
                tagOk = (TagP.Contains("*") && TagS.Contains("*")) || TagP.Contains(t.Primary) || t.SubTags.Any(x => TagS.Contains(x));
            }
            return cache[rate] = (s, c.Primary?.Kind == "rc" && c.Primary.RawDan >= Pass && !c.Vibro);
        }
        int svMajor = SvMajor(text);
        if (svMajor >= 3) return new { key, keys = map.KeyCount, sv_drop = svMajor }; // 체감 SV ±10% 밖 3회 이상 → 계산 없이 버림
        var first = await At(1.0);
        object? probe = null, curve = null;
        bool force = Environment.GetEnvironmentVariable("S3_FORCE") == "1"; // 분석용: 태그 무시, 진입 없으면 1.0x 구간
        if ((tagOk || force) && first.s.kind == "rc")
        {
            var p = await At(Probe);
            probe = p.s;
            if (p.pass)
            {
                var seven = new List<StepOut>();
                foreach (double r in Curve)
                {
                    var x = await At(r);
                    seven.Add(x.s);
                    if (entry == null && x.pass) entry = x.s;
                }
                curve = seven.Select(x => new { x.rate, x.raw, x.vibro });
                if (entry is StepOut e) sections = Sections(decoded, e.rate);
            }
        }
        if (force && sections == null) sections = Sections(decoded, 1.0);
        return new { key, keys = map.KeyCount, length_s = map.TotalLength / 1000, star, tags, hits, vibro = vibro10, entry, sections, first = first.s, probe, curve };
    }

    // LazerSRebirth.App SectionTimeline.Calculate(기본값 0.75 / 4000ms)를 그대로 옮김. 시간은 배속을 나눈 실제 시간(ms).
    private static object? Sections(IBeatmap decoded, double rate)
    {
        var names = new List<string>();
        if (rate > 1.0 + 1e-9) names.Add("DoubleTime"); else if (rate < 1.0 - 1e-9) names.Add("HalfTime");
        var mods = ManiaBeatmapLoader.CreateMods(names, rate);
        if (Math.Abs(ModUtils.CalculateRateWithMods(mods) - rate) > 1e-6) return null;
        var playable = ManiaBeatmapLoader.ToPlayable(decoded, mods, default);
        var raw = new SunnyManiaDifficultyCalculator().GetStrainTimeline(playable, mods, default)
            .Select(p => (p.Time / rate, p.Strain)).ToArray();
        var segs = Calc(raw, 0.75, 4000);
        if (segs.Count == 0) return null;
        double rest = segs.Where(s => !s.hard).Select(s => s.e - s.s).DefaultIfEmpty(0).Max() / 1000;
        double hard = segs.Where(s => s.hard).Select(s => s.e - s.s).DefaultIfEmpty(0).Max() / 1000;
        double? scv = null; // 최장 HARD 블록 [시작+1s, 끝-1s]의 strain 곡선(SmoothD) CV — StrainCv.cs와 같은 계산
        var hb = segs.Where(s => s.hard).OrderByDescending(s => s.e - s.s).FirstOrDefault();
        if (hb.e > hb.s)
        {
            var (tt, ss) = StrainGraph.SmoothD(raw);
            var v = tt.Zip(ss).Where(p => p.First >= hb.s + 1000 && p.First <= hb.e - 1000).Select(p => p.Second).ToArray();
            if (v.Length > 1) { double m = v.Average(); scv = Math.Round(Math.Sqrt(v.Select(x => (x - m) * (x - m)).Average()) / m, 4); }
        }
        return new { rest = Math.Round(rest, 1), hard = Math.Round(hard, 1), scv, segs = segs.Select(s => new[] { Math.Round(s.s / 1000, 1), Math.Round(s.e / 1000, 1), s.hard ? 1 : 0 }) };
    }

    private static List<(double s, double e, bool hard)> Calc((double Time, double Strain)[] raw, double frac, double minMs)
    {
        var segs = new List<(double s, double e, bool hard)>();
        if (raw.Length == 0) return segs;
        var (times, strains) = StrainGraph.SmoothD(raw);
        if (times.Length == 0) return segs;
        double max = strains.Max();
        if (max <= 0) return segs;
        double[] g = strains.Select(x => Math.Pow(x / max, 3.0 / 2.2)).ToArray();
        double[] sm = StrainGraph.GaussianSmooth(g, 1100.0 / 100.0);
        double smax = sm.Max();
        if (smax <= 0) return segs;
        double th = smax * frac;
        int st = 0; bool hard = sm[0] >= th;
        for (int i = 1; i <= times.Length; i++)
        {
            bool cur = i < times.Length && sm[i] >= th;
            if (i == times.Length || cur != hard)
            {
                double end = i < times.Length ? times[i] : times[i - 1] + 100.0;
                segs.Add((times[st], end, hard));
                if (i < times.Length) { st = i; hard = cur; }
            }
        }
        bool changed = true;
        while (changed)
        {
            changed = false;
            for (int i = segs.Count - 1; i > 0; i--)
                if (segs[i].hard == segs[i - 1].hard) { segs[i - 1] = (segs[i - 1].s, segs[i].e, segs[i - 1].hard); segs.RemoveAt(i); changed = true; }
            for (int i = 0; i < segs.Count; i++)
            {
                if (segs[i].e - segs[i].s <= minMs)
                {
                    if (segs.Count == 1) break;
                    bool prev = i == segs.Count - 1 || (i > 0 && (segs[i - 1].e - segs[i - 1].s) >= (segs[i + 1].e - segs[i + 1].s));
                    if (prev) { segs[i - 1] = (segs[i - 1].s, segs[i].e, segs[i - 1].hard); segs.RemoveAt(i); }
                    else { segs[i + 1] = (segs[i].s, segs[i + 1].e, segs[i + 1].hard); segs.RemoveAt(i); }
                    changed = true; break;
                }
            }
        }
        return segs;
    }
}
