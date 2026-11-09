# 참고: 정의 · 설정 · 파일 형식

## 용어와 정의

**dan raw**
LazerSRebirth 판정기의 RC(라이스) dan 값이다. 11 = alpha, 12 = beta, 13 = gamma, 14 = delta, 15 = epsilon, 16 = zeta, 17 = eta, 18 = theta이고, 10 이하는 1st~10th다.
표기의 접미사는 반올림 단계와의 차이 d로 정한다.

| d | 접미사 |
|---|---|
| d < −0.3 | `--` |
| −0.3 ≤ d < −0.1 | `-` |
| −0.1 ≤ d ≤ 0.1 | 없음 |
| 0.1 < d ≤ 0.3 | `+` |
| d > 0.3 | `++` |

**통과**
그 배속에서 dan 종류가 rc이고, raw ≥ target_dan − 0.5이고, vibro가 아니어야 한다.

**배속 세트**
같은 맵셋에서 노트 수(단노트·LN)는 같은데 길이가 다른 난이도들을 하나로 묶은 것이다. 기준 난이도 1개를 후보로 삼는다.
진입 배속이 세트에 있는 배속이면 그 난이도로 링크하고(`how=set`), 없으면 기준 난이도에 레이트를 거는 것으로 본다(`how=mod`).

**진입 배속**
잰 배속들(03의 curve + 04의 추가 배속) 중 raw가 target_dan에 가장 가까운 배속이다. 차이가 같으면 느린 쪽을 고른다.
04단계는 target을 둘러싼 두 배속 사이에 0.05 단위로 가운데 배속을 하나 더 잰다. 가장 느린 배속에서도 target보다 높으면 그 아래 배속을 더 잰다.
rate_min(0.5)까지 내려가도 target보다 높은 맵은 가장 가까운 배속을 그대로 쓴다. 그래서 raw가 target에서 멀 수 있다(예제에서 raw < 10.5인 맵이 52개).

**따닥이**
같은 칼럼의 연속 노트로, 실제 시간 간격(맵 ms ÷ 배속)이 15000/max_bpm보다 크고 15000/min_bpm + tol 이하인 것이다. 기본값은 37.5 ms 초과 ~ 103 ms 이하로, 150~400 BPM의 1/4 박자에 해당한다.
- 이어지는 간격이 첫 간격의 ±tol_ms 안이면 하나의 묶음으로 계속 이어진다.
- 묶음 크기: 2노트 = 2따닥, 3노트 = 3따닥, 4노트 이상 = 줄연타. LN도 머리 시각만 보고 일반 노트처럼 센다.

| 지표 | 정의 |
|---|---|
| `ratio` | 따닥이에 속한 노트 수 ÷ 전체 노트 수 |
| `r2` | 2따닥에 속한 노트 비율 |
| `r3` | 3따닥과 줄연타에 속한 노트 비율 |
| `main` | 주력 따닥 BPM. 묶음마다 BPM = 15000 ÷ 평균 간격을 노트 수만큼 가중해 정렬한 뒤, 이웃과 3% 이내면 같은 군집으로 묶고, 가장 큰 군집의 중앙값을 쓴다. |

**출발 분류(`base`)**
1.0x 패턴 태그로 정한다.
- 서브 태그에 speedjack이 있으면 `speedjack`
- 메인 태그가 stream이거나 서브 태그에 dumpstream이 있으면 `dump`
- 나머지는 `tech`

**체력맵**
진입 배속 실제 시간으로 잰 최장 HARD 블록이 stamina_hard_s(70초) 이상인 맵이다.
HARD/REST 블록은 strain 곡선을 정규화하고 매끄럽게 한 뒤 최대치의 75% 이상인 구간을 HARD로 본 것이다. 4초 이하 블록은 이웃 블록에 합친다.

**SV**
체감 스크롤 = SV × BPM ÷ 지배 BPM으로 계산하고, 1% 넘는 변화를 센다.
- 1.0 ± 10% 밖으로 바뀌는 변화가 3회 이상이면 탈락이다.
- 1.0 ± 10% 안의 변화가 3회 이상이면 감점이다.

**15nps**
1초 창, 100 ms 간격으로 잰 국소 NPS(실제 시간)의 85퍼센타일이다.

## 점수 (`score`)
점수 = base(50) + 커뮤니티 − 밀도 − REST − 평탄도 − SV. 0보다 작아지지 않는다.

| 항목 | 계산 | 한도 | 설정 키 |
|---|---|---|---|
| 커뮤니티 | 즐겨찾기 × 1000 ÷ 플레이 수 | 최대 10 | `community_max` |
| 밀도 | 같은 raw대 참고 모집단(`data/nps_pool.json`) 안에서 15nps 백분위가 p일 때 max(0, p×100 − 50) ÷ 2. 밀도가 평범한 수준보다 높을수록 감점이다. | 최대 25 | `density_max` |
| REST | 최장 REST − 40초 | 최대 30 | `rest_free_s`, `rest_max` |
| 평탄도 | 체력맵만. 최장 HARD 블록 안 strain 곡선의 변동계수 cv에 대해 (cv − 0.045) × 400. 체력 구간이 단조로울수록 감점이다. | 최대 20 | `flat_cv0`, `flat_per_cv`, `flat_max` |
| SV | 위 SV 감점 조건에 걸리면 고정 감점 | 20 | `sv_penalty` |

페이지 별점은 (점수 − `page.star_offset`) ÷ `page.points_per_star`이고 5개 만점이다. 이 값이 음수인 맵은 페이지에서 뺀다.

