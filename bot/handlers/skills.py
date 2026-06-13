"""
skills.py — FSM-хендлер раздела «🧠 Навыки».

Флоу добавления Knowledge:  start → type → name → when_use → when_not → how → scope → saved
Флоу добавления Workflow:   start → type → name → steps → scope → saved
"""
from __future__ import annotations
import logging
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from tools.skills_db import (
    get_index, get_skill, delete_skill, toggle_skill,
    create_knowledge_skill, create_workflow_skill,
)
from bot.keyboards.skills_kb import (
    skills_list_keyboard, skill_view_keyboard, skill_delete_confirm_kb,
    skill_type_keyboard, skill_scope_keyboard, skip_keyboard,
    CB_SKILLS_LIST, CB_SKILLS_ADD,
    CB_SK_TYPE_KN, CB_SK_TYPE_WF,
    CB_SK_SCOPE_GL, CB_SK_SCOPE_CH,
    CB_SK_SKIP, CB_SK_CANCEL,
)

log    = logging.getLogger(__name__)
router = Router()

CB_SKILLS_MENU = "menu:skills"


# ════════════════════════════════════════════════════
# FSM СОСТОЯНИЯ
# ════════════════════════════════════════════════════

class SkillStates(StatesGroup):
    waiting_type    = State()
    waiting_name    = State()
    waiting_scope   = State()
    # Knowledge
    waiting_content = State()
    waiting_not     = State()
    waiting_how     = State()
    # Workflow
    waiting_steps   = State()


# ════════════════════════════════════════════════════
# СПИСОК НАВЫКОВ
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_SKILLS_MENU)
@router.callback_query(F.data == CB_SKILLS_LIST)
async def show_skills_list(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    skills     = get_index()
    active_cnt = sum(1 for s in skills if s.active)
    text = (
        f"🧠 <b>Навыки агента</b>  ({active_cnt} активных из {len(skills)})\n\n"
        "Навыки — знания и сценарии, которые агент читает перед каждой задачей.\n"
        "<i>📖 Knowledge</i> — текст-инструкция (автоматически инжектируется в промпт)\n"
        "<i>⚡ Workflow</i> — готовый шаблон плана (агент вызывает <code>use_skill</code>)"
    )
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=skills_list_keyboard(skills))
    await query.answer()


# ════════════════════════════════════════════════════
# ПРОСМОТР НАВЫКА
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("skill:view:"))
async def view_skill(query: CallbackQuery) -> None:
    name  = query.data[len("skill:view:"):]
    skill = get_skill(name)
    if not skill:
        await query.answer("Навык не найден", show_alert=True)
        return
    TYPE_LABEL = {"knowledge": "📖 Knowledge", "workflow": "⚡ Workflow"}
    tags_str   = ", ".join(skill.tags) or "—"
    preview    = skill.content[:700] + ("…" if len(skill.content) > 700 else "")
    status     = "✅ Активен" if skill.active else "⬜ Выключен"
    text = (
        f"<b>{skill.title}</b>  {TYPE_LABEL.get(skill.skill_type,'📄')}\n"
        f"Статус: {status}  |  Создан: {skill.created}\n"
        f"Теги: <code>{tags_str}</code>\n"
        f"Файл: <code>data/skills/{skill.name}.md</code>\n\n"
        f"{preview}"
    )
    await query.message.edit_text(text[:4000], parse_mode="HTML",
                                  reply_markup=skill_view_keyboard(skill.name, skill.active))
    await query.answer()


# ════════════════════════════════════════════════════
# TOGGLE АКТИВНОСТИ
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("skill:toggle:"))
async def toggle_skill_cb(query: CallbackQuery) -> None:
    name      = query.data[len("skill:toggle:"):]
    new_state = toggle_skill(name)
    if new_state is None:
        await query.answer("Навык не найден", show_alert=True)
        return
    await query.answer("✅ Включён" if new_state else "⬜ Выключен")
    skill = get_skill(name)
    if skill:
        await query.message.edit_reply_markup(reply_markup=skill_view_keyboard(skill.name, skill.active))


