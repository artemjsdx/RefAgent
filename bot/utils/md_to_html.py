"""
md_to_html.py — Конвертирует Markdown (который генерирует LLM) в Telegram HTML.

Поддерживаемые паттерны:
  **bold** / __bold__     → <b>bold</b>
  *italic* / _italic_     → <i>italic</i>
  `inline code`           → <code>inline code</code>
  ```lang\\ncode\\n```    → <pre><code>code</code></pre>
  ### / ## / # Heading    → <b>Heading</b>
  ---  / ***              → ─────────────
  - item / * item         → • item  (bullet list)

Все остальные символы HTML-экранируются чтобы не ломать parse_mode="HTML".
"""

from __future__ import annotations

import html
import re


def md_to_html(text: str) -> str:
    """Convert LLM Markdown output to Telegram-safe HTML string."""
    if not text:
        return text

    # ── 1. Вырезаем блоки кода ─────────────────────────────
    # Сохраняем их с placeholder'ами, чтобы не трогать внутри

    code_blocks: list[str] = []

    def _save_block(m: re.Match) -> str:
        inner = html.escape(m.group(2).strip())
        code_blocks.append(f"<pre><code>{inner}</code></pre>")
        return f"\x00BLOCK{len(code_blocks) - 1}\x00"

    text = re.sub(r"```(?:[^\n`]*)\n?(.*?)```", _save_block, text, flags=re.DOTALL)

    # ── 2. Вырезаем inline-code ────────────────────────────
    inline_codes: list[str] = []

    def _save_inline(m: re.Match) -> str:
        inner = html.escape(m.group(1))
        inline_codes.append(f"<code>{inner}</code>")
        return f"\x00INLINE{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`\n]+)`", _save_inline, text)

    # ── 3. HTML-экранируем оставшийся текст ───────────────
    text = html.escape(text)

    # ── 4. Восстанавливаем code-блоки ─────────────────────
    for i, block in enumerate(code_blocks):
        text = text.replace(f"\x00BLOCK{i}\x00", block)
    for i, code in enumerate(inline_codes):
        text = text.replace(f"\x00INLINE{i}\x00", code)

    # ── 5. Заголовки: ### Heading ──────────────────────────
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # ── 6. Bold: **text** и __text__ ──────────────────────
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"__(.+?)__",     r"<b>\1</b>", text, flags=re.DOTALL)

    # ── 7. Italic: *text* и _text_ ────────────────────────
    # Только однострочные чтобы не захватывать лишнего
    text = re.sub(r"\*([^*\n<>]+)\*", r"<i>\1</i>", text)
    text = re.sub(r"_([^_\n<>]+)_",   r"<i>\1</i>", text)

    # ── 8. Горизонтальные разделители ─────────────────────
    text = re.sub(r"^[-*_]{3,}$", "─────────────", text, flags=re.MULTILINE)

    # ── 9. Bullet-списки: - item / * item ─────────────────
    text = re.sub(r"^[ \t]*[-*]\s+", "• ", text, flags=re.MULTILINE)

    return text
