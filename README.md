# STT for Conferences, Lectures & Meetings

학회 세미나(주 용도), 강연, 회의 녹음(Zoom H1e)을 대상으로:

1. 여러 억양의 **영어/한국어 음성 → 전사** (클라우드 STT 기본, mlx-whisper 폴백)
2. **앞뒤 문맥 기반 오인식 교정** (OpenAI API + Knowledge Pack 용어집)
3. **교정 내역을 별도 표로 정리** (환각 방지 diff 검증 포함)
4. 용도별 프로필(학회/강연/회의)에 맞는 **요약 정리**

까지 한 번에 처리하는 파이프라인 프로젝트입니다.

**용도별 STT 모델을 따로 만들지 않고, 하나의 통합 파이프라인 + 설정 프로필**로 구성합니다 — 근거와 전체 설계는 [PLAN.md](./PLAN.md) 참고.

## 상태

- [x] 전체 설계 계획 수립 → [PLAN.md](./PLAN.md)
- [x] Phase 1 Knowledge Pack 우선순위 스캐폴드 → `src/stt_pipeline/knowledge_pack.py`
- [x] OCR 텍스트/레퍼런스 PDF 추출 어댑터 경계 → `src/stt_pipeline/slide_extract.py`, `src/stt_pipeline/pdf_tools.py`
- [x] OpenAI STT adapter + provider bakeoff CLI → `src/stt_pipeline/stt_provider.py`, `src/stt_pipeline/cli.py`
- [x] 로컬 `mlx-whisper` fallback adapter → `src/stt_pipeline/local_whisper.py`
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
- [x] glossary 후보와 낮은 품질 reference metadata를 위한 `review_queue.json` 검수 경로
- [x] Phase 1: MVP (CLI, 학회 프로필)
- [ ] Phase 2: 회의/강연 프로필, 용어집 자동 누적
- [ ] Phase 3: 웹 UI, 검수 도구

## CLI Preview

초기 1회 설치:

```bash
python3 -m pip install -e .
```

API 키 설정:

```bash
export OPENAI_API_KEY="..."
```

교정 옵션까지 쓰려면 OpenAI 텍스트 모델도 환경변수로 지정:

```bash
export OPENAI_MODEL="your-openai-text-model"
```

자료 없이 전사:

```bash
stt transcribe sample.wav --profile seminar --provider gpt-4o --output out/seminar
```

보강자료 폴더를 같이 넣어 한 번에 전사:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --output out/seminar
```

이후에는 녹음파일, 보강자료 폴더, `OPENAI_API_KEY`만 준비하면 됩니다. `--pack`은 현재 `.txt`, `.md`, `.pptx`, 슬라이드 OCR 결과 `.json`을 읽어 `prompt_terms.txt`와 `knowledge_pack.json`을 출력합니다. 슬라이드 사진(`.jpg`, `.jpeg`, `.png`, `.heic`)은 `--ocr-images`를 같이 주면 OpenAI vision으로 OCR합니다. PDF는 기본으로 STT prompt terms에 섞지 않고 `pdf_sources`와 warning에 남깁니다.

슬라이드 사진 OCR 포함:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --ocr-images --output out/seminar
```

긴 녹음 파일 분할 전사:

```bash
stt run long-seminar.wav --profile seminar --provider gpt-4o --chunk-audio --chunk-seconds 600 --output out/seminar
```

`--chunk-audio`는 ffmpeg segment 기능으로 `audio_chunks/chunk_*.wav`를 만든 뒤 각 chunk를 전사하고, 타임스탬프를 chunk offset만큼 보정해 하나의 `transcript.md/json/srt`로 합칩니다. OpenAI 파일 업로드 제한에 걸릴 수 있는 긴 Zoom H1e WAV에는 이 옵션을 켜는 것이 안전합니다.

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

`--write-review-queue`는 적용된 교정쌍을 glossary 후보로, `metadata_quality_score`가 낮거나 `review_flags`가 있는 레퍼런스를 reference metadata 검수 항목으로 `review_queue.json`에 남깁니다. 사람이 각 항목의 `status`를 `accepted` 또는 `rejected`로 바꾼 뒤, accepted glossary 후보만 저장할 수 있습니다.

```bash
stt run sample.wav --profile seminar --provider gpt-4o --correct --save-glossary ./glossary.tsv --review-decisions-file out/seminar/review_queue.json --output out/seminar-reviewed
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
- `review_queue.json` (`--write-review-queue`)
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

Whisper와 최신 OpenAI STT 후보 비교:

```bash
stt bakeoff sample.wav --profile seminar --providers whisper-1,gpt-4o,gpt-4o-mini,mlx-whisper --output out/bakeoff
```

로컬 fallback만 실행:

```bash
stt transcribe sample.wav --profile seminar --provider mlx-whisper --output out/local
```

`mlx-whisper`는 기본 경로가 아니라 오프라인/비상 fallback입니다. 실행 환경에 `mlx_whisper` CLI가 설치되어 있어야 하며, 필요하면 `MLX_WHISPER_COMMAND`와 `MLX_WHISPER_MODEL`로 command/model을 바꿀 수 있습니다.

## Knowledge Pack 원칙

보강 근거 우선순위는 `레퍼런스 PDF > 슬라이드 문장 > figure/table 문맥 > 고유명사 > 단편 키워드`입니다. 같은 레퍼런스가 여러 슬라이드에 반복되면 중요도를 올리고, 원 논문 PDF를 찾은 뒤 figure/table caption과 crop을 추출하는 작업을 먼저 계획합니다.

전사와 발표자료는 상호보완적으로 사용합니다. 슬라이드 용어는 STT/교정 용어집으로 들어가고, 전사 문장은 슬라이드 figure/table의 의도와 결론을 해석하는 데 사용하되, 최종 노트는 `발표 전사`, `슬라이드 텍스트`, `레퍼런스 PDF`, `추가 조사`, `검토 필요` 섹션으로 분리합니다.