# ════════════════════════════════════════════════════
# УДАЛЕНИЕ
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("skill:delete:"))
async def ask_delete(query: CallbackQuery) -> None:
    name  = query.data[len("skill:delete:"):]
    skill = get_skill(name)
    if not skill:
        await query.answer("Навык не найден", show_alert=True)
        return
    await query.message.edit_text(
        f"🗑 Удалить навык <b>{skill.title}</b>?\nЭто действие нельзя отменить.",
        parse_mode="HTML", reply_markup=skill_delete_confirm_kb(name),
    )
    await query.answer()


@router.callback_query(F.data.startswith("skill:del_ok:"))
async def confirm_delete(query: CallbackQuery) -> None:
    name = query.data[len("skill:del_ok:"):]
    ok   = delete_skill(name)
    await query.answer("✅ Удалён" if ok else "Не найден")
    skills = get_index()
    await query.message.edit_text(
        f"🧠 <b>Навыки агента</b>  ({len(skills)} шт.)",
        parse_mode="HTML", reply_markup=skills_list_keyboard(skills),
    )


# ════════════════════════════════════════════════════
# ДОБАВЛЕНИЕ — ШАГ 1: ТИП
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_SKILLS_ADD)
async def start_add(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SkillStates.waiting_type)
    await query.message.edit_text(
        "🧠 <b>Новый навык</b>\n\nВыбери тип:",
        parse_mode="HTML", reply_markup=skill_type_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == CB_SK_CANCEL)
