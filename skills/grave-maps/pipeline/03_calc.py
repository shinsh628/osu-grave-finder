"""3단계 계산: 차트마다 1.0x 패턴 태그 → probe 배속 통과 확인 → curve 배속별 dan raw → 진입 배속의 구간(REST/HARD) → res3_<샤드>.jsonl
통과 = RC dan raw ≥ target_dan − 0.5 이고 vibro가 아님. 태그가 patterns에 안 맞거나 probe에서 통과 못 하면 배속 곡선을 재지 않는다.
SV 변화(체감 ±10% 밖)가 3회 이상이면 계산 없이 버린다. 재시작 가능(이미 결과가 있는 차트는 건너뜀).
--redo-no-curve: 배속 곡선 없이 끝난 결과(태그 불일치·probe 미통과)를 지우고 다시 잰다. patterns를 넓혔거나 target_dan을 낮췄을 때 쓴다."""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CALC, default_shards, jsonl, jsonl_glob, load_config, rate_of, work_arg

W = work_arg(); cfg = load_config(W)
if "--redo-no-curve" in sys.argv:
    import glob
    n = 0
    for f in glob.glob(W + "/res3_*.jsonl"):
        keep = [r for r in jsonl(f) if r.get("curve") or "error" in r or r.get("sv_drop")]
        n += len(jsonl(f)) - len(keep)
        with open(f, "w", encoding="utf-8") as o:
            for r in keep: o.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"곡선 없는 결과 {n}개 지움 → 다시 잰다", flush=True)
C = jsonl(W + "/cands.jsonl")
with open(W + "/jobs3.jsonl", "w", encoding="utf-8") as f:
    for x in C:
        ms = x["members"]; ref = ms[0]
        rates = sorted({rate_of(b, ref) for b in ms if b["passA"]} | {1.0}) if x["is_rate_set"] else [1.0, 1.1, 1.2]
        f.write(json.dumps({"key": x["key"], "rates": [r for r in rates if 0.5 <= r <= 2.0]}) + "\n")
n = cfg["calc"]["shards"] or default_shards()
done = {r["key"] for r in jsonl_glob(W + "/res3_*.jsonl")}
print(f"후보 {len(C)}, 이미 계산 {len(done & {x['key'] for x in C})}, 워커 {n}개 시작", flush=True)
p = cfg["patterns"]
env = dict(os.environ, DAN_PASS=str(cfg["target_dan"] - 0.5), PROBE_RATE=str(cfg["calc"]["probe_rate"]),
           CURVE_RATES=",".join(str(r) for r in cfg["calc"]["curve_rates"]),
           TAG_PRIMARY=",".join(p["primary"]) or "-", TAG_SUB=",".join(p["sub"]) or "-")
procs = [subprocess.Popen(["dotnet", CALC, W, "--worker3", str(i), str(n)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i in range(n)]
for pr in procs: pr.wait()
R = jsonl_glob(W + "/res3_*.jsonl")
print(f"끝: 결과 {len(R)}, 오류 {sum('error' in r for r in R)}, SV 탈락 {sum(bool(r.get('sv_drop')) for r in R)}, "
      f"진입 있음 {sum(bool(r.get('entry')) for r in R)}")
