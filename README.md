# STT for Conferences, Lectures & Meetings

학회 세미나(주 용도), 강연, 회의 녹음(Zoom H1e)을 대상으로:

1. 여러 억양의 **영어/한국어 음성 → 전사** (OpenAI/Gemini 클라우드 API)
2. **앞뒤 문맥 기반 오인식 교정** (Codex ChatGPT 로그인/OAuth + Knowledge Pack 용어집)
3. **교정 내역을 별도 표로 정리** (환각 방지 diff 검증 포함)
4. 용도별 프로필(학회/강연/회의)에 맞는 **요약 정리**

까지 한 번에 처리하는 파이프라인 프로젝트입니다.

**용도별 STT 모델을 따로 만들지 않고, 하나의 통합 파이프라인 + 설정 프로필**로 구성합니다 — 근거와 전체 설계는 [PLAN.md](./PLAN.md) 참고.

## 상태

- [x] 전체 설계 계획 수립 → [PLAN.md](./PLAN.md)
- [x] Phase 1 Knowledge Pack 우선순위 스캐폴드 → `src/stt_pipeline/knowledge_pack.py`
- [x] OCR 텍스트/레퍼런스 PDF 추출 어댑터 경계 → `src/stt_pipeline/slide_extract.py`, `src/stt_pipeline/pdf_tools.py`
- [x] OpenAI STT adapter + provider bakeoff CLI → `src/stt_pipeline/stt_provider.py`, `src/stt_pipeline/cli.py`
- [x] 선택 가능한 OpenAI/Gemini STT provider와 동일 녹음 bake-off
- [x] `stt run ... --pack ./materials` 기본 실행 흐름 → 텍스트/PPTX/OCR JSON 자료에서 STT prompt terms 생성
- [x] 전처리 옵션, 긴 녹음 chunking 옵션, SRT 출력, OpenAI 교정 옵션, 기본 요약 출력
- [x] OpenAI vision 기반 슬라이드 사진 OCR 옵션
- [x] 레퍼런스 DOI/검색 URL 계획 출력 옵션
- [x] Crossref/OpenAlex/Semantic Scholar 기반 레퍼런스 조회, publisher PDF fallback, open PDF cache 옵션
- [x] 명시적 PDF figure/table 추출 실행 옵션
- [x] 세미나/강연/회의 프로필별 기본 요약 섹션
- [x] 적용된 교정쌍을 TSV glossary로 저장/재사용
- [x] source label 기반 `notes.md` 보강 노트 출력
- [x] OpenAI LLM 기반 source-labeled `rich_summary.md` 출력 옵션
- [x] 명시적 추가 조사 파일(`--additional-research-file`)을 source-labeled evidence로 반영
- [x] 명시적 web/reference search endpoint adapter (`--web-research-query`, 기본 비활성)
- [x] glossary 후보와 낮은 품질 reference metadata를 위한 `review_queue.json` + 정적 HTML 검수 경로
- [x] Phase 1: MVP (CLI, 학회 프로필)
- [ ] Phase 2: 회의/강연 프로필, 용어집 자동 누적
- [ ] Phase 3: 웹 UI, 검수 도구

## CLI Preview

### 기본 비용 정책

- Platform API 키는 기본적으로 `gpt-4o-transcribe` 전사에만 사용합니다.
- 전사 후 문맥 교정, 요약, 슬라이드 해석, 레퍼런스 통합은 로그인된 Codex 앱/CLI의 ChatGPT 구독 접근으로 처리합니다.
- ChatGPT 로그인 사용량은 구독 플랜의 사용량 또는 크레딧을 소비하지만 OpenAI Platform API 종량제 청구에는 포함되지 않습니다.
- `--correct`, `--llm-summarize`, `--ocr-images`는 기존의 **유료 Platform API 옵션**이므로 명시적으로 비용을 허용한 경우에만 사용합니다.

저비용 기본 실행은 전사까지만 CLI에서 수행합니다:

```bash
stt transcribe sample.wav --profile seminar --provider gpt-4o --output out/seminar
```

그다음 Codex에서 `transcript.json`과 선택적 보강자료를 읽어 별도 버전의 교정본과 변경 내역을 생성합니다. 원본 전사는 덮어쓰지 않습니다.

