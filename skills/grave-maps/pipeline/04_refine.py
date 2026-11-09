"""4단계 배속 다듬기: 진입 배속(dan raw가 target_dan에 가장 가까운 배속)을 refine.step(0.05) 단위로 정한다.
대상 맵마다 반복:
  - target을 둘러싼 두 배속 간격이 step보다 넓으면 그 사이 가운데 배속 하나를 잰다 (예: 1.2x 10.3 / 1.3x 12.3 → 1.25x만)
  - 가장 느린 배속에서도 target보다 높으면 그 아래로 extend개(0.85/0.8/0.75 …, rate_min까지)
  - 가장 빠른 배속에서도 target보다 낮으면 그 위로 extend개(rate_max까지)
결과 rawat/out_*.jsonl {id: "<key>@<rate>", rate, kind, raw, rcRaw, vibro}. 새로 잴 것이 없을 때까지 돈다."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import _rawat_cache, default_shards, jsonl_glob, load_config, passing, rate_points, run_calc, work_arg

W = work_arg(); cfg = load_config(W); F = cfg["refine"]; T = cfg["target_dan"]; step = F["step"]
P, stat = passing(W, cfg)
print("대상 맵", len(P), dict(stat), flush=True)


def wanted(pts):
    rs = sorted(pts)
    if not rs: return []
    for a, b in zip(rs, rs[1:]):
        if pts[a] < T <= pts[b]:
            if b - a > step + 1e-9:
                m = round(round((a + b) / 2 / step) * step, 2)
                if not (a < m < b): m = round(a + step, 2)
                return [m]
            return []
    if pts[rs[0]] > T:
        return [round(rs[0] - step * i, 2) for i in range(1, F["extend"] + 1) if rs[0] - step * i >= F["rate_min"] - 1e-9]
    if pts[rs[-1]] < T:
        return [round(rs[-1] + step * i, 2) for i in range(1, F["extend"] + 1) if rs[-1] + step * i <= F["rate_max"] + 1e-9]
    return []


rnd = 0
while True:
    _rawat_cache.clear()
    have = {o["id"] for o in jsonl_glob(W + "/rawat/*out_*.jsonl")}
    jobs = []
    for c, r, base in P:
        for rate in wanted(rate_points(W, r)):
            i = f"{r['key']}@{rate}"
            if i not in have: jobs.append({"id": i, "path": f"{W}/osu/{r['key']}.osu", "rate": rate})
    if not jobs: break
    rnd += 1
    print(f"{rnd}회차: {len(jobs)}개 계산", flush=True)
    run_calc("rawat", jobs, W + "/rawat", f"r{rnd}_", cfg["calc"]["shards"] or default_shards())
print("끝: 더 잴 배속 없음")
