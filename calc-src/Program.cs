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
using MsdFacade = LazerSRebirth.Dan.Msd.Msd;

// args: dir of <hash>.osu — 1.0x, no mods: sunny (ChartVariantCalculator), dan (DanInfoWidget과 같은 경로), tags (MapDataBuilder.BuildTagsAsync와 같은 경로)
if (args.Length > 1 && args[1] == "--worker") { await Worker.Run(args[0]); return; }
if (args.Length > 3 && args[1] == "--worker3") { await Worker3.Run(args[0], int.Parse(args[2]), int.Parse(args[3])); return; }
if (args.Length > 2 && args[1] == "--straincv") { StrainCv.Run(args[0], args[2]); return; }
if (args.Length > 2 && args[1] == "--rawat") { await RawAt.Run(args[0], args[2]); return; }
if (args.Length > 1 && args[1] == "--danentry") { await DanEntry.Run(args[0]); return; }
if (args.Length > 1 && args[1] == "--clusters") { await ClusterDump.Run(args[0]); return; }
if (args.Length > 1 && args[1] == "--timing") { await Timing.Run(args[0]); return; }
var output = new List<object>();
foreach (var path in Directory.GetFiles(args[0], "*.osu"))
{
    string hash = Path.GetFileNameWithoutExtension(path);
    string text = File.ReadAllText(path);
    var decoded = ManiaBeatmapLoader.DecodeFile(path);
    double sunny = ChartVariantCalculator.Compute(decoded, 1.0, "")!.Sr;
    double? star = null;
    try { var r = new ManiaRuleset(); star = new ManiaDifficultyCalculator(r.RulesetInfo, new FlatWorkingBeatmap(decoded)).Calculate(Array.Empty<Mod>()).StarRating; } catch { }
    var map = ManiaBeatmapParser.Parse(text);
    var msd = MsdFacade.ComputeMsd(text, new MsdOptions { Rate = 1.0, KeyCount = map.KeyCount })?.Values;
    var input = new ClassifyChartInput { Rate = 1.0, StarRating = star, TotalLength = map.TotalLength > 0 ? map.TotalLength / 1000 : null, Version = map.Version };
    var c = await DanClassifier.ClassifyChartWithCompanellaAsync(text, input, msd);
    var tags = ChartTags.Derive(c, msd, map.TotalLength / 1000);
    object? half(DanVerdictHalf? h) => h == null ? null : new { display = h.DisplayName, raw = h.RawDan, label = h.Label, boundary = h.Boundary };
    output.Add(new { hash, keys = c.KeyCount, sunny, rc = half(c.Rc), ln = half(c.Ln), primaryDan = half(c.Primary), primary = tags.Primary, sub = tags.SubTags, vibro = c.Vibro });
}
Console.WriteLine(JsonSerializer.Serialize(output));
