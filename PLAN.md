# 학회·강연·회의 STT 시스템 — 전체 설계 계획

> Zoom H1e로 녹음한 학회 세미나(주 용도), 강연, 회의 음성을
> **여러 억양의 영어/한국어 → 자연스러운 전사 → 문맥 기반 교정 → 교정 내역 리포트 → 요약 정리**
> 까지 자동으로 처리하고, 발표자료·강연자 정보를 함께 주면 **자료를 통합 이해·추가 조사하여 보강 노트**까지 생성하는 파이프라인.

**실행 환경**: MacBook Air M2 15" (단일 머신), 성능(품질) 우선.

---

## 1. 핵심 결론 요약

| 질문 | 결론 |
|---|---|
| 용도별(학회/강연/회의)로 STT 모델을 따로 만들어야 하나? | **아니오. 하나의 통합 파이프라인 + 용도별 "프로필"로 충분** |
| STT는 로컬 vs 클라우드? | **클라우드 API 기본** (M2 Air 팬리스 + 성능 우선 → 로컬 열세). 로컬(mlx-whisper)은 오프라인 폴백만 |
| STT 모델을 직접 학습/파인튜닝해야 하나? | **아니오.** 억양·용어 문제는 자료 기반 용어 주입 + LLM 후처리로 해결 |
| 수정 내역은 어떻게 보여주나? | LLM이 구조화된 교정 목록(JSON)을 출력 + **diff 검증**으로 환각 방지 → 문서 끝에 표로 정리 |
| 발표자료·강연자 정보 통합? | **Knowledge Pack 모듈**로 설계 — 용어 주입(Phase 1) + 조사·보강 노트(Phase 3) |

### 1-1. 왜 통합 모델 하나로 충분한가

학회/강연/회의의 차이는 **음향 모델(STT) 수준의 차이가 아니라 후처리 수준의 차이**입니다.

- **음향 측면**: 셋 다 "실내, 근거리~중거리 마이크, 1~수명의 화자, 자연 발화"라는 동일한 조건.
- **실제로 달라지는 것**: 전문용어 밀도(학회), 단일 화자 긴 흐름(강연), 다화자·액션아이템(회의) — 전부 **(1) 도메인 용어집, (2) 화자분리 on/off, (3) 요약 템플릿**으로 흡수됩니다. 즉 STT 모델이 아니라 **설정 프로필**의 문제입니다.

파인튜닝은 "특정 분야에서 반복적으로 틀리는 패턴이 데이터로 쌓인 뒤"에나 고려할 마지막 수단이며, 그 전에 자료 기반 용어 주입 + LLM 교정 계층이 같은 문제를 훨씬 싸고 유연하게 해결합니다. (교정된 전사 결과를 계속 저장해 두면, 훗날 파인튜닝이 필요해질 때 그대로 학습 데이터가 됩니다.)

### 1-2. 왜 클라우드 STT인가 (M2 Air 판단)

| 항목 | 로컬 (M2 Air) | 클라우드 API |
|---|---|---|
| 속도 | faster-whisper는 맥에서 CPU만 사용 → 1시간 녹음에 2~3시간+. mlx-whisper/whisper.cpp(Metal)로도 10~25분, **팬리스 스로틀링**으로 지속 부하 시 저하 | 1시간 녹음 ≈ 수 분 |
| 정확도 | Whisper large-v3 수준이 상한 | 2026 현재 상용 API(gpt-4o-transcribe, ElevenLabs Scribe, AssemblyAI 등)가 억양 영어·한국어에서 우위 |
| 화자분리 | pyannote를 CPU로 → 매우 느림 | **API 내장 diarization** 사용 가능 → 파이프라인 단순화 |
| 비용 | 무료 (시간·발열 비용) | 시간당 ~$0.4 안팎 |
| 프라이버시 | 유리 | 사용자 우선순위상 허용 (성능 > 보안) |

