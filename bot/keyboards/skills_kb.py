"""
  skills_kb.py — Клавиатуры раздела Навыки.
  """
  from __future__ import annotations
  from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
  from tools.skills_db import SkillMeta

  CB_SKILLS_LIST   = "skills:list"
  CB_SKILLS_ADD    = "skills:add"
  CB_SK_TYPE_KN    = "skill:type:knowledge"
  CB_SK_TYPE_WF    = "skill:type:workflow"
  CB_SK_SCOPE_GL   = "skill:scope:global"
  CB_SK_SCOPE_CH   = "skill:scope:chat"
  CB_SK_SKIP       = "skill:skip"
  CB_SK_CANCEL     = "skill:cancel"

  def _scb(action: str, name: str) -> str:
      return f"skill:{action}:{name[:38]}"

  def skills_list_keyboard(skills: list[SkillMeta]) -> InlineKeyboardMarkup:
      TYPE_ICON = {"knowledge": "📖", "workflow": "⚡"}
      rows = []
      for s in skills[:12]:
          icon  = TYPE_ICON.get(s.skill_type, "📄")
          flag  = "✅" if s.active else "⬜"
          label = f"{flag} {icon} {s.title}"[:42]
          rows.append([InlineKeyboardButton(text=label, callback_data=_scb("view", s.name))])
      rows.append([InlineKeyboardButton(text="➕ Добавить навык", callback_data=CB_SKILLS_ADD)])
      rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu:back_main")])
      return InlineKeyboardMarkup(inline_keyboard=rows)

  def skill_view_keyboard(name: str, active: bool) -> InlineKeyboardMarkup:
      tl = "⬜ Выключить" if active else "✅ Включить"
      return InlineKeyboardMarkup(inline_keyboard=[
          [
              InlineKeyboardButton(text=tl,            callback_data=_scb("toggle", name)),
              InlineKeyboardButton(text="🗑 Удалить",  callback_data=_scb("delete", name)),
          ],
          [InlineKeyboardButton(text="◀️ К навыкам",  callback_data=CB_SKILLS_LIST)],
      ])

  def skill_delete_confirm_kb(name: str) -> InlineKeyboardMarkup:
      return InlineKeyboardMarkup(inline_keyboard=[
          [
              InlineKeyboardButton(text="✅ Да, удалить", callback_data=_scb("del_ok", name)),
              InlineKeyboardButton(text="❌ Отмена",      callback_data=_scb("view",   name)),
          ]
      ])

  def skill_type_keyboard() -> InlineKeyboardMarkup:
      return InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="📖 Knowledge — инструкция для агента", callback_data=CB_SK_TYPE_KN)],
          [InlineKeyboardButton(text="⚡ Workflow — шаблон плана",           callback_data=CB_SK_TYPE_WF)],
          [InlineKeyboardButton(text="❌ Отмена",                            callback_data=CB_SK_CANCEL)],
      ])

  def skill_scope_keyboard() -> InlineKeyboardMarkup:
      return InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="🌍 Глобальный (все чаты)", callback_data=CB_SK_SCOPE_GL)],
          [InlineKeyboardButton(text="💬 Только этот чат",       callback_data=CB_SK_SCOPE_CH)],
          [InlineKeyboardButton(text="❌ Отмена",                callback_data=CB_SK_CANCEL)],
      ])

  def skip_keyboard() -> InlineKeyboardMarkup:
      return InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="⏭ Пропустить", callback_data=CB_SK_SKIP)],
          [InlineKeyboardButton(text="❌ Отмена",     callback_data=CB_SK_CANCEL)],
      ])
  