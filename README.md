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
- [x] `stt run ... --pack ./materials` 기본 실행 흐름 → 텍스트/PPTX/OCR JSON 자료에서 STT prompt terms 생성
- [x] 전처리 옵션, SRT 출력, OpenAI 교정 옵션, 기본 요약 출력
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

이후에는 녹음파일, 보강자료 폴더, `OPENAI_API_KEY`만 준비하면 됩니다. `--pack`은 현재 `.txt`, `.md`, `.pptx`, 슬라이드 OCR 결과 `.json`을 읽어 `prompt_terms.txt`와 `knowledge_pack.json`을 출력합니다. 원본 슬라이드 사진과 PDF 직접 OCR/파싱은 아직 자동 실행하지 않으며, 해당 파일이 있으면 출력 JSON의 `warnings`에 남깁니다.

전처리, 교정, 요약까지 포함:

```bash
stt run sample.wav --profile seminar --provider gpt-4o --pack ./materials --preprocess --correct --summarize --output out/seminar
```

`--preprocess`는 `ffmpeg`로 16kHz mono/loudness-normalized WAV를 만든 뒤 STT에 넘깁니다. `--correct`는 OpenAI Responses API에 구조화된 교정 JSON을 요청하고, 실제 세그먼트에 존재하는 원문만 바꿉니다. `--summarize`는 전사/교정 결과를 분리한 기본 Markdown 요약을 만듭니다.

직접 만든 용어 힌트 파일만 추가:

```bash
stt transcribe sample.wav --profile seminar --provider gpt-4o --terms-file terms.txt --output out/seminar
```

주요 출력:

- `transcript.md` / `transcript.json` / `transcript.srt`
- `corrected_transcript.md` / `corrected_transcript.json` / `corrected_transcript.srt` (`--correct`)
- `corrections.json` (`--correct`)
- `summary.md` (`--summarize`)
- `prompt_terms.txt`, `knowledge_pack.json`, `run_manifest.json`

Whisper와 최신 OpenAI STT 후보 비교:

```bash
stt bakeoff sample.wav --profile seminar --providers whisper-1,gpt-4o,gpt-4o-mini --output out/bakeoff
```

## Knowledge Pack 원칙

보강 근거 우선순위는 `레퍼런스 PDF > 슬라이드 문장 > figure/table 문맥 > 고유명사 > 단편 키워드`입니다. 같은 레퍼런스가 여러 슬라이드에 반복되면 중요도를 올리고, 원 논문 PDF를 찾은 뒤 figure/table caption과 crop을 추출하는 작업을 먼저 계획합니다.

전사와 발표자료는 상호보완적으로 사용합니다. 슬라이드 용어는 STT/교정 용어집으로 들어가고, 전사 문장은 슬라이드 figure/table의 의도와 결론을 해석하는 데 사용하되, 최종 노트는 `발표 전사`, `슬라이드 텍스트`, `레퍼런스 PDF`, `추가 조사`, `검토 필요` 섹션으로 분리합니다.