초기 1회 설치:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install '.[gemini,pdf]'
```

API 키 설정은 환경변수를 우선 사용합니다:

```bash
export OPENAI_API_KEY="..."
```

macOS에서는 환경변수가 없을 때 로그인 Keychain의 `stt-conference-openai`
서비스 항목을 자동으로 읽습니다. 이 Mac에는 해당 항목이 이미 설정되어 있으므로
OpenAI 전사만 사용할 때는 키를 다시 입력하거나 `export`할 필요가 없습니다.

Gemini 전사를 비교할 때만 별도 Gemini API 키를 설정합니다:

```bash
export GEMINI_API_KEY="..."
export GEMINI_AUDIO_MODEL="gemini-3.5-flash"  # optional default
```

OpenAI가 기본 provider이며 Gemini는 명시적으로 `--provider gemini-audio`를 선택했을 때만 호출됩니다.

유료 Responses API 교정을 명시적으로 사용할 때만 OpenAI 텍스트 모델을 지정합니다:

```bash
export OPENAI_MODEL="your-openai-text-model"
```

기본 흐름에서는 이 환경변수와 `--correct`가 필요하지 않습니다.

자료 없이 전사:

```bash
stt transcribe sample.wav --profile seminar --provider gpt-4o --output out/seminar
```

Gemini Audio Understanding으로 동일 파일 전사:

```bash
stt transcribe sample.wav --profile seminar --provider gemini-audio --output out/gemini
```

Gemini는 전체 녹음 문맥을 유지하기 위해 Files API로 파일을 업로드하고 처리 후 원격 파일을 삭제합니다. `gemini-audio`에는 `--chunk-audio`를 함께 사용하지 않습니다.

보강자료 폴더를 같이 넣어 한 번에 전사:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --output out/seminar
```

이후에는 녹음파일과 선택적 보강자료 폴더만 준비하면 됩니다. 다른 컴퓨터에서는 `OPENAI_API_KEY` 환경변수 또는 같은 이름의 Keychain 항목도 필요합니다. `--pack`은 현재 `.txt`, `.md`, `.pptx`, 슬라이드 OCR 결과 `.json`을 읽어 `prompt_terms.txt`와 `knowledge_pack.json`을 출력합니다. 슬라이드 사진(`.jpg`, `.jpeg`, `.png`, `.heic`)은 `--ocr-images`를 같이 주면 OpenAI vision으로 OCR합니다. PDF는 기본으로 STT prompt terms에 섞지 않고 `pdf_sources`와 warning에 남깁니다.

슬라이드 사진 OCR 포함:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --ocr-images --output out/seminar
```

긴 녹음 파일 분할 전사:

```bash
stt run long-seminar.wav --profile seminar --provider gpt-4o --chunk-audio --chunk-seconds 600 --output out/seminar
```

`--chunk-audio`는 ffmpeg segment 기능으로 `audio_chunks/chunk_*.wav`를 만든 뒤 각 chunk를 전사하고, 타임스탬프를 chunk offset만큼 보정해 하나의 `transcript.md/json/srt`로 합칩니다. OpenAI 파일 업로드 제한에 걸릴 수 있는 긴 Zoom H1e WAV를 `gpt-4o`, `gpt-4o-mini`, `whisper-1`로 처리할 때 사용합니다.

`diarize` provider에는 `--chunk-audio`를 사용하지 마십시오. 외부에서 나눈 각 chunk마다 화자 ID가 새로 매겨져 동일 화자가 서로 다른 사람으로 합쳐질 수 있으므로 CLI가 이 조합을 거부합니다. 회의 화자분리는 전체 파일을 전달하고 OpenAI의 `chunking_strategy=auto`를 사용합니다:

```bash
stt run meeting.wav --profile meeting --provider diarize --output out/meeting
```

PDF figure/table 추출 도구 실행:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --extract-pdfs --pdf-extractor-script /path/to/extract-figures-tables.py --output out/seminar
```