**결정**: 클라우드 STT 기본. 후보(gpt-4o-transcribe / ElevenLabs Scribe / AssemblyAI, 한국어 비중 높으면 클로바 스피치 추가)를 **실제 세미나 녹음 1개로 직접 비교(bake-off)**하여 기본 API를 확정 — Phase 1 첫 작업. 로컬 mlx-whisper large-v3-turbo는 오프라인 폴백 옵션으로만 유지. LLM 교정·요약·비전 추출은 OpenAI API 기본으로 둡니다.

---

## 2. 전체 아키텍처

```
[입력]
 ├─ 녹음: Zoom H1e WAV (32-bit float)
 └─ 자료(선택): 초록·강연자 정보, PPT 파일, 슬라이드 사진
        │
        ▼
⓪ Knowledge Pack 생성 (자료가 있을 때)
   - PPT 텍스트 추출(python-pptx) / 사진은 OpenAI vision-capable model로 추출
   - 용어·고유명사·논문 레퍼런스 추출
   - (Phase 3) 레퍼런스 논문 조사: Semantic Scholar/arXiv/웹 검색
        │
        ▼
① 전처리 (ffmpeg)
   - 16kHz mono, 라우드니스 정규화(EBU R128), 무음 트리밍
        │
        ▼
② STT (클라우드 API — bake-off로 확정)
   - ko/en 자동 감지, 코드스위칭 대응
   - Knowledge Pack 용어를 프롬프트/키워드 부스팅으로 주입
   - 세그먼트 타임스탬프 + (회의 프로필) 내장 화자분리
        │
        ▼
③ LLM 교정 계층 (OpenAI API)
   - 앞뒤 문맥 + Knowledge Pack 용어집 기반 오인식 교정
   - 구조화된 교정 목록(JSON) + difflib 검증으로 환각 차단
        │
        ▼
④ 정리·요약 (OpenAI API, 프로필별 템플릿)
        │
        ▼
⑤ (Phase 3) 슬라이드-전사 정렬 + 통합 보강 노트
   - 슬라이드별: 🎤 발화 / 📊 슬라이드 전용 내용 / 🔍 AI 조사 보강
        │
        ▼
[산출물] transcript.md / transcript.json / transcript.srt / notes.md
```

---

## 3. 단계별 상세 설계

### ① 전처리

Zoom H1e는 32-bit float, 44.1/48/96kHz로 녹음됩니다. 클리핑 걱정 없이 녹음 후 정규화가 가능하므로 녹음 시 게인을 보수적으로 잡아도 됩니다.

```bash
ffmpeg -i input.wav -ac 1 -ar 16000 -af loudnorm=I=-16:TP=-1.5:LRA=11 prep.wav
```

클라우드 STT는 대부분 자체 VAD를 내장하므로 로컬 VAD는 필수가 아니지만, 업로드 용량 절감을 위해 긴 무음 트리밍은 유지합니다. API의 파일 크기 제한(예: OpenAI 25MB)에 걸리면 무음 경계 기준으로 분할 업로드합니다(문장 중간 절단 방지).

### ② STT (클라우드)

- **기본 후보**: gpt-4o-transcribe(OpenAI), ElevenLabs Scribe(diarization 내장), AssemblyAI. 한국어 단독 세션 비중이 높으면 클로바 스피치도 후보.
- **선정 방법**: 실제 세미나 녹음 1개(억양 영어 + 한영 혼용 구간 포함)로 동일 구간 전사를 비교하는 bake-off 스크립트를 Phase 1에서 먼저 작성. WER보다 **전문용어·고유명사 정확도**를 중점 평가.
- **용어 주입**: Knowledge Pack에서 추출한 용어를 API별 메커니즘(prompt / keyword boosting / custom vocabulary)으로 전달. 억양 있는 발표의 전문용어 인식률을 올리는 가장 효과 큰 단일 수단.
- **화자분리**: 회의 프로필은 diarization 내장 API 사용(pyannote 로컬 실행 제거). 학회 Q&A는 "발표자/질문자" 경량 구분.

