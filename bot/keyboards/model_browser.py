"""
model_browser.py — Paginated model selection keyboard for OpenRouter (300+ models).

Features:
- Fetches live model list from OpenRouter API (cached 1 hour)
- Free / Paid filter (two entry buttons)
- 10 models per page with Prev / Next navigation
- Manual text input fallback always available
- Shows price per 1M tokens for paid models

Callback data format:
    "models:free:0"          — page 0 of free models
    "models:paid:2"          — page 2 of paid models
    "models:select:<model_id>" — user selected a model
    "models:manual"           — switch to manual text input
    "models:back"             — back to settings
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from providers.base import ModelInfo
from config.constants import MODELS_PER_PAGE


# ════════════════════════════════════════════════════
# ENTRY — Free / Paid choice
# ════════════════════════════════════════════════════

def model_filter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Бесплатные модели", callback_data="models:free:0")],
        [InlineKeyboardButton(text="Платные модели",    callback_data="models:paid:0")],
        [InlineKeyboardButton(text="Ввести вручную",    callback_data="models:manual")],
        [InlineKeyboardButton(text="Назад",             callback_data="settings:back")],
    ])


# ════════════════════════════════════════════════════
# PAGINATED LIST
# ════════════════════════════════════════════════════

def model_page_keyboard(
    models:   list[ModelInfo],
    tier:     str,    # "free" | "paid"
    page:     int,
    active_model: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Build keyboard for one page of models.
    active_model: currently selected model id (marked with asterisk).
    """
    filtered = [m for m in models if (m.is_free if tier == "free" else not m.is_free)]
    total    = len(filtered)
    start    = page * MODELS_PER_PAGE
    end      = min(start + MODELS_PER_PAGE, total)
    page_models = filtered[start:end]
    total_pages = max(1, (total + MODELS_PER_PAGE - 1) // MODELS_PER_PAGE)

    rows = []

    # ── Model buttons ──
    for m in page_models:
        label = _model_label(m, active=(m.id == active_model))
        rows.append([InlineKeyboardButton(
            text          = label,
            callback_data = f"models:select:{m.id}",
        )])

    # ── Navigation row ──
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="Назад",  callback_data=f"models:{tier}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="models:noop"))
    if end < total:
        nav.append(InlineKeyboardButton(text="Вперёд", callback_data=f"models:{tier}:{page + 1}"))
    if nav:
        rows.append(nav)

    # ── Footer ──
    rows.append([InlineKeyboardButton(text="Ввести вручную", callback_data="models:manual")])
    rows.append([InlineKeyboardButton(text="Назад к фильтру", callback_data="settings:model")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════

def _model_label(m: ModelInfo, active: bool) -> str:
    """Format model button label with price and active marker."""
    marker = "* " if active else ""
    name   = m.name[:28] if len(m.name) > 28 else m.name

    if m.is_free:
        price_str = "free"
    elif m.price_prompt is not None:
        price_str = f"${m.price_prompt:.2f}/1M"
    else:
        price_str = "paid"

    return f"{marker}{name} [{price_str}]"


def model_page_text(tier: str, page: int, total: int) -> str:
    """Header text for model browser message."""
    tier_label = "Бесплатные" if tier == "free" else "Платные"
    total_pages = max(1, (total + MODELS_PER_PAGE - 1) // MODELS_PER_PAGE)
    return (
        f"<b>Модели OpenRouter — {tier_label}</b>\n"
        f"Страница {page + 1} из {total_pages} | Всего: {total}"
    )
