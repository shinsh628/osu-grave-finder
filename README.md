# osu-grave-finder

osu!mania 4K **무덤(graveyard) 맵**에서 내 실력(목표 dan)에 맞는 연습맵을 찾는 도구입니다.
찾은 맵은 **따닥덤프 · 덤프 · 따닥테크 · 테크 · 스잭** 다섯 분류로 나누고 별점을 매긴 페이지로 보여줍니다.
Claude Code용 스킬로 만들어져 있어서, 설치한 뒤 Claude에게 말로 시키면 됩니다.

- 맵마다 배속별 dan raw를 계산해 목표 dan(기본 alpha = 11)에 가장 가까운 **진입 배속**을 0.05 단위로 정합니다.
- 같은 칼럼 연타인 **따닥이**의 비율과 주력 BPM을 그 진입 배속 기준으로 분석합니다.
- 결과는 분류 탭, 자켓, 별점, 패턴 태그가 있는 HTML 페이지 하나로 나옵니다.
- **예제 데이터셋이 들어 있습니다.** 2026-11 기준 무덤 4K 1,182맵을 계산까지 끝낸 데이터라, 수집 없이 몇 분 만에 결과를 볼 수 있습니다.
- 분류 기준, 따닥이 판정, 점수 가중치, 목표 dan은 Claude에게 말하면 설정 파일에서 바꿔 줍니다.

## 필요한 것
- Windows x64
- Python 3.10 이상. 자켓 썸네일을 넣으려면 `pip install Pillow`도 필요합니다.
- [.NET 10 런타임](https://dotnet.microsoft.com/download/dotnet/10.0) (".NET Runtime" x64)
- (새로 수집할 때만) osu! API 키: osu! 웹 → 설정 → OAuth → 새 OAuth 애플리케이션

## 설치 (Claude Code)
```
/plugin marketplace add shinsh628/osu-grave-finder
/plugin install osu-grave-finder@osu-grave-finder
```
설치한 뒤 Claude Code를 다시 시작하고, 이렇게 말하면 됩니다.

- "예제 데이터로 무덤 연습맵 페이지 만들어 줘"
- "내 osu id는 1234567이야. 목표는 beta(12)로 해서 처음부터 새로 찾아 줘"
- "따닥덤프 기준을 3%에서 5%로 올려 줘" / "주력 BPM 200 넘는 덤프는 빠른덤프로 따로 빼 줘"

플러그인을 쓰지 않는다면 이 저장소를 받은 뒤 Claude Code에 "`skills/grave-maps/SKILL.md` 읽고 따라 해"라고 하면 됩니다.

## 직접 돌리기
`$G` = `skills/grave-maps`
```
python $G/pipeline/00_init.py grave-work --example --user <osu id>
python $G/pipeline/05_played.py grave-work      # 선택, API 키 필요
python $G/pipeline/06_classify.py grave-work
python $G/pipeline/07_build.py grave-work       # → grave-work/grave.html
```
새로 수집하려면 `--example` 없이 init한 다음 `01_search` → `02_download`(백그라운드)와 `03_calc`를 동시에 → `04_refine` → `05` → `06` → `07` 순서로 돌립니다.

단계별 설명은 [SKILL.md](skills/grave-maps/SKILL.md), 정의와 설정 키는 [reference.md](skills/grave-maps/reference.md)에 있습니다.

## 구성
```
.claude-plugin/        플러그인 정의
skills/grave-maps/
  SKILL.md             Claude가 읽는 사용 설명서
  reference.md         정의 · 점수 · 분류 변수 · 파일 형식
  pipeline/            00~07 스크립트, defaults.json(기본 설정), template.html(페이지)
  calc/                dan 판정 계산기 빌드(LazerSRebirth 기반, .NET 10)
  data/nps_pool.json   밀도 점수용 참고 모집단
  example/             예제 데이터셋(후보, 계산 결과, 추가 배속, .osu, 썸네일)
calc-src/              계산기 C# 소스(참고용. 빌드하려면 LazerSRebirth 원본 소스 필요)
```

## 알아 둘 점
- 지인끼리 쓰는 개인 토이 프로젝트입니다.
- dan 판정은 LazerSRebirth의 판정기를 그대로 씁니다.
- 예제 데이터는 검색 당시 특정 매퍼 18명을 뺀 결과이고, 기본 패턴 태그(stream/tech/dumpstream/speedjack)에 맞는 맵만 들어 있습니다.
- osu! 서버에는 초당 1회 이하로만 요청합니다.