### ③ LLM 교정 계층 — 이 시스템의 핵심

**목표**: 억양·소음으로 인한 오인식 단어를 앞뒤 문맥으로 복원하되, **원문을 마음대로 다시 쓰지 않게** 통제하고, 수정한 곳을 전부 추적.

**모델**: OpenAI text model을 기본으로 사용하되, 실제 모델명은 설정값(`OPENAI_MODEL`, `OPENAI_VISION_MODEL`)으로 둡니다.
- 실시간이 필요 없으므로 배치/비동기 처리 옵션을 우선 고려
- 1시간 세미나 ≈ 전사 1만~1.5만 토큰 → 모델별 비용은 선택한 OpenAI 모델 기준으로 산정

**처리 방식**:

1. 전사를 **세그먼트 ID가 붙은 청크**(약 4천 토큰, 앞뒤 500토큰 오버랩)로 분할
2. 각 청크를 아래 계약으로 OpenAI LLM provider에 전달:
   - 시스템 프롬프트(고정, **prompt caching** 적용): 교정 규칙 + Knowledge Pack 용어집
   - 출력(structured outputs, JSON schema 강제):

```json
{
  "corrected_segments": [
    {"id": "seg_012", "text": "이 실험에서 CRISPR-Cas9을 사용해서..."}
  ],
  "corrections": [
    {
      "segment_id": "seg_012",
      "original": "크리스퍼 캐스나인",
      "corrected": "CRISPR-Cas9",
      "reason": "음성 오인식 — 문맥상 유전자 편집 도구 명칭",
      "confidence": "high"
    }
  ]
}
```

3. **환각 방지 이중 검증**:
   - `difflib`로 원문 ↔ 교정문 실제 diff 계산
   - diff에는 있는데 `corrections` 목록에 없는 변경 = 무단 수정 → 원문으로 롤백하고 플래그
   - `confidence: low` 항목은 교정 반영하되 리포트에 ⚠️ 표시 (사람 확인 유도)

**교정 규칙 (시스템 프롬프트 핵심)**:
- 화자의 말투·어순·문체는 유지한다 (다듬기 금지, 오인식 복원만)
- 명백한 음성 오인식만 수정: 전문용어, 고유명사, 숫자/단위, 한영 혼용 표기
- 확신이 없으면 원문 유지 + `uncertain` 플래그
- 모든 수정은 corrections 배열에 기록 — 기록 없는 수정은 무효 처리됨을 명시

### ④ 정리·요약

교정 완료된 전체 전사를 입력으로 프로필별 템플릿 요약을 생성합니다. 긴 전사는 OpenAI LLM provider의 컨텍스트 한도에 맞춰 단일 호출 또는 계층 요약으로 처리합니다.

- **학회**: 발표 개요 → 배경 → 방법론 → 주요 결과 → 한계·향후 과제 → Q&A 정리
- **강연**: 목차형 구조 요약 + 핵심 메시지 + 인상적 인용(타임스탬프)
- **회의**: 안건별 논의 → 결정사항 → 액션아이템(담당/기한)

---

## 4. Knowledge Pack — 자료 통합·조사·보강 모듈

강연자 정보(초록, 이름, 소속, 논문)와 발표자료(PPT 또는 슬라이드 사진)를 함께 제공하면, 이를 토대로 음성을 더 정확히 이해하고 자료 맥락을 조사하여 보강 노트를 만드는 모듈. **두 단계로 나눠 배치합니다 — 용어 주입은 값싸고 효과가 커서 Phase 1, 조사·보강은 Phase 3.**

### 4-1. 자료 수집·추출 (Phase 1)

