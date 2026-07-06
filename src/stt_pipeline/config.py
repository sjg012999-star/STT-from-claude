"""프로필·용어집 로딩.

프로필은 config/profiles/<name>.yaml, 용어집은 config/glossaries/<name>.yaml.
저장소 루트를 기준으로 config/ 를 찾되, 환경변수 STT_CONFIG_DIR 로 override 가능.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def config_dir() -> Path:
    env = os.environ.get("STT_CONFIG_DIR")
    if env:
        return Path(env)
    # src/stt_pipeline/config.py -> 저장소 루트/config
    return Path(__file__).resolve().parents[2] / "config"


def load_profile(name: str) -> dict[str, Any]:
    """프로필 YAML 로드. 존재하지 않으면 명확한 에러."""
    path = config_dir() / "profiles" / f"{name}.yaml"
    if not path.exists():
        available = _list_names(config_dir() / "profiles")
        raise FileNotFoundError(
            f"프로필 '{name}' 을(를) 찾을 수 없습니다: {path}\n"
            f"사용 가능한 프로필: {', '.join(available) or '(없음)'}"
        )
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_glossary(name: str) -> dict[str, Any]:
    """용어집 YAML 로드. 없으면 빈 구조 반환(에러 아님 — 용어집은 선택)."""
    path = config_dir() / "glossaries" / f"{name}.yaml"
    if not path.exists():
        return {"terms": [], "aliases": {}}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("terms", [])
    data.setdefault("aliases", {})
    return data


def _list_names(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.yaml"))
