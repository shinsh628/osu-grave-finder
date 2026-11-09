"""공용 함수: 설정, osu! API, .osu 파싱, 배속 세트, 따닥이, SV, 밀도, dan 표기, 계산기 실행."""
import bisect, collections, glob, json, math, os, re, statistics, subprocess, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace("\\", "/")  # skills/grave-maps
CALC = ROOT + "/calc/calc.dll"
UA = "osu-grave-finder (personal toy project)"
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass


# ---------- 설정 ----------
def merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
    return out


def load_config(work):
    cfg = json.load(open(ROOT + "/pipeline/defaults.json", encoding="utf-8"))
    p = os.path.join(work, "config.json")
    if os.path.exists(p):
        cfg = merge(cfg, json.load(open(p, encoding="utf-8")))
    return cfg


def work_arg():
    if len(sys.argv) < 2:
        sys.exit(f"usage: python {os.path.basename(sys.argv[0])} <작업 폴더>")
    w = os.path.abspath(sys.argv[1]).replace("\\", "/")
    if not os.path.isdir(w):
        sys.exit(f"작업 폴더가 없습니다: {w} (00_init.py로 만드세요)")
    return w


def jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if l:
            try: out.append(json.loads(l))
            except ValueError: pass  # 강제 종료로 잘린 마지막 줄
    return out


def jsonl_glob(pattern):
    out = []
    for f in sorted(glob.glob(pattern)):
        out += jsonl(f)
    return out


# ---------- osu! API ----------
_tok = [None, 0.0]; _last = [0.0]


def _cred(work):
    cid, sec = os.environ.get("OSU_CLIENT_ID"), os.environ.get("OSU_CLIENT_SECRET")
    p = os.path.join(work, "secrets.json")
    if not (cid and sec) and os.path.exists(p):
        d = json.load(open(p, encoding="utf-8")); cid, sec = d.get("client_id"), d.get("client_secret")
    if not (cid and sec):
        sys.exit("osu! API 키가 없습니다. <작업 폴더>/secrets.json에 {\"client_id\": ..., \"client_secret\": \"...\"}를 넣거나 "
                 "OSU_CLIENT_ID / OSU_CLIENT_SECRET 환경 변수를 설정하세요. (osu! 설정 → OAuth → 새 OAuth 앱)")
    return str(cid), sec


def throttle(sec=1.05):
    w = sec - (time.time() - _last[0])
    if w > 0: time.sleep(w)
    _last[0] = time.time()


def api(work, path, **q):
    if not (_tok[0] and time.time() < _tok[1]):
        cid, sec = _cred(work)
        body = urllib.parse.urlencode({"client_id": cid, "client_secret": sec, "grant_type": "client_credentials", "scope": "public"}).encode()
        d = json.load(urllib.request.urlopen(urllib.request.Request("https://osu.ppy.sh/oauth/token", data=body, headers={"Accept": "application/json"})))
        _tok[:] = [d["access_token"], time.time() + d["expires_in"] - 120]
    url = "https://osu.ppy.sh/api/v2/" + path + ("?" + urllib.parse.urlencode(q, doseq=True) if q else "")
    for a in range(4):
        throttle()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": "Bearer " + _tok[0], "Accept": "application/json",
                                                                             "x-api-version": "20220705", "User-Agent": UA}), timeout=30)
            return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and a < 3: time.sleep(10 * (a + 1)); continue
            raise


def fetch(url, tries=4, wait=15):
    for a in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read()
        except Exception:
            if a == tries - 1: raise
            time.sleep(wait * (a + 1))


# ---------- 맵셋 / 배속 세트 ----------
RATE_TOKEN = re.compile(r"(?<![\d.])(0\.\d{1,2}|1\.\d{1,2}|2\.0)\s*x|x\s*(0\.\d{1,2}|1\.\d{1,2}|2\.0)\b|(?<![\w.])(0\.\d{1,2}|1\.\d{1,2})(?![\w.])", re.I)
ONE = re.compile(r"(?<![\d.])1\.0+\s*x|x\s*1\.0+\b", re.I)


