"""1단계 검색: 무덤(graveyard) 맵셋을 즐겨찾기 fav_start부터 한 값씩 내려가며 검색해 후보 차트를 모은다 → cands.jsonl
- 4K 차트를 배속 세트로 묶고(세트는 후보 1개), 별·길이·LN 비율로 1차 거르기
- 제외: 맵 모음집(제목), 서로 다른 4K 차트가 max_charts_per_set 초과인 맵셋, exclude_mapper_ids
- 매퍼(차트 user_id)당 max_per_mapper개까지, 마지막에 후보 min_per_mapper개 미만 매퍼는 뺀다
검색 결과 페이지는 search/에 캐시되어 다시 돌리면 이어서 진행한다."""
import collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import api, groups_of, load_config, work_arg

W = work_arg(); cfg = load_config(W); S = cfg["search"]
os.makedirs(W + "/search", exist_ok=True)
PACK = re.compile(S["pack_title"], re.I)
EXCL = set(S["exclude_mapper_ids"])


def passA(b, star_min):
    n = b["count_circles"] + b["count_sliders"]
    return (star_min <= b["difficulty_rating"] <= S["star_max"] and n > 0 and b["count_sliders"] / n <= S["ln_max"]
            and S["length_min"] <= b["total_length"] <= S["length_max"])


def pages(fav):
    cur, i = None, 0
    while True:
        p = f"{W}/search/f{fav}_{i}.json"
        if os.path.exists(p): r = json.load(open(p, encoding="utf-8"))
        else:
            q = dict(m=3, s="graveyard", sort="favourites_desc", q=f"{S['query']} favourites={fav}")
            if cur: q["cursor_string"] = cur
            r = api(W, "beatmapsets/search", **q)
            json.dump(r, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        yield r
        cur = r.get("cursor_string"); i += 1
        if not cur or not r["beatmapsets"]: break


per_mapper = collections.Counter(); cands = []; stats = collections.Counter()
fav = S["fav_start"]
for fav in range(S["fav_start"], 0, -1):
    n_sets = 0
    for r in pages(fav):
        for st in r["beatmapsets"]:
            n_sets += 1; stats["sets"] += 1
            if st["favourite_count"] != fav: continue
            maps4 = [b for b in st["beatmaps"] if b["mode"] == "mania" and b["cs"] == 4]
            if PACK.search(st["title"]): stats["x_pack"] += 1; continue
            gs = groups_of(maps4)
            if len(gs) > S["max_charts_per_set"]: stats["x_charts"] += 1; continue
            for g in gs:
                ref = g[0]
                ok = any(passA(b, S["star_min"]) for b in g) if len(g) > 1 else passA(ref, S["star_min_single"])
                if not ok: continue
                uid = ref["user_id"]
                if uid in EXCL or st["user_id"] in EXCL: stats["x_excluded"] += 1; continue
                if per_mapper[uid] >= S["max_per_mapper"]: stats["x_cap"] += 1; continue
                per_mapper[uid] += 1
                cands.append({"key": str(ref["id"]), "set": st["id"], "fav": fav, "plays": st["play_count"], "mapper_id": uid, "creator": st["creator"],
                              "title": st["title"], "artist": st["artist"], "tags": st.get("tags", ""), "is_rate_set": len(g) > 1,
                              "members": [{"id": b["id"], "version": b["version"], "bpm": b["bpm"], "star": b["difficulty_rating"], "length": b["total_length"],
                                           "ln_ratio": round(b["count_sliders"] / max(1, b["count_circles"] + b["count_sliders"]), 3),
                                           "passA": passA(b, S["star_min"])} for b in g]})
    print(f"즐겨찾기 {fav}: 맵셋 {n_sets}, 누적 후보 {len(cands)}", flush=True)
    if len(cands) >= S["target_candidates"]: break

n_before = len(cands)
cands = [c for c in cands if per_mapper[c["mapper_id"]] >= S["min_per_mapper"]]
with open(W + "/cands.jsonl", "w", encoding="utf-8") as f:
    for c in cands: f.write(json.dumps(c, ensure_ascii=False) + "\n")
json.dump({"stop_fav": fav, "cands_before_min_per_mapper": n_before, "cands": len(cands), "stats": stats},
          open(W + "/search_summary.json", "w"), indent=1)
print(f"끝: 즐겨찾기 {fav}에서 멈춤, 후보 {n_before} → 매퍼 최소 {S['min_per_mapper']}개 조건 후 {len(cands)}", dict(stats))
