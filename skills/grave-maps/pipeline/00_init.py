"""작업 폴더 만들기. usage: python 00_init.py <작업 폴더> [--example] [--user <osu id>] [--dan <목표 dan raw>]
--example: 포함된 예제 데이터셋(무덤 4K 1,182맵, 계산 끝난 상태)을 복사해 05단계부터 바로 돌릴 수 있게 한다."""
import argparse, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

ap = argparse.ArgumentParser()
ap.add_argument("work"); ap.add_argument("--example", action="store_true")
ap.add_argument("--user", type=int); ap.add_argument("--dan", type=float)
a = ap.parse_args()
W = os.path.abspath(a.work)
os.makedirs(W, exist_ok=True)

cp = os.path.join(W, "config.json")
cfg = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {"osu_user_id": None, "target_dan": 11.0}
if a.user: cfg["osu_user_id"] = a.user
if a.dan: cfg["target_dan"] = a.dan
json.dump(cfg, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

sp = os.path.join(W, "secrets.json")
if not os.path.exists(sp):
    json.dump({"client_id": "", "client_secret": ""}, open(sp, "w"), indent=2)

if a.example:
    E = ROOT + "/example"
    shutil.copy(E + "/cands.jsonl", W + "/cands.jsonl")
    shutil.copy(E + "/res3.jsonl", W + "/res3_example.jsonl")
    os.makedirs(W + "/rawat", exist_ok=True)
    shutil.copy(E + "/rawat.jsonl", W + "/rawat/out_example.jsonl")
    shutil.copy(E + "/thumbs.json", W + "/thumbs.json")
    shutil.copy(E + "/scv_cache.json", W + "/scv_cache.json")
    os.makedirs(W + "/osu", exist_ok=True)
    for f in os.listdir(E + "/osu"):
        if not os.path.exists(f"{W}/osu/{f}"): shutil.copy(f"{E}/osu/{f}", f"{W}/osu/{f}")
    open(W + "/dl.log", "w").write("DONE example\n")
    print("예제 데이터 복사 완료 → 05_played.py(선택) / 06_classify.py / 07_build.py")
print("작업 폴더:", W)
print("config.json:", json.dumps(cfg, ensure_ascii=False))
if not cfg.get("osu_user_id"): print("※ osu_user_id가 비어 있습니다(05_played.py에 필요).")
