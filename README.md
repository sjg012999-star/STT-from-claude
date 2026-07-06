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
- [ ] Phase 1: MVP (CLI, 학회 프로필)
- [ ] Phase 2: 회의/강연 프로필, 용어집 자동 누적
- [ ] Phase 3: 웹 UI, 검수 도구

## Knowledge Pack 원칙

보강 근거 우선순위는 `레퍼런스 PDF > 슬라이드 문장 > figure/table 문맥 > 고유명사 > 단편 키워드`입니다. 같은 레퍼런스가 여러 슬라이드에 반복되면 중요도를 올리고, 원 논문 PDF를 찾은 뒤 figure/table caption과 crop을 추출하는 작업을 먼저 계획합니다.

전사와 발표자료는 상호보완적으로 사용합니다. 슬라이드 용어는 STT/교정 용어집으로 들어가고, 전사 문장은 슬라이드 figure/table의 의도와 결론을 해석하는 데 사용하되, 최종 노트는 `발표 전사`, `슬라이드 텍스트`, `레퍼런스 PDF`, `추가 조사`, `검토 필요` 섹션으로 분리합니다.