| 입력 | 처리 |
|---|---|
| 초록·강연자 정보 (텍스트) | 그대로 사용 |
| PPT 파일 | `python-pptx`로 슬라이드별 텍스트·노트 추출 |
| 슬라이드 사진 | OpenAI vision-capable model로 텍스트·수식·그림 설명·레퍼런스 추출 (사진 품질이 낮으면 `검토필요`로 표기) |

추출 결과에서 **용어·고유명사·논문 레퍼런스·수식 기호**를 뽑아 구조화 → 이것이 Knowledge Pack의 뼈대.

### 4-2. 파이프라인 주입 (Phase 1) — 가장 효과 큰 부분

- STT 프롬프트/커스텀 어휘에 용어 전달 → 억양 있는 발표의 전문용어 인식률 대폭 개선
- 교정 계층 용어집에 반영 → "크리스퍼 캐스나인 → CRISPR-Cas9" 같은 교정의 근거 강화
- 강연자 이름·소속·인용 논문 저자명 → 고유명사 오인식 교정

### 4-3. 추가 조사 (Phase 3)

- 슬라이드에서 추출한 논문 레퍼런스를 **Semantic Scholar / arXiv API + 웹 검색**으로 조회 → 초록·핵심 결과 수집
- 강연자의 대표 선행 연구 조사 (발표 배경 이해)
- 조사 결과를 슬라이드별 컨텍스트로 정리 (OpenAI provider의 검색/도구 호출 또는 별도 검색 adapter 활용)

### 4-4. 슬라이드-전사 정렬 + 통합 보강 노트 (Phase 3)

전사 구간을 내용 유사도로 슬라이드에 매칭한 뒤, 슬라이드 단위 통합 노트를 생성:

```markdown
### Slide 7 — Off-target Analysis  [00:23:10 ~ 00:27:45]
🎤 **발표 내용**: 발표자는 GUIDE-seq 결과에서 off-target이 3개 검출되었고, 그중 2개는 유전자 사막(gene desert) 영역이라 영향이 작다고 설명함.
📊 **슬라이드에만 있는 내용**: 표 하단의 검증 조건(read depth ≥ 1000)과 세 번째 off-target 좌표는 슬라이드에 있으나 발화에서는 언급되지 않음.
🔍 **AI 조사 보강**: 이 슬라이드가 인용한 Tsai et al., 2015 (Nat Biotechnol) — GUIDE-seq 원 논문. off-target 검출 민감도 및 발표자가 생략한 방법론적 한계 요약. [DOI 링크]
```

### 4-5. 설계 원칙 (이 모듈의 안전장치)

보강 기능은 강력한 만큼, 아래 원칙을 지키지 않으면 "전사(사실 기록)와 AI 추측이 섞인 신뢰 불가 문서"가 됩니다.

- **출처 라벨 강제**: 모든 문장은 🎤 발화 / 📊 슬라이드 / 🔍 AI 조사 중 하나로 표시. 라벨 없는 서술 금지.
- **보강 = 인용 필수**: 🔍 항목은 출처(논문 링크·URL) 없이 서술 금지 → 환각 차단. 근거를 못 찾으면 "확인 불가"로 표기.
- **전사 본문 불가침**: 보강·조사 내용은 별도 섹션/주석으로만. 전사 교정 diff 검증(§3-③)과 동일한 사상.
- **자료-발화 불일치는 숨기지 않고 드러냄**: "슬라이드엔 있으나 발표에서 언급 안 함", "발표자가 슬라이드와 다르게 말함" 같은 차이는 별도 표기 → 오히려 이 시스템의 가치.

### 4-6. 보강 근거 우선순위 (Phase 1 스캐폴드 반영)

보강은 단편 키워드가 아니라 강한 근거부터 시작합니다.