def groups_of(maps4):
    """같은 노트 수(단·LN)이면서 길이가 다른 난이도 = 배속 세트. 기준(ref, 맨 앞) = 배속 표기가 없거나 1.0x인 난이도."""
    by = {}
    for b in maps4: by.setdefault((b["count_circles"], b["count_sliders"]), []).append(b)
    out = []
    for g in by.values():
        if len(g) == 1 or len({b["total_length"] for b in g}) == 1:
            out += [[b] for b in g]; continue
        plain = [b for b in g if not RATE_TOKEN.search(b["version"]) or ONE.search(b["version"])]
        med = sorted(x["bpm"] for x in g)[len(g) // 2]
        ref = plain[0] if plain else min(g, key=lambda b: abs(b["bpm"] - med))
        out.append([ref] + [b for b in g if b is not ref])
    return out


def rate_of(b, ref):
    if ref["bpm"] and b["bpm"] and abs(b["bpm"] / ref["bpm"] - 1) > 0.004: return round(b["bpm"] / ref["bpm"], 2)
    if b["length"]: return round(ref["length"] / b["length"], 2)
    return 1.0


def members_by_rate(c):
    ref = c["members"][0]
    return {rate_of(b, ref): b for b in c["members"]} if c["is_rate_set"] else {1.0: ref}


# ---------- .osu ----------
def read_osu(path):
    t = open(path, encoding="utf-8", errors="ignore").read()
    ts = []
    for line in t.split("[HitObjects]", 1)[1].splitlines():
        p = line.split(",")
        if len(p) >= 4:
            try: ts.append(int(float(p[2])))
            except ValueError: pass
    ts.sort()
    tps = []
    if "[TimingPoints]" in t:
        for line in t.split("[TimingPoints]", 1)[1].split("\n[", 1)[0].splitlines():
            p = line.strip().split(",")
            if len(p) < 2: continue
            try: tps.append((float(p[0]), float(p[1]), p[6].strip() == "1" if len(p) > 6 else True))
            except ValueError: pass
    return ts, tps


def columns(path, keys=4):
    t = open(path, encoding="utf-8", errors="ignore").read().split("[HitObjects]", 1)[1]
    c = collections.defaultdict(list)
    for line in t.splitlines():
        p = line.split(",")
        if len(p) < 4: continue
        try: c[min(keys - 1, int(float(p[0]) * keys / 512))].append(float(p[2]))
        except ValueError: pass
    return c


# ---------- 지표 ----------
def tadak(cols, rate, cfg):
    """따닥이: 같은 칼럼 연속 노트, 실제 시간 간격이 (15000/max_bpm, 15000/min_bpm + tol]이고 첫 간격 ±tol 유지.
    반환: ratio(따닥이 노트 비율), r2, r3(3따닥+줄연타 비율), main(주력 따닥 BPM, 노트 가중 3% 군집의 중앙값), runs(크기별 개수)."""
    tol = cfg["tol_ms"]; lo = 15000 / cfg["min_bpm"] + tol; hi = 15000 / cfg["max_bpm"]
    total = 0; mem = {"2": set(), "3": set(), "line": set()}; bw = []; runs = collections.Counter()
    for k, ns in cols.items():
        ns = sorted(ns); total += len(ns); i = 0
        while i < len(ns) - 1:
            d0 = (ns[i + 1] - ns[i]) / rate
            if not (hi < d0 <= lo): i += 1; continue
            j = i + 1; ds = [d0]
            while j < len(ns) - 1:
                d = (ns[j + 1] - ns[j]) / rate
                if hi < d <= lo and abs(d - d0) <= tol: ds.append(d); j += 1
                else: break
            n = j - i + 1; z = "2" if n == 2 else "3" if n == 3 else "line"
            runs[z] += 1
            mem[z].update((k, x) for x in ns[i:j + 1]); bw += [15000 / (sum(ds) / len(ds))] * n; i = j
    main = None
    if bw:
        bw.sort(); cl = [[bw[0]]]
        for b in bw[1:]:
            if b / cl[-1][0] - 1 <= cfg["main_cluster"]: cl[-1].append(b)
            else: cl.append([b])
        main = statistics.median(max(cl, key=len))
    total = max(1, total)
    return dict(ratio=len(mem["2"] | mem["3"] | mem["line"]) / total, r2=len(mem["2"]) / total,
                r3=len(mem["3"] | mem["line"]) / total, main=main, runs=dict(runs))


def nps85(ts, rate):
    """1초 창·100ms 간격 국소 NPS(실제 시간)의 85퍼센타일 = '15nps'"""
    if len(ts) < 2: return None
    t = [x / 1000 / rate for x in ts]; vals = []; x = t[0]
    while x <= t[-1]:
        vals.append(bisect.bisect_right(t, x + .5) - bisect.bisect_left(t, x - .5)); x += 0.1
    vals.sort(); return vals[int(len(vals) * .85)]


def sv_triggers(ts, tps):
    """체감 스크롤 = SV × BPM / 지배 BPM. 1% 넘는 변화 트리거를 새 값이 1.0±10% 안(minor)/밖(major)으로 센다."""
    if not ts or not tps: return 0, 0
    tps = sorted(tps, key=lambda p: (p[0], not p[2]))
    end = ts[-1]
    reds = [(p[0], 60000 / p[1]) for p in tps if p[2] and p[1] > 0]
    if not reds: return 0, 0
    dur = {}
    for i, (t0, bpm) in enumerate(reds):
        t1 = reds[i + 1][0] if i + 1 < len(reds) else end
        dur[round(bpm, 3)] = dur.get(round(bpm, 3), 0) + max(0, min(t1, end) - max(t0, ts[0]))
    dom = max(dur, key=dur.get) or reds[0][1]
    states, bpm, sv = [], reds[0][1], 1.0
    for t0, bl, red in tps:
        if red:
            if bl > 0: bpm = 60000 / bl
            sv = 1.0
        elif bl < 0:
            sv = min(10.0, max(0.01, -100 / bl))
        if states and abs(states[-1][0] - t0) < 1: states[-1] = (t0, bpm * sv / dom)
        else: states.append((t0, bpm * sv / dom))
    minor = major = 0; prev = 1.0
    for t0, v in states:
        if t0 > end: break
        if abs(v - prev) > 0.01 * prev:
            if t0 >= ts[0] - 1:
                if abs(v - 1) <= 0.10: minor += 1
                else: major += 1
            prev = v
        elif t0 < ts[0]: prev = v
    return minor, major


_pool = []


def band_pct(raw, val):
    """같은 dan raw대(±0.5, 20개 미만이면 가까운 20개) 참고 모집단 안에서 15nps 백분위"""
    if not _pool: _pool.extend(json.load(open(ROOT + "/data/nps_pool.json")))
    near = sorted(v for r, v in _pool if abs(r - raw) <= 0.5)
    if len(near) < 20: near = sorted(v for r, v in sorted(_pool, key=lambda x: abs(x[0] - raw))[:20])
    return (bisect.bisect_left(near, val) + bisect.bisect_right(near, val)) / 2 / len(near)


DAN_NAMES = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th", 7: "7th", 8: "8th", 9: "9th", 10: "10th",
             11: "alpha", 12: "beta", 13: "gamma", 14: "delta", 15: "epsilon", 16: "zeta", 17: "eta", 18: "theta"}


