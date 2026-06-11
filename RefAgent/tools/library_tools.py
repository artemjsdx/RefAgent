"""
library_tools.py — Инструменты для работы с базой знаний об ошибках.

База знаний: data/library/*.md — Markdown файлы, один файл = одна запись.
Поиск: простой поиск по словам в заголовке и содержимом.
Запись: создание нового .md файла в библиотеке.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from config.constants import LIBRARY_DIR


# ════════════════════════════════════════════════════
# SEARCH
# ════════════════════════════════════════════════════

def search_library(query: str, max_results: int = 3) -> list[dict]:
    """
    Найти записи в библиотеке знаний по запросу.
    Возвращает список dict: {slug, title, content, score}
    """
    if not LIBRARY_DIR.exists():
        return []

    query_terms = set(re.split(r"\s+", query.lower()))
    results     = []

    for md_file in LIBRARY_DIR.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        # Заголовок — первая строка # Title
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1) if title_match else md_file.stem

        # Подсчёт score: количество совпадений терминов
        lower_text = text.lower()
        score = sum(1 for t in query_terms if t in lower_text)

        if score > 0:
            results.append({
                "slug":    md_file.stem,
                "title":   title,
                "content": text,
                "score":   score,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]


def get_all_entries() -> list[dict]:
    """Вернуть все записи библиотеки."""
    if not LIBRARY_DIR.exists():
        return []
    entries = []
    for md_file in sorted(LIBRARY_DIR.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
            title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            entries.append({
                "slug":    md_file.stem,
                "title":   title_match.group(1) if title_match else md_file.stem,
                "content": text,
            })
        except OSError:
            continue
    return entries


# ════════════════════════════════════════════════════
# WRITE
# ════════════════════════════════════════════════════

def write_library(slug: str, title: str, content: str) -> dict:
    """
    Записать новую запись в библиотеку знаний.
    slug: snake_case идентификатор (только [a-z0-9_])
    Возвращает {slug, path, overwritten}
    """
    # Санитизировать slug
    clean_slug = re.sub(r"[^a-z0-9_]", "_", slug.lower())
    if not clean_slug:
        clean_slug = "entry"

    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    path = LIBRARY_DIR / f"{clean_slug}.md"
    overwritten = path.exists()

    # Убедиться что content начинается с заголовка
    if not content.strip().startswith("#"):
        content = f"# {title}\n\n{content}"

    path.write_text(content, encoding="utf-8")

    return {
        "slug":        clean_slug,
        "path":        str(path),
        "overwritten": overwritten,
    }


# ════════════════════════════════════════════════════
# FORMAT
# ════════════════════════════════════════════════════

def format_search_results(results: list[dict]) -> str:
    """Отформатировать результаты поиска для передачи агенту."""
    if not results:
        return "Библиотека: ничего не найдено по запросу."

    parts = [f"Библиотека: найдено {len(results)} записей\n"]
    for r in results:
        parts.append(f"--- [{r['slug']}] {r['title']} ---")
        # Первые 500 символов контента
        content_preview = r["content"][:500]
        if len(r["content"]) > 500:
            content_preview += "\n[...обрезано...]"
        parts.append(content_preview)
        parts.append("")

    return "\n".join(parts)
