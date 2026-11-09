"""2단계 다운로드: cands.jsonl의 기준 차트 .osu → osu/<id>.osu (초당 1개 이하). 재시작 가능.
끝나면 dl.log에 DONE을 쓴다(03_calc.py 워커는 다운로드와 동시에 돌 수 있고, DONE을 보면 없는 파일을 건너뛰고 끝난다)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fetch, jsonl, throttle, work_arg

W = work_arg()
C = jsonl(W + "/cands.jsonl")
os.makedirs(W + "/osu", exist_ok=True)
log = open(W + "/dl.log", "a", encoding="utf-8")
ok = fail = 0
for i, x in enumerate(C):
    p = f"{W}/osu/{x['key']}.osu"
    if os.path.exists(p): ok += 1; continue
    throttle()
    try: data = fetch(f"https://osu.ppy.sh/osu/{x['key']}")
    except Exception as e: data = None; log.write(f"FAIL {x['key']} {e}\n")
    if data and data.lstrip(b"\xef\xbb\xbf").startswith(b"osu file format"):
        open(p, "wb").write(data); ok += 1
    else: fail += 1
    if i % 50 == 0:
        log.write(f"{i + 1}/{len(C)} ok {ok} fail {fail}\n"); log.flush()
        print(f"{i + 1}/{len(C)} ok {ok} fail {fail}", flush=True)
log.write(f"DONE {len(C)} ok {ok} fail {fail}\n"); log.close()
print(f"끝: {len(C)}개 중 ok {ok}, 실패 {fail}")
