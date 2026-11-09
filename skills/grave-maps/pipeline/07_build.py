"""7단계 페이지: final.json → grave.html (자켓 썸네일 내장, 파일 하나로 열림)
점수 − star_offset를 points_per_star 점당 별 1개(5개 만점)로 보여주고, 그 값이 음수인 맵은 뺀다.
자켓은 assets.ppy.sh 맵셋 커버를 받아 96px로 줄여 thumbs.json에 캐시한다(Pillow 필요, 없으면 자켓 없이 만든다)."""
import base64, io, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, fetch, load_config, work_arg

W = work_arg(); cfg = load_config(W); PG = cfg["page"]
M = json.load(open(W + "/final.json", encoding="utf-8"))
n_all = len(M)
M = [m for m in M if m["score"] - PG["star_offset"] >= 0 and not (PG.get("hide_played") and m["played"])]

tp = W + "/thumbs.json"
thumbs = json.load(open(tp)) if os.path.exists(tp) else {}
try:
    from PIL import Image
except ImportError:
    Image = None; print("Pillow가 없어 자켓 없이 만듭니다 (pip install Pillow)")
if Image:
    todo = sorted({str(m["set"]) for m in M} - set(thumbs))
    for i, s in enumerate(todo):
        try:
            im = Image.open(io.BytesIO(fetch(f"https://assets.ppy.sh/beatmaps/{s}/covers/list.jpg", tries=2, wait=2))).convert("RGB")
            w, h = im.size; z = min(w, h)
            im = im.crop(((w - z) // 2, (h - z) // 2, (w + z) // 2, (h + z) // 2)).resize((96, 96), Image.LANCZOS)
            b = io.BytesIO(); im.save(b, "JPEG", quality=68, optimize=True)
            thumbs[s] = base64.b64encode(b.getvalue()).decode()
        except Exception:
            thumbs[s] = ""
        if i % 100 == 99:
            print(f"자켓 {i + 1}/{len(todo)}", flush=True); json.dump(thumbs, open(tp, "w"))
    json.dump(thumbs, open(tp, "w"))

rows = [dict(c=m["cls"], s=round(m["score"] - PG["star_offset"], 1), st=int(m["stamina"]), a=m["artist"], t=m["title"], v=m["version"],
             u=m["url"], id=str(m["set"]), tg=[m["tags"].get("primary")] + list(m["tags"].get("sub") or [])) for m in M]
used = {r["id"] for r in rows}
tpl = open(ROOT + "/pipeline/template.html", encoding="utf-8").read()
rep = {"__TITLE__": PG["title"], "__DATA__": json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
       "__THUMBS__": json.dumps({k: v for k, v in thumbs.items() if v and k in used}, separators=(",", ":")),
       "__CLASSES__": json.dumps([[k["id"], k["name"]] for k in cfg["classes"]], ensure_ascii=False),
       "__PAGE__": str(PG["page_size"]), "__PER_STAR__": str(PG["points_per_star"])}
for k, v in rep.items(): tpl = tpl.replace(k, v)
open(W + "/grave.html", "w", encoding="utf-8").write(tpl)
print(f"끝: {len(rows)}맵 (점수 {PG['star_offset']} 미만{' 또는 친 맵' if PG.get('hide_played') else ''} {n_all - len(rows)}개 제외), "
      f"{len(tpl) / 1e6:.2f} MB → {W}/grave.html")
