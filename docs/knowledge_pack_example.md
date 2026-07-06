# Knowledge Pack 추출 예시 — 실제 학회 슬라이드 1장

> 이 문서는 `enrich` 모듈의 **동작 스펙 겸 테스트 픽스처**입니다.
> 입력: 학회에서 촬영한 발표 슬라이드 사진 1장 (궤양성 대장염 단일세포 연구).
> Claude 비전이 슬라이드를 읽어 아래처럼 **3개 레이어로 분류**하고, 전사(🎤)와는 절대 섞지 않습니다.

---

## 0. 슬라이드에서 원시 추출된 것 (OCR/비전)

- **제목**: Cellular and Intercellular Rewiring of the Human Colon in Ulcerative Colitis
- **부제**: scRNA-seq atlas · 366,650 cells · 18 UC patients + 12 healthy controls · 51 cell subsets | Smillie et al., Cell 2019
- **본문 블록 1 (NOVEL CELL TYPES)**: BEST4+ enterocytes & microfold-like cells — 51개 세포 subset, BEST4+ enterocyte(luminal pH sensing)와 microfold-like cell이 활동성 UC에서 확장
- **본문 블록 2 (INFLAMMATORY FIBROBLASTS)**: IL13RA2+IL11+ fibroblasts linked to anti-TNF resistance — anti-TNF 치료 무반응과 연관된 stromal fibroblast 집단
- **도식**: Healthy vs Ulcerative colitis 세포 상호작용 허브 (Follicular B, CD8+ T, Tregs, CD8+ IL17+ T, Inflammatory monocytes, M-like cells, Inflammatory fibroblasts)
- **현미경 이미지 마커**: DAPI, BEST4, KRT19, EPCAM, RSPO3, GREM2, VIM / IL13RA2, PLAU, VIM
- **막대그래프**: IL13RA2+ VIM+ cells/field, Healthy vs Inflamed, *** (유의)
- **인용**: Smillie C.S. et al. — Cell 178(3):714–730, 2019

---

## 1. 🔤 STT/교정에 주입할 것 (용어·고유명사) — Phase 1

억양 있는 발표에서 오인식되기 쉬운 항목만 뽑아 STT 프롬프트와 교정 용어집에 넣습니다.
이게 **전사 정확도를 가장 크게 올리는 부분**입니다.

```
유전자/마커: BEST4, IL13RA2, IL11, KRT19, EPCAM, RSPO3, GREM2, VIM, PLAU, DAPI
세포/개념: enterocyte, microfold-like cell (M cell), inflammatory fibroblast,
          Treg, follicular B cell, monocyte, scRNA-seq
치료/임상: anti-TNF, ulcerative colitis (UC)
고유명사: Smillie (저자명), Cell (저널명)
숫자: 366,650 cells / 18 patients / 12 controls / 51 subsets / Cell 178(3):714–730
```
→ 예: 발표자가 "아이엘 써틴 알에이 투"라 발음 → 교정 계층이 `IL13RA2`로 복원 (근거: 이 용어집)

---

## 2. 📊 슬라이드 전용 사실 (발화 안 해도 기록) — Phase 1

발표자가 말로 다루지 않았더라도 슬라이드에 있으면 노트에 남깁니다. 전사와는 별도 레이어.

- 데이터 규모: 366,650 세포 / UC 환자 18명 + 정상 12명 / 51개 subset
- 핵심 마커 조합 IL13RA2+ VIM+ 세포가 염증 조직에서 유의하게(***) 증가
- 상호작용 허브 도식: inflammatory fibroblast ↔ monocyte ↔ T cell ↔ epithelium

---

## 3. 🔍 추가 조사·보강 대상 (보고서·공부용) — Phase 3

**전사와 분리되고, 반드시 출처가 있어야 하며, 못 찾으면 "확인 불가"로 남깁니다.**

| 보강 항목 | 출처 상태 | 처리 |
|---|---|---|
| 인용 원논문 (Smillie et al., Cell 2019) 초록·주요 결론 | 슬라이드에 서지정보 인쇄됨 → 확정 | Semantic Scholar/PubMed로 DOI·초록 fetch |
| BEST4+ enterocyte 후속 연구 (2019 이후 진전) | **미확인 (라이브 조회 필요)** | 검색 성공 시 인용, 실패 시 "확인 불가" 표기 |
| IL13RA2+IL11+ fibroblast ↔ anti-TNF 저항 기전 | **미확인 (라이브 조회 필요)** | 위와 동일 |
| 발표자 소속·선행 연구 (강연자 정보 함께 주면) | 자료 제공 시 | 프로필 조회 |

> ⚠️ **이번 시뮬레이션에서는 웹 검색이 세션 한도에 걸려 라이브 조회를 못 했습니다.**
> 설계 원칙대로, 확인 못 한 항목은 위 표에서 **"미확인"으로만 표기하고 내용을 지어내지 않았습니다.**
> 실제 빌드에서는 이 단계에서 Semantic Scholar/arXiv/웹 검색 API로 근거를 붙입니다.

---

## 4. 최종 병합 노트 형태 (이 슬라이드 기준)

```markdown
### Slide — Cellular & Intercellular Rewiring in UC   [발표 타임스탬프 자동 매칭]

🎤 **발표 발화**: (STT 전사에서 이 슬라이드 구간의 실제 발언 — 별도 레이어)

📊 **슬라이드 사실**:
- scRNA-seq 아틀라스: 366,650 세포, UC 18명 + 정상 12명, 51개 subset
- IL13RA2+ VIM+ 세포가 염증 조직에서 유의 증가 (***)
- 상호작용 허브: inflammatory fibroblast ↔ monocyte ↔ T cell ↔ epithelium

🔍 **AI 조사 보강** (출처 필수):
- 원논문: Smillie C.S. et al., Cell 178(3):714–730, 2019 [슬라이드 인용 → DOI 조회]
- BEST4+ enterocyte / IL13RA2+IL11+ fibroblast 후속 문헌: 확인 불가 (라이브 조회 미수행)
```

핵심: **🎤(사실 기록)과 🔍(AI 해설)은 시각적으로도 데이터 구조에서도 절대 섞이지 않습니다.**
보고서/공부에는 📊+🔍를 쓰고, "발표자가 실제 뭐라 했는지"가 필요할 땐 🎤만 보면 됩니다.