async def cancel_add(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    skills = get_index()
    await query.message.edit_text(
        "🧠 <b>Навыки агента</b>",
        parse_mode="HTML", reply_markup=skills_list_keyboard(skills),
    )
    await query.answer()


@router.callback_query(F.data.in_({CB_SK_TYPE_KN, CB_SK_TYPE_WF}))
async def choose_type(query: CallbackQuery, state: FSMContext) -> None:
    skill_type = "knowledge" if query.data == CB_SK_TYPE_KN else "workflow"
    await state.update_data(skill_type=skill_type)
    await state.set_state(SkillStates.waiting_name)
    icon = "📖 Knowledge" if skill_type == "knowledge" else "⚡ Workflow"
    await query.message.edit_text(
        f"Тип: <b>{icon}</b>\n\n"
        "Введи <b>название-slug</b> (латиница, snake_case):\n"
        "<i>Примеры: ref_cryptobot, flood_bypass, warmup_20acc</i>",
        parse_mode="HTML",
    )
    await query.answer()


# ════════════════════════════════════════════════════
# ШАГ 2: НАЗВАНИЕ
# ════════════════════════════════════════════════════

@router.message(SkillStates.waiting_name)
async def step_name(msg: Message, state: FSMContext) -> None:
    raw  = msg.text.strip() if msg.text else ""
    slug = re.sub(r"[^a-z0-9_]", "_", raw.lower())
    if not slug or len(slug) > 40:
        await msg.reply("⚠️ Название 1–40 символов, латиница + цифры + _. Попробуй снова.")
        return
    data = await state.get_data()
    await state.update_data(name=slug, title=raw)

    if data.get("skill_type") == "workflow":
        await state.set_state(SkillStates.waiting_steps)
        await msg.answer(
            f"Навык: <b>{slug}</b>\n\n"
            "Введи <b>шаги плана</b> — каждый с новой строки:\n"
            "<i>conductor_setup(@bot)\njoin_channel для каналов\nstart_bot с ref_param</i>",
            parse_mode="HTML",
        )
    else:
        await state.set_state(SkillStates.waiting_content)
        await msg.answer(
            f"Навык: <b>{slug}</b>\n\n"
            "✏️ <b>Когда использовать</b> этот навык?\n"
            "<i>Опиши ситуации в которых агент должен его применять.</i>",
            parse_mode="HTML",
        )


# ════════════════════════════════════════════════════
# KNOWLEDGE: ШАГИ 3–5
# ════════════════════════════════════════════════════

@router.message(SkillStates.waiting_content)
async def step_content(msg: Message, state: FSMContext) -> None:
    await state.update_data(when_use=msg.text.strip())
    await state.set_state(SkillStates.waiting_not)
    await msg.answer(
        "✏️ <b>Когда НЕ использовать</b>?",
        parse_mode="HTML", reply_markup=skip_keyboard(),
    )


@router.callback_query(F.data == CB_SK_SKIP, SkillStates.waiting_not)
async def skip_not(query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(when_not="—")
    await state.set_state(SkillStates.waiting_how)
    await query.message.edit_text(
        "✏️ <b>Как применять</b>? Конкретный алгоритм/инструкция.",
        parse_mode="HTML", reply_markup=skip_keyboard(),
    )
    await query.answer()


@router.message(SkillStates.waiting_not)
async def step_not(msg: Message, state: FSMContext) -> None:
    await state.update_data(when_not=msg.text.strip())
    await state.set_state(SkillStates.waiting_how)
    await msg.answer(
        "✏️ <b>Как применять</b>? Конкретный алгоритм/инструкция.",
        parse_mode="HTML", reply_markup=skip_keyboard(),
    )


@router.callback_query(F.data == CB_SK_SKIP, SkillStates.waiting_how)
async def skip_how(query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(how="—")
    await state.set_state(SkillStates.waiting_scope)
    await query.message.edit_text(
        "🌍 <b>Область навыка</b>:", parse_mode="HTML", reply_markup=skill_scope_keyboard(),
    )
    await query.answer()


@router.message(SkillStates.waiting_how)
async def step_how(msg: Message, state: FSMContext) -> None:
    await state.update_data(how=msg.text.strip())
    await state.set_state(SkillStates.waiting_scope)
    await msg.answer("🌍 <b>Область навыка</b>:", parse_mode="HTML", reply_markup=skill_scope_keyboard())


# ════════════════════════════════════════════════════
# WORKFLOW: ШАГ 3 — ШАГИ
# ════════════════════════════════════════════════════

@router.message(SkillStates.waiting_steps)
async def step_wf_steps(msg: Message, state: FSMContext) -> None:
    raw_steps = [l.strip() for l in (msg.text or "").splitlines() if l.strip()]
    steps     = [re.sub(r"^\d+\.\s*", "", s) for s in raw_steps]
    if not steps:
        await msg.reply("⚠️ Список шагов пустой. Введи хотя бы один шаг.")
        return
    await state.update_data(steps=steps)
    await state.set_state(SkillStates.waiting_scope)
    await msg.answer("🌍 <b>Область навыка</b>:", parse_mode="HTML", reply_markup=skill_scope_keyboard())


# ════════════════════════════════════════════════════
# ФИНАЛ — СОХРАНЕНИЕ
# ════════════════════════════════════════════════════

@router.callback_query(F.data.in_({CB_SK_SCOPE_GL, CB_SK_SCOPE_CH}))
async def finish_skill(query: CallbackQuery, state: FSMContext) -> None:
    scope = "global" if query.data == CB_SK_SCOPE_GL else "chat"
    data  = await state.get_data()
    await state.clear()

    name       = data.get("name", "skill")
    title      = data.get("title", name)
    skill_type = data.get("skill_type", "knowledge")
    tags       = re.findall(r"[a-z]+", name)

    try:
        if skill_type == "workflow":
            skill = create_workflow_skill(
                name=name, title=title, tags=tags, scope=scope,
                steps=data.get("steps", []), description=title,
            )
        else:
            skill = create_knowledge_skill(
                name=name, title=title, tags=tags, scope=scope,
                when_use=data.get("when_use", "—"),
                when_not=data.get("when_not", "—"),
                how=data.get("how", "—"),
            )
        type_label  = "📖 Knowledge" if skill_type == "knowledge" else "⚡ Workflow"
        scope_label = "🌍 Глобальный" if scope == "global" else "💬 Только этот чат"
        text = (
            f"✅ Навык <b>{skill.title}</b> создан!\n\n"
            f"Тип: {type_label}\n"
            f"Область: {scope_label}\n"
            f"Файл: <code>data/skills/{skill.name}.md</code>\n\n"
            f"Агент будет автоматически читать этот навык перед задачами по теме."
        )
    except Exception as e:
        text = f"❌ Ошибка создания навыка: {e}"

    skills = get_index()
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=skills_list_keyboard(skills))
    await query.answer()
