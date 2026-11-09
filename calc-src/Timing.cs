using LazerSRebirth.Dan.Types;
using System.Diagnostics;
using LazerSRebirth.Dan;
using LazerSRebirth.Dan.Beatmap;
using LazerSRebirth.Dan.Classifier;
using LazerSRebirth.Dan.Msd;
using LazerSRebirth.Sunny;
using osu.Game.Beatmaps;
using osu.Game.Rulesets.Mania;
using osu.Game.Rulesets.Mania.Difficulty;
using osu.Game.Rulesets.Mods;
public static class Timing {
  public static async Task Run(string dir) {
    var sw = new Stopwatch(); bool first = true;
    foreach (var path in Directory.GetFiles(dir, "*.osu")) {
      string text = File.ReadAllText(path); var t = new Dictionary<string,long>();
      sw.Restart(); var decoded = ManiaBeatmapLoader.DecodeFile(path); var sun = ChartVariantCalculator.Compute(decoded, 1.0, ""); t["sunny+strain"]=sw.ElapsedMilliseconds;
      sw.Restart(); double? star=null; try { var r=new ManiaRuleset(); star=new ManiaDifficultyCalculator(r.RulesetInfo,new FlatWorkingBeatmap(decoded)).Calculate(Array.Empty<Mod>()).StarRating; } catch {} t["osuStar"]=sw.ElapsedMilliseconds;
      var map = ManiaBeatmapParser.Parse(text);
      sw.Restart(); var msd = Msd.ComputeMsd(text, new MsdOptions{Rate=1.0,KeyCount=map.KeyCount})?.Values; t["msd"]=sw.ElapsedMilliseconds;
      sw.Restart(); var c = await DanClassifier.ClassifyChartWithCompanellaAsync(text, new ClassifyChartInput{Rate=1.0,StarRating=star,TotalLength=map.TotalLength/1000,Version=map.Version}, msd); t["classify"]=sw.ElapsedMilliseconds;
      sw.Restart(); var msd12 = Msd.ComputeMsd(text, new MsdOptions{Rate=1.2,KeyCount=map.KeyCount})?.Values; var c12 = await DanClassifier.ClassifyChartWithCompanellaAsync(text, new ClassifyChartInput{Rate=1.2,StarRating=star,TotalLength=map.TotalLength/1000,Version=map.Version}, msd12); t["rate1.2(msd+classify)"]=sw.ElapsedMilliseconds;
      var tags = ChartTags.Derive(c, msd, map.TotalLength/1000);
      Console.WriteLine($"{(first?"[1st]":"")}{Path.GetFileName(path)[..8]} len={map.TotalLength/1000:0}s " + string.Join(" ", t.Select(kv=>$"{kv.Key}={kv.Value}ms")) +
        $" | dan1.0={c.Primary?.DisplayName}({c.Primary?.RawDan}) dan1.2={c12.Primary?.DisplayName}({c12.Primary?.RawDan}) | tag={tags.Primary}+[{string.Join(",",tags.SubTags)}] | patterns=" +
        string.Join(",", c.Patterns.Patterns.Select(h=>$"{h.Id.ToKey()}:{h.Score:0.00}")));
      first=false;
    }
  }
}