`--extract-pdfs`는 명시적으로 켰을 때만 실행됩니다. 현재는 PDF에서 STT 용어를 직접 뽑지 않고, Knowledge Pack의 레퍼런스 기반 `pdf_extraction_jobs` 또는 PDF 파일명 기반 fallback job을 만들어 `pdf_extraction_jobs.json`에 실행 명령과 결과 경로를 남깁니다.

레퍼런스 검색 계획 출력:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --plan-reference-search --output out/seminar
```

`--plan-reference-search`는 네트워크 다운로드를 실행하지 않고, 슬라이드 레퍼런스에서 DOI와 Crossref/OpenAlex/DOI URL 후보를 만들어 `reference_lookup_jobs.json`에 남깁니다. DOI가 있으면 `planned`, DOI가 없으면 `needs_lookup`으로 표시합니다.

레퍼런스 조회 및 open PDF cache:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --lookup-references --output out/seminar
```

`--lookup-references`는 실제 네트워크 조회를 수행합니다. 현재는 Crossref를 먼저 보고, PDF가 없거나 조회가 실패하면 OpenAlex와 Semantic Scholar 후보까지 확인합니다. 그래도 PDF가 없으면 DOI 기반 publisher fallback URL(MDPI, PLOS, Frontiers, Nature/Springer, Wiley, ACS, Taylor & Francis 일부)을 시도합니다. open PDF 링크가 있으면 `reference_cache/*.pdf`로 저장한 뒤 `reference_lookup_results.json`에 `metadata_source`, `metadata_quality_score`, `review_flags`, `publisher_pdf_urls`와 함께 남깁니다. `--lookup-references --extract-pdfs --pdf-extractor-script ...`를 같이 쓰면 cache된 PDF가 기존 figure/table 추출 입력으로 바로 연결됩니다.

명시적 추가 조사 파일 포함:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --additional-research-file ./research/open-web-notes.md --enrich-notes --llm-summarize --output out/seminar
```

`--additional-research-file`은 직접 조사한 웹 검색 결과, 논문 후보, 강연자 정보, 검증 메모를 `.md`, `.txt`, `.json` 파일로 넣는 명시적 입력입니다. pipeline이 자체적으로 broad web search를 기본 실행하지는 않습니다. 입력 파일은 `additional_research.json`에 보존되고, `notes.md`와 `rich_summary.md`의 `additional_research` 근거로만 사용됩니다.

명시적 web/reference search endpoint 사용:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --web-research-query "InTesTiny RGD nanoparticle" --web-research-endpoint "https://your-search-endpoint.example/api" --enrich-notes --llm-summarize --output out/seminar
```

`--web-research-query`는 `--web-research-endpoint`가 함께 있을 때만 실행됩니다. endpoint는 `items`, `results`, `organic`, 또는 Bing-style `webPages.value` JSON 배열을 반환하는 검색 API/사내 도구/로컬 프록시를 가정합니다. 결과는 `web_research_results.json`에 저장되고 `additional_research.json`에도 합쳐집니다.

전처리, 교정, 요약까지 포함:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --ocr-images --preprocess --chunk-audio --correct --summarize --llm-summarize --lookup-references --enrich-notes --output out/seminar
```

`--preprocess`는 `ffmpeg`로 16kHz mono/loudness-normalized WAV를 만든 뒤 STT에 넘깁니다. `--correct`는 OpenAI Responses API에 구조화된 교정 JSON을 요청하고, 실제 세그먼트에 존재하는 원문만 바꿉니다. `--summarize`는 전사/교정 결과를 분리한 기본 Markdown 요약을 만듭니다.
`--llm-summarize`는 OpenAI Responses API로 source label이 있는 `rich_summary.md`를 추가 생성합니다. source label이 없거나 허용되지 않은 label이 오면 실패시켜 전사/슬라이드/PDF/추가조사 근거가 섞이지 않게 합니다.
요약은 프로필별로 기본 섹션이 다릅니다: 세미나는 talk flow, 강연은 outline/key messages, 회의는 decisions/action items/needs review를 우선 만듭니다.

긴 녹음은 교정 요청을 세그먼트 단위로 나눌 수 있습니다:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --correct --correction-chunk-size 40 --correction-overlap 3 --output out/seminar
```

청크 정보는 `corrections.json`과 `run_manifest.json`에 남습니다.

