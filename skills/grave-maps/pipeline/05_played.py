"""5단계(선택) 플레이 기록: config의 osu_user_id가 한 번이라도 친 차트 → played.json {beatmap_id: 플레이 수}.
osu! API users/{id}/beatmapsets/most_played(전체 플레이 기록, 무덤 맵 포함)를 끝까지 넘긴다. 없으면 06단계는 전부 '안 친 맵'으로 본다."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import api, load_config, work_arg

W = work_arg(); cfg = load_config(W)
uid = cfg.get("osu_user_id")
if not uid: sys.exit("config.json에 osu_user_id를 넣으세요.")
played = {}; off = 0
while True:
    page = api(W, f"users/{uid}/beatmapsets/most_played", limit=100, offset=off)
    for x in page: played[str(x["beatmap_id"])] = x["count"]
    if len(page) < 100: break
    off += 100
    if off % 1000 == 0: print(f"{off}개…", flush=True)
json.dump(played, open(W + "/played.json", "w"))
print(f"끝: 친 차트 {len(played)}개")