1. **슬라이드에 적힌 레퍼런스**: 직접 검색해 원 논문 PDF/초록/figure caption을 확인. 같은 레퍼런스가 여러 슬라이드에 반복되면 우선순위 상승.
2. **긴 문장/결론문**: 슬라이드 제목, 설명문, 박스 안 문장을 핵심 anchor로 사용.
3. **figure/table 문맥**: 그래프 축, legend, 조건명, 통계표시를 "무엇을 비교했는가" 관점에서 추출.
4. **고유명사/물질명**: 프로젝트명, 인물명, peptide/polymer/nanoparticle label을 용어집과 검색 후보로 사용.
5. **단편 키워드**: STT 용어집에는 넣되 보강 설명의 중심 근거로 쓰지 않고 `검토필요`로 낮게 둠.

레퍼런스 PDF가 확보되면 기존 PDF figure/table 추출 도구 체인을 사용합니다: PyMuPDF로 페이지 렌더링/crop, pdfplumber로 텍스트와 표 후보 추출, Camelot으로 표 영역을 tight하게 잡습니다. 원 논문 figure/table/caption과 슬라이드 crop이 매칭되면 근거 등급을 최상위로 둡니다.

전사와 발표자료는 순환적으로 보강합니다. 슬라이드 용어는 STT와 교정 프롬프트에 들어가고, 전사 텍스트는 슬라이드 figure/table의 실험 의도와 결론을 해석하는 데 쓰입니다. 다만 최종 노트는 `발표 전사`, `슬라이드 텍스트`, `레퍼런스 PDF`, `추가 조사`, `검토 필요`를 분리해 환각과 출처 혼합을 막습니다.

---

## 5. 프로젝트 구조 (구현 시)

```
stt-conference/
├── pyproject.toml
├── config/
│   ├── profiles/
│   │   ├── seminar.yaml      # 학회: diarization 경량, 용어집 필수, Q&A 템플릿
│   │   ├── lecture.yaml      # 강연: 단일화자, 목차형 요약
│   │   └── meeting.yaml      # 회의: diarization on, 액션아이템
│   └── glossaries/           # 분야별 용어집 (누적 관리)
├── src/stt_pipeline/
│   ├── knowledge_pack.py     # 자료 단서 우선순위화 + 전사/슬라이드 정렬 + PDF 추출 작업 계획
│   ├── llm_provider.py       # OpenAI-first LLM/vision 작업 계획
│   ├── stt_provider.py       # OpenAI STT provider aliases + live adapter + normalized transcript output
│   ├── transcript.py         # 공통 transcript/segment dataclass
│   ├── slide_extract.py      # OCR 텍스트 → 슬라이드 근거 구조화
│   ├── pdf_tools.py          # 기존 PDF Figure/Table 추출 스크립트 호출 계획
│   ├── cli.py                # stt transcribe / stt bakeoff
│   ├── preprocess.py         # ffmpeg 변환, 무음 트리밍
│   ├── stt_providers/        # gpt4o / elevenlabs / assemblyai / mlx(폴백) 어댑터
│   ├── bakeoff.py            # STT API 비교 스크립트 (Phase 1 첫 작업)
│   ├── slide_ocr.py          # PPT/사진 OCR 및 figure/table crop 후보 추출
│   ├── correct.py            # OpenAI 교정 + diff 검증
│   ├── summarize.py          # 프로필별 요약
│   ├── enrich.py             # 슬라이드-전사 정렬 + 보강 노트 (Phase 3)
│   └── report.py             # md/json/srt 출력
└── tests/
```

**용어집 자산화**: 교정 리포트에서 확정된 수정 쌍을 용어집에 자동 누적 → 다음 녹음의 STT 프롬프트·교정에 반영. **쓸수록 정확해지는 구조.**

---

## 6. 비용·성능 추정 (1시간 세미나 기준)

