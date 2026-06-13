"""
skills_db.py — Управление навыками агента.

Inspired by Replit's .local/skills/ architecture:
  - Файлы data/skills/*.md = source of truth (Markdown + YAML frontmatter)
  - In-memory index (только мета) загружается при старте, обновляется при изменениях
  - Полный контент загружается лениво при вызове search / use_skill
  - SQLite skill_stats таблица = только счётчики (used_count, last_used)

Формат файла навыка:
  ---
  name: ref_standard
  title: Стандартный реферальный прогон
  type: knowledge          # knowledge | workflow
  tags: [ref, conductor, standard]
  scope: global            # global | chat
  active: true
  created: 2026-06-12
  ---

  ## Когда использовать
  ...

  ## Когда НЕ использовать
  ...

  ## Как применять
  ...
"""

from __future__ import annotations

import re
import logging
import json
import aiosqlite
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from config.constants import SESSIONS_DB

log = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "data" / "skills"

_KNOWLEDGE_TPL = """---
name: {name}
title: {title}
type: knowledge
tags: {tags}
scope: {scope}
active: true
created: {created}
---

## Когда использовать
{when_use}

## Когда НЕ использовать
{when_not}

## Как применять
{how}
"""

_WORKFLOW_TPL = """---
name: {name}
title: {title}
type: workflow
tags: {tags}
scope: {scope}
active: true
created: {created}
---

## Описание
{description}

## Шаги
{steps}
"""


# ════════════════════════════════════════════════════
# DATA CLASSES
# ════════════════════════════════════════════════════

@dataclass
class SkillMeta:
    """Лёгкий индекс — только фронтматтер, без контента."""
    name:       str
    title:      str
    skill_type: str          # knowledge | workflow
    tags:       list[str]
    scope:      str          # global | chat
    active:     bool
    created:    str
    path:       Path


@dataclass
class Skill(SkillMeta):
    """Полный навык с контентом (загружается лениво)."""
    content: str = ""


# ════════════════════════════════════════════════════
# ПАРСИНГ FRONTMATTER
# ════════════════════════════════════════════════════

_FRONT_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)", re.DOTALL)


def _parse_front(text: str) -> tuple[dict, str]:
    m = _FRONT_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    meta: dict = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            meta[k] = [t.strip() for t in v[1:-1].split(",") if t.strip()]
        elif v.lower() == "true":
            meta[k] = True
        elif v.lower() == "false":
            meta[k] = False
        else:
            meta[k] = v
    return meta, body.strip()


def _load_meta(path: Path) -> Optional[SkillMeta]:
    try:
        meta, _ = _parse_front(path.read_text(encoding="utf-8"))
        if not meta.get("name"):
            return None
        return SkillMeta(
            name=meta.get("name", path.stem),
            title=meta.get("title", path.stem),
            skill_type=meta.get("type", "knowledge"),
            tags=meta.get("tags", []),
            scope=meta.get("scope", "global"),
            active=meta.get("active", True),
            created=meta.get("created", ""),
            path=path,
        )
    except Exception as e:
        log.warning(f"[Skills] {path.name}: {e}")
        return None


def _load_full(path: Path) -> Optional[Skill]:
    try:
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_front(text)
        if not meta.get("name"):
            return None
        return Skill(
            name=meta.get("name", path.stem),
            title=meta.get("title", path.stem),
            skill_type=meta.get("type", "knowledge"),
            tags=meta.get("tags", []),
            scope=meta.get("scope", "global"),
            active=meta.get("active", True),
            created=meta.get("created", ""),
            path=path,
            content=body,
        )
    except Exception as e:
        log.warning(f"[Skills] {path.name}: {e}")
        return None


# ════════════════════════════════════════════════════
# IN-MEMORY INDEX
# ════════════════════════════════════════════════════

_index: dict[str, SkillMeta] = {}


def _rebuild_index() -> None:
    global _index
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    _index = {}
    for md in sorted(SKILLS_DIR.glob("*.md")):
        m = _load_meta(md)
        if m:
            _index[m.name] = m


def get_index() -> list[SkillMeta]:
    if not _index:
        _rebuild_index()
    return list(_index.values())


# ════════════════════════════════════════════════════
# CRUD
# ════════════════════════════════════════════════════

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.lower().strip())


