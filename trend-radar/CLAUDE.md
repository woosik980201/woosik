# CLAUDE.md — trend-radar

## 1. 프로젝트 개요

trend-radar는 패션·컬처·기술 RSS 피드를 수집해 AI로 큐레이션하는 개인 트렌드 리서치 자동화 봇이다.

- 목적: 매일 아침 흩어진 소스에서 "지금 중요한 흐름"만 걸러 요약
- AI 모델: Groq llama-3.3-70b (Gemini에서 마이그레이션함 — rate limit 이슈로 되돌리지 말 것)
- 자동화: GitHub Actions, 매일 10:00 KST 실행
- 이 폴더는 woosik980201/woosik 레포의 하위 폴더임

## 2. 실행 방법

로컬 실행 (이 폴더, `trend-radar/trend-radar/` 기준):

1. `pip install -r requirements.txt` (또는 `venv` 활성화 후 설치)
2. `.env`에 `GROQ_API_KEY` 설정
3. `python trend_radar.py` — RSS 수집 + 본문 크롤링 + Groq 요약 → `trends_YYYYMMDD.html` / `.md` 생성, `trends.db`에 누적
4. `python build_archive.py` — `trends.db` 전체를 검색 가능한 `index.html` 아카이브로 재생성
5. `python view_trends.py` — 누적 DB 조회/검색 CLI
   - `-n 50` 최근 50개, `-c 패션` 카테고리 필터, `-k 애플` 키워드 검색, `-d 2026-07-03` 날짜 지정, `--stats` 통계만
- Windows에서는 `run_radar.bat` 더블클릭으로 `trend_radar.py` 바로 실행 가능

자동화: 레포 루트의 `.github/workflows/daily-radar.yml`이 매일 `0 1 * * *`(UTC, KST 10:00)에 실행 →
`trend_radar.py` 실행 → `build_archive.py`로 아카이브 갱신 → 결과 파일(`trends_*.html/.md`, `trends.db`, `index.html`) 커밋·푸시 →
`index.html`만 GitHub Pages로 배포.

## 3. 구조

- `trend_radar.py` — 메인 스크립트. `FEEDS`의 RSS 수집 → 본문 크롤링(`fetch_body`) → Groq 큐레이션(`핵심`/`왜 주목` 2줄, `CURATOR_PROMPT`) → 일별 html/md 저장 + `trends.db`에 `link_key`(정규화 URL) 기준 중복 제외 누적
- `build_archive.py` — `trends.db` 전체를 카테고리 탭 + 키워드 검색이 되는 단일 `index.html`로 빌드 (순수 JS, 서버 불필요)
- `view_trends.py` — `trends.db` 조회/검색 CLI
- `compare_summary.py` — 요약 프롬프트 실험용 독립 스크립트 (자동화·`trend_radar.py`와 무관, 결과에 영향 없음)
- `requirements.txt` — feedparser, python-dotenv, groq, requests, beautifulsoup4
- `run_radar.bat` — Windows에서 `trend_radar.py` 더블클릭 실행용
- `trends.db` — SQLite 누적 DB (`trends` 테이블, `link_key` unique index로 중복 방지)
- `trends_YYYYMMDD.html` / `.md` — 일별 스냅샷 산출물 (매일 새로 생성, 검색 불가 — 누적 검색은 `trends.db`/`index.html`/`view_trends.py` 사용)
- `index.html` — `trends.db` 전체 아카이브, GitHub Pages 배포 대상
- `.env` — `GROQ_API_KEY` 보관 (`.gitignore` 처리됨, 커밋 금지)
- `sql_practice.py` / `sql_practice.md`, `practice.db` — SQL 연습용 (`trends.db` 사본 기반, 자동화와 무관)
- `../.github/workflows/daily-radar.yml` — 레포 루트의 GitHub Actions 워크플로 (매일 실행 + Pages 배포)

## 4. 코딩 컨벤션

- 새 RSS 소스 추가 시 기존 소스 정의 패턴을 그대로 따를 것
- 비밀값은 코드에 하드코딩 금지. os.environ / .env / Secrets 경유
- LLM 프롬프트 변경 시 기존 출력 포맷 유지
- 커밋 메시지는 무엇을·왜 바꿨는지 한 줄로

## 5. 알려진 함정 (수정 금지)

- 클라우드 IP 차단 소스: Hypebeast, yozm 등은 GitHub Actions IP에서 요청 차단됨. 로컬에선 되는데 Actions에서만 실패하면 이걸 먼저 의심. 대응 계획: User-Agent 스푸핑 또는 소스 교체
- API 키 노출 사고 이력 있음. .env + .gitignore 반드시 유지, 키를 로그·커밋에 남기지 말 것
- 결과물을 레포에 커밋하는 워크플로는 permissions: contents: write 필요
- Gemini로 회귀 금지 (rate limit 때문에 Groq로 옮긴 것)

## 6. 하지 말 것 (수정 금지)

- .env나 실제 API 키 커밋 금지
- Groq → Gemini 임의 변경 금지
- RSS 차단 문제를 "재시도"로 덮지 말 것 (근본 원인은 IP 차단)
- 큐레이션 출력 포맷을 합의 없이 변경 금지

## 7. TODO

- 차단 소스 해결 (User-Agent 스푸핑 or 소스 교체)