| 단계 | 시간 | 비용 |
|---|---|---|
| 전처리 | ~1분 | 무료 |
| STT (클라우드 API) | 수 분 | ~$0.4 |
| LLM 교정 (~15K 토큰, 청크별) | 수 분 (Batch/비동기: 수십 분) | 선택한 OpenAI 모델 기준 |
| 요약 | ~1분 | ~$0.1 |
| Knowledge Pack 조사 (Phase 3, 자료 있을 때) | 수 분 | ~$0.1~0.3 |
| **합계** | **약 10분 내외** | **회당 1,000원 안팎** |

로컬 대비 처리 시간이 크게 짧고(수 분 vs 수 시간), M2 Air 발열·스로틀링 부담이 없습니다.

---

## 7. 구현 로드맵

### Phase 1 — MVP (CLI, 학회 프로필)
- [x] **STT adapter + bake-off CLI** — `gpt-4o`, `gpt-4o-mini`, `whisper-1`, `diarize` 후보를 같은 녹음으로 비교 가능
- [x] `stt run seminar.wav --profile seminar --pack ./materials/` 기본 흐름 — 텍스트/PPTX/OCR JSON 자료에서 prompt terms 생성 후 transcript.md/transcript.json 출력
- [x] 전처리 옵션 → 클라우드 STT → md/json/srt 출력
- [x] Knowledge Pack **기본**: 텍스트/PPTX/OCR JSON 자료 → 용어 주입 (`--terms-file`과 병합)
- [ ] Knowledge Pack 확장: 원본 슬라이드 사진 OCR, PDF 본문/figure/table 자동 추출 CLI 연결
- [x] OpenAI 교정 계층 **기본**: structured outputs + 선언된 수정만 적용 + 거절 목록 기록
- [x] 기본 요약
- **완료 기준**: `stt run seminar.wav --profile seminar --pack ./materials/` 한 줄로 transcript.md 생성

### Phase 2 — 프로필 완성
- [ ] 회의 프로필: 내장 diarization + 액션아이템 추출
- [ ] 강연 프로필 템플릿
- [ ] 용어집 자동 누적
- [ ] Batch API 전환 (교정 비용 50% 절감)

### Phase 3 — Knowledge Pack 심화 + 편의성
- [ ] 레퍼런스 논문 조사 (Semantic Scholar/arXiv/웹 검색)
- [ ] 슬라이드-전사 정렬 + 통합 보강 노트 (출처 라벨 강제)
- [ ] Gradio 웹 UI: 파일·자료 드롭, 교정/보강 승인·거부 버튼
- [ ] 저신뢰 구간 오디오 클립 링크 (클릭 재생 검수)

### 하지 않기로 한 것 (명시)
- ❌ Whisper 파인튜닝 — 자료 기반 용어 주입 + LLM 교정으로 충분
- ❌ STT 로컬 상시 실행 — M2 Air에서 성능 열세, 폴백으로만 유지
- ❌ 실시간 스트리밍 전사 — 배치 처리가 품질·비용 우위
- ❌ 용도별 별도 STT 모델 — 프로필로 통합

---

## 8. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| LLM이 화자의 원래 표현을 과도하게 다듬음 | diff 검증 + "기록 없는 수정 무효" 규칙 + 롤백 |
| **보강 노트에서 AI 추측이 사실처럼 섞임** | 출처 라벨 강제 + 🔍 항목 인용 필수 + 전사 본문 불가침 (§4-5) |
| 코드스위칭 구간 오인식 | Knowledge Pack 용어 주입 + 저신뢰 구간 집중 교정 + ⚠️ 플래그 |
| 슬라이드 사진 품질 저하 | OpenAI vision-capable model로 1차 추출하되, 불확실 시 "판독 불가" 표기 |
| 긴 녹음에서 청크 경계 문맥 단절 | 청크 간 500토큰 오버랩 + 직전 청크 요약 전달 |
| 클라우드 STT 파일 크기 제한 | 무음 경계 기준 분할 업로드 (문장 중간 절단 방지) |
| API 장애·오프라인 | mlx-whisper 로컬 폴백 유지 |