def create_knowledge_skill(
    name: str, title: str, tags: list[str],
    when_use: str, when_not: str = "—", how: str = "—",
    scope: str = "global",
) -> Skill:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slug(name)
    path = SKILLS_DIR / f"{slug}.md"
    text = _KNOWLEDGE_TPL.format(
        name=slug, title=title,
        tags=json.dumps(tags, ensure_ascii=False),
        scope=scope, created=str(date.today()),
        when_use=when_use, when_not=when_not, how=how,
    )
    path.write_text(text, encoding="utf-8")
    _rebuild_index()
    return _load_full(path)


def create_workflow_skill(
    name: str, title: str, tags: list[str],
    steps: list[str], description: str = "",
    scope: str = "global",
) -> Skill:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slug(name)
    path = SKILLS_DIR / f"{slug}.md"
    steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    text = _WORKFLOW_TPL.format(
        name=slug, title=title,
        tags=json.dumps(tags, ensure_ascii=False),
        scope=scope, created=str(date.today()),
        description=description or title,
        steps=steps_text,
    )
    path.write_text(text, encoding="utf-8")
    _rebuild_index()
    return _load_full(path)


def get_skill(name: str) -> Optional[Skill]:
    if not _index:
        _rebuild_index()
    meta = _index.get(_slug(name))
    return _load_full(meta.path) if meta else None


def delete_skill(name: str) -> bool:
    if not _index:
        _rebuild_index()
    meta = _index.get(_slug(name))
    if not meta:
        return False
    meta.path.unlink(missing_ok=True)
    _rebuild_index()
    return True


def toggle_skill(name: str) -> Optional[bool]:
    if not _index:
        _rebuild_index()
    meta = _index.get(_slug(name))
    if not meta:
        return None
    text = meta.path.read_text(encoding="utf-8")
    old = "true" if meta.active else "false"
    new = "false" if meta.active else "true"
    text = re.sub(rf"^active:\s*{old}", f"active: {new}", text, flags=re.MULTILINE)
    meta.path.write_text(text, encoding="utf-8")
    _rebuild_index()
    return not meta.active


async def increment_used(name: str) -> None:
    from datetime import datetime
    try:
        async with aiosqlite.connect(SESSIONS_DB) as db:
            await db.execute(
                "INSERT INTO skill_stats(name, used_count, last_used) VALUES(?,1,?) "
                "ON CONFLICT(name) DO UPDATE SET used_count=used_count+1, last_used=?",
                (name, datetime.now().isoformat(), datetime.now().isoformat()),
            )
            await db.commit()
    except Exception:
        pass


# ════════════════════════════════════════════════════
# SEARCH  (agent tool: search_skills)
# ════════════════════════════════════════════════════

def search_skills(query: str, limit: int = 4) -> list[Skill]:
    """
    Поиск навыков по запросу (name + title + tags + content).
    Inspired by Replit agent skill lookup: индекс сначала,
    полный контент только при совпадении по индексу.
    """
    if not _index:
        _rebuild_index()
    terms = set(re.split(r"\W+", query.lower())) - {""}
    results = []
    for meta in _index.values():
        if not meta.active:
            continue
        blob  = (meta.name + " " + meta.title + " " + " ".join(meta.tags)).lower()
        score = sum(3 for t in terms if t in blob)
        skill = _load_full(meta.path)
        if skill:
            score += sum(1 for t in terms if t in skill.content.lower())
            results.append((score, skill))
    results.sort(key=lambda x: x[0], reverse=True)
    return [s for sc, s in results[:limit] if sc > 0]


def get_active_knowledge_skills() -> list[Skill]:
    """Все активные knowledge-навыки для инъекции в system prompt."""
    if not _index:
        _rebuild_index()
    out = []
    for meta in _index.values():
        if meta.active and meta.skill_type == "knowledge":
            s = _load_full(meta.path)
            if s:
                out.append(s)
    return out


def parse_workflow_steps(skill: Skill) -> list[str]:
    """Извлечь шаги из workflow-навыка для propose_plan."""
    steps, in_steps = [], False
    for line in skill.content.splitlines():
        s = line.strip()
        if s == "## Шаги":
            in_steps = True
            continue
        if in_steps:
            if s.startswith("##"):
                break
            m = re.match(r"^\d+\.\s+(.+)$", s)
            if m:
                steps.append(m.group(1))
    return steps


def format_skill_for_agent(skill: Skill) -> str:
    """Форматировать навык для инъекции в system prompt."""
    icon = "⚡" if skill.skill_type == "workflow" else "📖"
    return f"### {icon} Навык: {skill.title}\n\n{skill.content}"
