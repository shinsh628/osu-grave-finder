"""6단계 분류·점수 → final.json (점수순)
진입 배속 = 03 curve + 04 추가 배속 중 dan raw가 target_dan에 가장 가까운 배속(같으면 느린 쪽).
그 배속의 실제 시간으로 따닥이·15nps·REST·HARD·체력맵 평탄도를 내고, config의 classes 규칙(위에서부터 처음 맞는 것)으로 분류한다.
REST/HARD 구간은 03이 잰 진입 배속 구간을 새 배속으로 환산한 값이고, 평탄도(strain CV)는 새 배속에서 다시 잰다(scv_cache.json)."""
import collections, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (band_pct, columns, default_shards, jsonl, load_config, members_by_rate, nps85, passing, rate_points,
                    read_osu, run_calc, sv_triggers, tadak, work_arg)

W = work_arg(); cfg = load_config(W); T = cfg["target_dan"]; SC = cfg["score"]
P, stat = passing(W, cfg)
played = json.load(open(W + "/played.json")) if os.path.exists(W + "/played.json") else {}
RULES = [(k, compile(k["when"], k["id"], "eval")) for k in cfg["classes"]]

rows = []
for c, r, base in P:
    pts = rate_points(W, r)
    rate, raw = min(pts.items(), key=lambda p: (abs(p[1] - T), p[0]))
    sec = r.get("sections") or {"rest": 0, "hard": 0, "segs": []}
    k = r["entry"]["rate"] / rate  # 03 진입 배속 시간 → 새 배속 시간
    hard = sec["hard"] * k
    hs = [(s[0] * k, s[1] * k) for s in sec.get("segs") or [] if s[2]]
    rows.append(dict(c=c, r=r, base=base, rate=rate, raw=raw, pts=sorted(pts.items()), rest=sec["rest"] * k, hard=hard,
                     stamina=hard >= cfg["stamina_hard_s"], hseg=max(hs, key=lambda s: s[1] - s[0]) if hs else None))

# 체력맵 평탄도: 최장 HARD 블록 [시작+1s, 끝−1s]의 strain 곡선 변동계수
cp = W + "/scv_cache.json"
scv = json.load(open(cp)) if os.path.exists(cp) else {}
need = [x for x in rows if x["stamina"] and x["hseg"] and f"{x['r']['key']}@{x['rate']}" not in scv]
if need:
    print(f"체력맵 평탄도 {len(need)}개 계산", flush=True)
    jobs = [{"key": f"{x['r']['key']}@{x['rate']}", "path": f"{W}/osu/{x['r']['key']}.osu", "rate": x["rate"], "a": x["hseg"][0], "b": x["hseg"][1]} for x in need]
    run_calc("straincv", jobs, W + "/scv", "", cfg["calc"]["shards"] or default_shards())
    for i in range(64):
        for o in jsonl(f"{W}/scv/out_{i}.jsonl"):
            if "cv" in o: scv[o["key"]] = round(o["cv"], 4)
    json.dump(scv, open(cp, "w"))

out = []
for x in rows:
    c, r = x["c"], x["r"]; key = r["key"]
    ts, tps = read_osu(f"{W}/osu/{key}.osu")
    td = tadak(columns(f"{W}/osu/{key}.osu"), x["rate"], cfg["tadak"])
    n15 = nps85(ts, x["rate"]); pct = band_pct(x["raw"], n15)
    cv = scv.get(f"{key}@{x['rate']}") if x["stamina"] else None
    minor, major = sv_triggers(ts, tps)
    raw_parts = dict(community=round(min(SC["community_max"], c["fav"] * 1000 / max(1, c["plays"])), 1),
                     density=-min(SC["density_max"], max(0, pct * 100 - 50) / 2),
                     length=-min(SC["rest_max"], max(0, x["rest"] - SC["rest_free_s"])),
                     flat=-min(SC["flat_max"], max(0, (cv - SC["flat_cv0"]) * SC["flat_per_cv"])) if cv is not None else 0,
                     sv=-SC["sv_penalty"] if minor >= SC["sv_minor_count"] else 0)
    score = round(max(0, SC["base"] + sum(raw_parts.values())), 1)
    parts = {k: round(v, 1) for k, v in raw_parts.items()}
    tags = r.get("tags") or {}
    env = dict(base=x["base"], primary=tags.get("primary"), sub=tags.get("sub") or [], ratio=td["ratio"], r2=td["r2"], r3=td["r3"],
               main=td["main"] or 0, stamina=x["stamina"], raw=x["raw"], rate=x["rate"], rest=x["rest"], hard=x["hard"], cv=cv,
               nps15=n15, fav=c["fav"], plays=c["plays"], star=r.get("star"), length=r.get("length_s"), score=score)
    cls = next((k for k, e in RULES if eval(e, {"__builtins__": {}}, env)), None)
    if not cls: stat["no_class"] += 1; continue
    mem = members_by_rate(c)
    if x["rate"] in mem: diff = mem[x["rate"]]; how = "base" if x["rate"] == 1 else "set"
    else: diff = c["members"][0]; how = "mod"
    out.append(dict(key=key, cls=cls["id"], cls_name=cls["name"], score=score, parts=parts, base=x["base"], tags=tags,
                    entry_rate=x["rate"], raw=x["raw"], how=how, rate_points=x["pts"],
                    tadak=round(td["ratio"], 4), tadak_r2=round(td["r2"], 4), tadak_r3=round(td["r3"], 4), tadak_main=td["main"], tadak_runs=td["runs"],
                    nps15=n15, nps_pct=round(pct, 3), rest=round(x["rest"], 1), hard=round(x["hard"], 1), stamina=x["stamina"], strain_cv=cv,
                    sv_minor=minor, sv_major=major, set=c["set"], beatmap_id=diff["id"], version=diff["version"], artist=c["artist"], title=c["title"],
                    mapper=c["creator"], mapper_id=c["mapper_id"], fav=c["fav"], plays=c["plays"], star=r.get("star"), length_s=r.get("length_s"),
                    played=any(str(m["id"]) in played for m in c["members"]),
                    url=f"https://osu.ppy.sh/beatmapsets/{c['set']}#mania/{diff['id']}"))
out.sort(key=lambda m: -m["score"])
json.dump(out, open(W + "/final.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("거르기:", dict(stat))
for k in cfg["classes"]:
    v = sorted(m["score"] for m in out if m["cls"] == k["id"])
    if v:
        print(f"  {k['name']:6} {len(v):5}개 | 체력맵 {sum(m['stamina'] for m in out if m['cls'] == k['id']):4} | "
              f"안 친 맵 {sum(not m['played'] for m in out if m['cls'] == k['id']):5} | 점수 중앙 {statistics.median(v):.1f}")
    else:
        print(f"  {k['name']:6}     0개")
print(f"합계 {len(out)} → {W}/final.json")