def dan_label(raw):
    L = math.floor(raw + 0.5); d = raw - L
    suf = "--" if d < -0.3 else "-" if d < -0.1 else "" if d <= 0.1 else "+" if d <= 0.3 else "++"
    return DAN_NAMES.get(L, str(L)) + suf


def base_category(tags, cfg):
    """1.0x 태그 → 출발 분류(speedjack/dump/tech). 대상 태그가 아니면 None."""
    t = tags or {}; p = t.get("primary"); sub = t.get("sub") or []
    g = cfg["patterns"]
    if not (p in g["primary"] or any(s in g["sub"] for s in sub)): return None
    if "speedjack" in sub: return "speedjack"
    if p == "stream" or "dumpstream" in sub: return "dump"
    return "tech"


def passing(W, cfg):
    """03 결과 중 대상 맵: (후보, 계산 결과, 출발 분류) 리스트. 오류·SV·키 수·모음집·태그·vibro·진입 없음을 거른다."""
    C = {c["key"]: c for c in jsonl(W + "/cands.jsonl")}
    pack = re.compile(cfg["search"]["pack_title"], re.I)
    stat = collections.Counter(); out = []
    for r in jsonl_glob(W + "/res3_*.jsonl"):
        c = C.get(r["key"])
        if not c: continue
        if "error" in r: stat["error"] += 1; continue
        if r.get("sv_drop"): stat["sv"] += 1; continue
        if r.get("keys") != 4: stat["keys"] += 1; continue
        if pack.search(c["title"]): stat["pack"] += 1; continue
        base = base_category(r.get("tags"), cfg)
        if not base: stat["tag"] += 1; continue
        if r.get("vibro"): stat["vibro"] += 1; continue
        if not r.get("entry"): stat["no_entry"] += 1; continue
        if sv_triggers(*read_osu(f"{W}/osu/{r['key']}.osu"))[1] >= cfg["sv_drop_major"]: stat["sv"] += 1; continue
        out.append((c, r, base))
    stat["passing"] = len(out)
    return out, stat


def rate_points(W, r):
    """배속 → dan raw: 03의 curve + 04의 추가 배속"""
    pts = {float(x["rate"]): x["raw"] for x in (r.get("curve") or []) if x.get("raw") is not None}
    pts.update(_rawat(W).get(r["key"], {}))
    return pts


_rawat_cache = {}


def _rawat(W):
    if W not in _rawat_cache:
        d = collections.defaultdict(dict)
        for o in jsonl_glob(W + "/rawat/*out_*.jsonl"):
            if "error" in o or o.get("raw") is None: continue
            k, rr = o["id"].rsplit("@", 1); d[k][float(rr)] = o["raw"]
        _rawat_cache[W] = d
    return _rawat_cache[W]


# ---------- 계산기 ----------
def run_calc(mode, jobs, outdir, prefix, shards, env=None):
    """jobs(dict 리스트)를 shards개로 나눠 calc.dll <jobs> --<mode> <out>을 병렬 실행. 이미 out에 있는 id는 계산기가 건너뛴다."""
    os.makedirs(outdir, exist_ok=True)
    procs = []
    e = dict(os.environ, **(env or {}))
    for i in range(shards):
        part = jobs[i::shards]
        if not part: continue
        jp = f"{outdir}/{prefix}jobs_{i}.jsonl"
        with open(jp, "w", encoding="utf-8") as f:
            for j in part: f.write(json.dumps(j) + "\n")
        procs.append(subprocess.Popen(["dotnet", CALC, jp, "--" + mode, f"{outdir}/{prefix}out_{i}.jsonl"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=e))
    for p in procs: p.wait()
    for i in range(shards):
        jp = f"{outdir}/{prefix}jobs_{i}.jsonl"
        if os.path.exists(jp): os.remove(jp)


def default_shards():
    return max(1, (os.cpu_count() or 4) - 2)
