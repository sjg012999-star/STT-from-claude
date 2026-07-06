"""⓪ Knowledge Pack (Phase 1 기본) — 자료 추출 → 용어 주입.

입력 자료 디렉토리에서:
  - PPT(.pptx)   → python-pptx 로 슬라이드 텍스트·노트 추출
  - 슬라이드 사진(.png/.jpg) → Claude 비전(llm.describe_slide_image); 키 없으면 스킵/목
  - 용어집/텍스트(.yaml/.txt) → 용어·alias 로 병합

산출: KnowledgePack(glossary_terms 🔤, aliases, slide_facts[📊/🔍 골격]).
3레이어(🔤 STT주입 / 📊 슬라이드사실 / 🔍 조사대상)는 병합하지 않는다
(docs/knowledge_pack_example.md, 불변원칙 1). 🔍 는 Phase 3 이므로 골격만.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .llm.base import LLMClient
from .models import KnowledgePack, SlideFact

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def build_knowledge_pack(
    pack_dir: str | Path | None,
    llm: LLMClient | None = None,
) -> KnowledgePack:
    """자료 디렉토리에서 Knowledge Pack 을 만든다. pack_dir 없으면 빈 팩."""
    pack = KnowledgePack()
    if not pack_dir:
        return pack
    pack_dir = Path(pack_dir)
    if not pack_dir.exists():
        raise FileNotFoundError(f"자료 디렉토리가 없습니다: {pack_dir}")

    terms: list[str] = []
    for path in sorted(pack_dir.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext == ".pptx":
            fact = _extract_pptx(path)
            pack.slide_facts.append(fact)
            terms.extend(fact.glossary_terms)
        elif ext in _IMAGE_EXTS:
            fact = _extract_image(path, llm)
            pack.slide_facts.append(fact)
            terms.extend(fact.glossary_terms)
        elif ext in {".yaml", ".yml"}:
            _merge_glossary_file(path, terms, pack.aliases)
        elif ext == ".txt":
            terms.extend(_terms_from_text(path.read_text(encoding="utf-8")))

    # 중복 제거(순서 유지) + alias 의 정식표기도 용어에 포함.
    for v in pack.aliases.values():
        terms.append(v)
    pack.glossary_terms = _dedup(terms)
    return pack


def _extract_pptx(path: Path) -> SlideFact:
    """python-pptx 로 텍스트 추출. 미설치면 note 남기고 스킵."""
    try:
        from pptx import Presentation  # lazy import
    except ImportError:
        return SlideFact(
            source=path.name,
            raw_extract="",
            slide_only_facts=[
                "python-pptx 미설치 → PPT 추출 스킵. `pip install 'stt-pipeline[pack]'`"
            ],
        )
    prs = Presentation(str(path))
    texts: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = "".join(run.text for run in para.runs).strip()
                    if line:
                        texts.append(line)
    raw = "\n".join(texts)
    return SlideFact(
        source=path.name,
        raw_extract=raw,
        glossary_terms=_terms_from_text(raw),
        slide_only_facts=texts,  # 📊 슬라이드 전용 사실(발화 여부와 무관)
    )


def _extract_image(path: Path, llm: LLMClient | None) -> SlideFact:
    """슬라이드 사진 → 비전 추출. llm 없거나 미구현이면 스킵."""
    if llm is None:
        return SlideFact(
            source=path.name,
            slide_only_facts=["비전 LLM 미제공 → 슬라이드 사진 추출 스킵 (mock/키없음)"],
        )
    try:
        out = llm.describe_slide_image(str(path))
    except NotImplementedError as e:
        return SlideFact(source=path.name, slide_only_facts=[f"비전 추출 미구현: {e}"])
    return SlideFact(
        source=path.name,
        raw_extract=str(out.get("raw_extract", "")),
        glossary_terms=list(out.get("glossary_terms", []) or []),
        slide_only_facts=list(out.get("slide_only_facts", []) or []),
    )


def _merge_glossary_file(path: Path, terms: list[str], aliases: dict[str, str]) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for t in data.get("terms", []) or []:
        terms.append(str(t))
    for k, v in (data.get("aliases", {}) or {}).items():
        aliases[str(k)] = str(v)


def _terms_from_text(text: str) -> list[str]:
    """추출 텍스트에서 오인식되기 쉬운 용어 후보를 뽑는다(휴리스틱).

    - 대문자/숫자/하이픈이 섞인 토큰(유전자·마커·모델명): BEST4, IL13RA2, CRISPR-Cas9
    - CamelCase / 약어
    정밀 추출은 아니며, Phase 1 의 용어 주입 시드로 충분.
    """
    candidates: list[str] = []
    # 영문+숫자+하이픈 토큰
    for m in re.findall(r"[A-Za-z][A-Za-z0-9\-]*[0-9][A-Za-z0-9\-]*", text):
        candidates.append(m)
    # 하이픈 포함 영문 (CRISPR-Cas9, scRNA-seq)
    for m in re.findall(r"[A-Za-z]+\-[A-Za-z0-9]+", text):
        candidates.append(m)
    # 전부 대문자 약어 (2글자 이상)
    for m in re.findall(r"\b[A-Z]{2,}\b", text):
        candidates.append(m)
    return _dedup(candidates)


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        x = x.strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out