교정 결과를 다음 실행 용어집으로 저장:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --correct --save-glossary ./glossary.tsv --output out/seminar
```

저장된 `glossary.tsv`는 그대로 `--terms-file ./glossary.tsv`로 다시 넣을 수 있습니다. 이때 STT prompt에는 `corrected` 컬럼의 용어만 들어갑니다.

검수 큐 생성:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --correct --lookup-references --write-review-queue --output out/seminar
```

`--write-review-queue`는 적용된 교정쌍을 glossary 후보로, `metadata_quality_score`가 낮거나 `review_flags`가 있는 레퍼런스를 reference metadata 검수 항목으로 `review_queue.json`에 남깁니다. 동시에 `review_queue.html`을 만들므로 JSON을 직접 편집할 필요가 없습니다. HTML에서 검색·필터·항목별 또는 일괄 승인/거절을 한 뒤 `Download decisions`를 누르면 기존 파이프라인이 읽을 수 있는 `review_decisions.json`이 내려받아집니다. 정적 파일이라 별도 서버나 추가 패키지가 필요하지 않습니다.

기존 검수 큐로 HTML을 다시 생성:

```bash
stt review-ui out/seminar/review_queue.json --output out/seminar/review_queue.html
open out/seminar/review_queue.html
```

다운로드한 결정 파일을 적용해 승인된 glossary 후보만 저장:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --correct --save-glossary ./glossary.tsv --review-decisions-file ~/Downloads/review_decisions.json --output out/seminar-reviewed
```

직접 만든 용어 힌트 파일만 추가:

```bash
stt transcribe sample.wav --profile seminar --provider gpt-4o --terms-file terms.txt --output out/seminar
```

주요 출력:

- `transcript.md` / `transcript.json` / `transcript.srt`
- `corrected_transcript.md` / `corrected_transcript.json` / `corrected_transcript.srt` (`--correct`)
- `corrections.json` (`--correct`)
- `glossary.tsv` 또는 지정 경로 (`--save-glossary`)
- `review_queue.json` / `review_queue.html` (`--write-review-queue`)
- `summary.md` (`--summarize`)
- `rich_summary.md` (`--llm-summarize`)
- `notes.md` (`--enrich-notes`)
- `prompt_terms.txt`, `knowledge_pack.json`, `run_manifest.json`
- `audio_chunks/chunk_*.wav` (`--chunk-audio`)
- `reference_lookup_jobs.json` (`--plan-reference-search`)
- `reference_lookup_results.json`, `reference_cache/*.pdf` (`--lookup-references`)
- `additional_research.json` (`--additional-research-file`)
- `web_research_results.json` (`--web-research-query`)
- `pdf_extraction_jobs.json`, `pdf_extract/` (`--extract-pdfs`)

OpenAI와 Gemini STT 후보 비교:

```bash
stt bakeoff sample.wav --profile seminar --providers whisper-1,gpt-4o,gpt-4o-mini,gemini-audio --output out/bakeoff
```

Gemini를 포함한 비교에는 `GEMINI_API_KEY`가 필요하고, OpenAI 모델을 포함하면 `OPENAI_API_KEY`도 필요합니다. 같은 녹음과 Knowledge Pack으로 공급자별 `*.json`과 `bakeoff_report.md`를 생성합니다. 로컬 모델은 설치하지 않으며 모든 STT provider는 클라우드 API를 사용합니다.

## Knowledge Pack 원칙

보강 근거 우선순위는 `레퍼런스 PDF > 슬라이드 문장 > figure/table 문맥 > 고유명사 > 단편 키워드`입니다. 같은 레퍼런스가 여러 슬라이드에 반복되면 중요도를 올리고, 원 논문 PDF를 찾은 뒤 figure/table caption과 crop을 추출하는 작업을 먼저 계획합니다.

전사와 발표자료는 상호보완적으로 사용합니다. 슬라이드 용어는 STT/교정 용어집으로 들어가고, 전사 문장은 슬라이드 figure/table의 의도와 결론을 해석하는 데 사용하되, 최종 노트는 `발표 전사`, `슬라이드 텍스트`, `레퍼런스 PDF`, `추가 조사`, `검토 필요` 섹션으로 분리합니다.