## 분류 규칙 변수 (`classes[].when`)

| 변수 | 뜻 |
|---|---|
| `base` | 출발 분류 `'dump'` / `'tech'` / `'speedjack'` |
| `primary`, `sub` | 1.0x 메인 태그(문자열)와 서브 태그(리스트). 태그 종류: stream, jumpstream, handstream, dumpstream, tech, jack, chordjack, speedjack, stamina 등 |
| `ratio`, `r2`, `r3` | 따닥이 비율 (0~1) |
| `main` | 주력 따닥 BPM (따닥이가 없으면 0) |
| `stamina` | 체력맵 여부 (True/False) |
| `raw`, `rate` | 진입 배속의 dan raw와 배속 |
| `rest`, `hard` | 최장 REST·HARD 블록 길이(초, 실제 시간) |
| `cv` | 체력맵 평탄도 (체력맵이 아니면 None) |
| `nps15`, `fav`, `plays`, `star`, `length`, `score` | 15nps, 즐겨찾기, 플레이 수, 1.0x 별, 길이(초), 점수 |

기본 5분류는 아래와 같다(`defaults.json`).

| 순서 | 분류 | 조건 |
|---|---|---|
| 1 | 따닥덤프 | 덤프이고, 3따닥 이상 10% 미만이고, 따닥이 3% 이상 |
| 2 | 덤프 | 덤프이고, 3따닥 이상 10% 미만 |
| 3 | 따닥테크 | 메인 태그가 jack·chordjack·tech인 스잭이 아니고, 따닥이 8% 이상이고, 주력 BPM 165 초과 |
| 4 | 테크 | 메인 태그가 jack·chordjack·tech인 스잭이 아님 |
| 5 | 스잭 | 나머지 전부 |

순서가 이 결과를 만든다.
- 덤프 중 3따닥 이상이 10% 이상인 맵은 1·2번에 걸리지 않고 테크 쪽으로 간다.
- 메인 태그가 다른 스잭도 테크 쪽으로 간다.

예: "주력 BPM 200 이상인 덤프를 '빠른덤프'로 따로 빼 줘" → 1번 앞에 `{"id": "fast-dump", "name": "빠른덤프", "when": "base == 'dump' and r3 < 0.10 and main >= 200"}`를 넣는다. `classes`는 리스트 전체를 config.json에 넣어야 한다(기본값과 합쳐지지 않고 통째로 바뀐다).

## 새 지표 추가
1. 함수 만들기: `pipeline/common.py`에 `tadak(cols, rate, cfg)` 같은 모양으로 만든다.
   - 입력 `columns(path)`는 {칼럼: [노트 머리 시각 ms]}이고, `read_osu(path)`는 (정렬된 노트 시각, 타이밍 포인트)를 준다.
   - 시간은 반드시 `/ rate`로 실제 시간으로 바꾼다.
2. 06에 연결하기: `pipeline/06_classify.py`에서 `td = tadak(...)` 옆에서 계산하고, `env`에 새 변수로 넣고, `out.append(dict(...))`에도 넣어 final.json에 남긴다.
3. 분류에 쓰기: config의 `classes[].when`에서 그 변수를 쓴다.
4. 다시 돌리기: 06과 07만 다시 돌리면 된다.

## 작업 폴더 파일

| 파일 | 만든 단계 | 내용 |
|---|---|---|
| `config.json`, `secrets.json` | 0 | 사용자 설정(기본값과 합쳐짐), API 키 |
| `search/f<fav>_<n>.json` | 1 | 검색 페이지 캐시 |
| `cands.jsonl` | 1 | 후보 차트 `{key, set, fav, plays, mapper_id, creator, title, artist, is_rate_set, members[{id, version, bpm, star, length, ln_ratio, passA}]}`. members[0]이 기준 난이도 |
| `osu/<key>.osu`, `dl.log` | 2 | .osu 파일, 다운로드 로그(끝에 DONE) |
| `jobs3.jsonl`, `res3_<n>.jsonl` | 3 | 계산 결과 `{key, keys, length_s, star, tags{primary, sub}, hits, vibro, entry{rate, raw, …}, sections{rest, hard, scv, segs[[시작초, 끝초, hard?]]}, first, probe, curve[{rate, raw, vibro}]}` |
| `rawat/*out_*.jsonl` | 4 | 추가 배속 `{id: "<key>@<rate>", rate, kind, raw, rcRaw, vibro}` |
| `played.json` | 5 | `{beatmap_id: 플레이 수}` |
| `scv_cache.json`, `scv/` | 6 | 체력맵 평탄도 캐시 `{"<key>@<rate>": cv}` |
| `final.json` | 6 | 맵별 최종 결과(점수순). cls, score, parts, entry_rate, raw, how, rate_points, tadak*, rest, hard, stamina, strain_cv, url 등 |
| `thumbs.json`, `grave.html` | 7 | 자켓 썸네일 캐시(base64), 결과 페이지 |

## 계산기 직접 쓰기
`dotnet $G/calc/calc.dll <입력> --<모드> <출력>`으로 쓴다.
- `--rawat`: 입력 jsonl `{id, path, rate}` → `{id, rate, kind, raw, rcRaw, vibro}`. 출력 파일에 이미 있는 id는 건너뛴다.
- `--straincv`: `{key, path, rate, a, b}` → `[a+1, b−1]`초 구간 strain CV.
- `<작업 폴더> --worker3 <샤드> <샤드 수>`: 03단계 워커다. 환경 변수 DAN_PASS, PROBE_RATE, CURVE_RATES, TAG_PRIMARY, TAG_SUB를 받는다.
