# CLAUDE.md — STT for Conferences, Lectures & Meetings

학회 세미나(주), 강연, 회의 녹음을 전사·문맥교정·요약하고, 발표자료를 통합 조사·보강하는 파이프라인.
전체 설계는 **[PLAN.md](./PLAN.md)**, 자료 보강 스펙은 **[docs/knowledge_pack_example.md](./docs/knowledge_pack_example.md)** 참고.

## 모델 라우팅 정책 (중요)

이 저장소는 **역할별로 모델을 나눠 씁니다.**

| 역할 | 모델 | 담당 |
|---|---|---|
| 계획·설계·리뷰·조율 | **Claude Fable 5** (메인 세션) | 아키텍처 결정, 계획 수립, 코드 리뷰, 서브에이전트 지시·통합 |
| **실제 코드 빌드/구현** | **Claude Opus 4.8** (`builder` 서브에이전트) | 파일 작성, 구현, 테스트, 실행/검증 |

**규칙**: 메인(Fable 5) 세션은 직접 프로덕션 코드를 작성하지 않는다.
구현이 필요하면 `builder` 서브에이전트(Opus 4.8)에 위임한다.
서브에이전트 정의: `.claude/agents/builder.md` (`model: opus`).

호출 예: Agent 도구로 `subagent_type: "builder"` 지정 → Opus 4.8이 구현 수행.

## 빌드 개요

- **언어**: Python 3.11+, 패키지 매니저 `uv` (또는 pip), CLI 진입점 `stt`
- **구조**: PLAN.md §5 프로젝트 구조를 따른다 (`src/stt_pipeline/`)
- **STT**: 클라우드 API 기본(어댑터 패턴, `stt_providers/`), 로컬 mlx-whisper는 폴백. 기본 API는 `bakeoff.py` 결과로 확정
- **LLM 교정/요약/보강**: Claude API (`claude-opus-4-8`), structured outputs + difflib 검증, prompt caching, 배치는 Batch API
- **외부 의존**: `ffmpeg` (시스템 설치 필요)

## 실행에 필요한 입력 (사용자 제공)

- 녹음 파일 (Zoom H1e WAV 등)
- **STT API 키** (예: `OPENAI_API_KEY` — Whisper/gpt-4o-transcribe) — 전사에 필수
- **`ANTHROPIC_API_KEY`** — 교정·요약·보강에 필수 (이게 없으면 원시 전사만 나옴)
- (선택) 발표자료/강연자 정보 — Knowledge Pack 보강용

키·비밀은 코드·커밋에 하드코딩 금지. 환경변수/`.env`(gitignore)만 사용.

## Git

- 개발 브랜치: `claude/stt-conference-system-6bt09c`
- 커밋 후 `git push -u origin claude/stt-conference-system-6bt09c`
- PR은 사용자가 명시적으로 요청할 때만 생성

## 설계 불변 원칙 (구현 시 반드시 준수)

1. **전사(🎤 사실)와 AI 보강(🔍 해설)은 데이터 구조·출력 모두에서 분리.** 절대 병합 금지.
2. **교정은 diff 검증**: `corrections` 목록에 없는 변경은 무단 수정 → 원문 롤백.
3. **보강은 출처 필수**: 근거 못 찾으면 내용 생성 금지, "확인 불가" 표기.
4. **전사 본문 불가침**: 보강·조사는 별도 섹션/주석으로만.
