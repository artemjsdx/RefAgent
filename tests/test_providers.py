"""
test_providers.py — Автономный тест всех трёх LLM-провайдеров.

Уровни тестирования:
  Level 1: прямой HTTP вызов (health check)
  Level 2: один chat completion (без инструментов)
  Level 3: одна итерация ReAct с propose_plan (tool calling)

Запуск:
  cd RefAgent && python3 tests/test_providers.py
  cd RefAgent && python3 tests/test_providers.py openrouter
  cd RefAgent && python3 tests/test_providers.py bai
  cd RefAgent && python3 tests/test_providers.py favoriteapi
"""
from __future__ import annotations

import asyncio
import os
import sys
import json
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import load_settings
from providers.base import Message, ProviderResponse


# ── ANSI colors ─────────────────────────────────────────────────────────────
GRN = "\033[92m"; RED = "\033[91m"; YLW = "\033[93m"; BLU = "\033[94m"; RST = "\033[0m"
OK  = f"{GRN}PASS{RST}"; FAIL = f"{RED}FAIL{RST}"; SKIP = f"{YLW}SKIP{RST}"


def hdr(title: str):
    print(f"\n{BLU}{'═'*60}{RST}")
    print(f"{BLU}  {title}{RST}")
    print(f"{BLU}{'═'*60}{RST}")


def result(label: str, passed: bool, detail: str = ""):
    mark = OK if passed else FAIL
    print(f"  [{mark}] {label}", f"— {detail}" if detail else "")


# ── Provider factory ─────────────────────────────────────────────────────────

def make_openrouter(model: str = "google/gemma-4-26b-a4b-it:free"):
    from providers.openrouter import OpenRouterProvider
    s = load_settings()
    key = s.env.openrouter_api_key
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY не задан")
    return OpenRouterProvider(api_key=key, default_model=model)


def make_bai(model: str = "kimi-k2.5"):
    from providers.bai import BaiProvider
    s = load_settings()
    key = s.env.bai_api_key
    if not key:
        raise RuntimeError("BAI_API_KEY не задан")
    return BaiProvider(api_key=key, default_model=model)


def make_favoriteapi(model: str = "gemini-3.0-flash-thinking"):
    from providers.favoriteapi import FavoriteAPIProvider
    s = load_settings()
    key = s.env.favoriteapi_key
    url = s.env.favoriteapi_url
    if not key or not url:
        raise RuntimeError("FAVORITEAPI_KEY / FAVORITEAPI_URL не задан")
    return FavoriteAPIProvider(api_key=key, base_url=url, default_model=model)


# ── Level 1: Health check ─────────────────────────────────────────────────────

async def test_health(provider_name: str, provider):
    t0 = time.monotonic()
    try:
        ok = await provider.health_check()
        elapsed = time.monotonic() - t0
        result(f"health_check [{provider_name}]", ok, f"{elapsed:.1f}s")
        return ok
    except Exception as e:
        elapsed = time.monotonic() - t0
        result(f"health_check [{provider_name}]", False, f"{e}")
        return False


# ── Level 2: Simple chat ─────────────────────────────────────────────────────

SIMPLE_TASK = (
    "Reply ONLY with the following JSON and nothing else: "
    '{"status":"PROVIDER_OK","provider":"<your_model_name_here>"}'
)

async def test_simple_chat(provider_name: str, provider):
    t0 = time.monotonic()
    try:
        resp: ProviderResponse = await provider.chat(
            messages=[Message(role="user", content=SIMPLE_TASK)],
        )
        elapsed = time.monotonic() - t0
        text = (resp.text or "").strip()
        # Извлекаем JSON даже если есть markdown ```
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        try:
            parsed = json.loads(text)
            passed = parsed.get("status") == "PROVIDER_OK"
            result(f"simple_chat [{provider_name}]", passed,
                   f"{elapsed:.1f}s model={parsed.get('provider','?')}")
            return passed
        except json.JSONDecodeError:
            # Просто проверяем есть ли PROVIDER_OK в тексте
            passed = "PROVIDER_OK" in (resp.text or "")
            result(f"simple_chat [{provider_name}]", passed,
                   f"{elapsed:.1f}s raw={repr((resp.text or '')[:80])}")
            return passed
    except Exception as e:
        elapsed = time.monotonic() - t0
        result(f"simple_chat [{provider_name}]", False, f"{elapsed:.1f}s ERROR: {e}")
        traceback.print_exc()
        return False


# ── Level 3: ReAct iteration (propose_plan tool) ─────────────────────────────

REACT_TASK = (
    "Create a plan with ONE step: 'Confirm test passed'. "
    "Use the propose_plan tool with steps=['Confirm test passed'] "
    "and description='Provider test'."
)

async def test_react_one_iteration(provider_name: str, provider):
    """Run one ReAct iteration that calls propose_plan tool."""
    from agent.react_loop import ReactLoop
    logs: list[str] = []

    async def log_cb(msg: str):
        logs.append(msg)
        print(f"    LOG: {msg}")

    stop = asyncio.Event()
    loop = ReactLoop(provider=provider, stop_event=stop, log_cb=log_cb)

    t0 = time.monotonic()
    try:
        answer = await asyncio.wait_for(
            loop.run(chat_id=0, user_message=REACT_TASK),
            timeout=90.0,
        )
        elapsed = time.monotonic() - t0
        passed = answer and len(answer) > 5 and "error" not in answer.lower()[:50]
        result(f"react_loop [{provider_name}]", passed,
               f"{elapsed:.1f}s iters={len([l for l in logs if 'итерация' in l])}")
        if not passed:
            print(f"    ANSWER: {repr(answer[:200])}")
        return passed
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        result(f"react_loop [{provider_name}]", False, f"TIMEOUT after {elapsed:.0f}s")
        return False
    except Exception as e:
        elapsed = time.monotonic() - t0
        result(f"react_loop [{provider_name}]", False, f"{elapsed:.1f}s {e}")
        traceback.print_exc()
        return False


# ── Full provider test suite ──────────────────────────────────────────────────

async def run_provider_tests(name: str, factory_fn, model_label: str):
    hdr(f"{name}  [{model_label}]")
    scores = {"total": 0, "passed": 0}

    try:
        provider = factory_fn()
    except RuntimeError as e:
        print(f"  [{SKIP}] Пропуск — {e}")
        return

    # L1
    scores["total"] += 1
    if await test_health(name, provider):
        scores["passed"] += 1
    else:
        print(f"  Здоровье не ОК — пропуск дальнейших тестов")
        _print_summary(name, scores)
        return

    # L2
    scores["total"] += 1
    if await test_simple_chat(name, provider):
        scores["passed"] += 1

    # L3
    scores["total"] += 1
    if await test_react_one_iteration(name, provider):
        scores["passed"] += 1

    _print_summary(name, scores)
    return scores


def _print_summary(name: str, scores: dict):
    p, t = scores["passed"], scores["total"]
    color = GRN if p == t else (YLW if p > 0 else RED)
    print(f"\n  {color}▶ {name}: {p}/{t} тестов прошло{RST}")


# ── Entry point ───────────────────────────────────────────────────────────────

PROVIDERS = {
    "openrouter": lambda: (
        "OpenRouter",
        lambda: make_openrouter("google/gemma-4-26b-a4b-it:free"),
        "gemma-4-26b:free",
    ),
    "bai": lambda: (
        "b.ai",
        lambda: make_bai("kimi-k2.5"),
        "kimi-k2.5",
    ),
    "favoriteapi": lambda: (
        "FavoriteAPI",
        lambda: make_favoriteapi("gemini-3.0-flash-thinking"),
        "gemini-3.0-flash-thinking",
    ),
}


async def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(PROVIDERS.keys())
    unknown = [t for t in targets if t not in PROVIDERS]
    if unknown:
        print(f"Неизвестные провайдеры: {unknown}")
        sys.exit(1)

    print(f"\n{BLU}RefAgent Provider Tests — {len(targets)} провайдер(ов){RST}")
    print(f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    all_results = {}
    for key in targets:
        name, factory, model = PROVIDERS[key]()
        r = await run_provider_tests(name, factory, model)
        all_results[key] = r

    # Итог
    print(f"\n{BLU}{'═'*60}{RST}")
    print(f"{BLU}  ИТОГО{RST}")
    print(f"{BLU}{'═'*60}{RST}")
    for key, r in all_results.items():
        if r is None:
            print(f"  {SKIP} {key}: пропущен")
        else:
            p, t = r["passed"], r["total"]
            c = GRN if p == t else (YLW if p > 0 else RED)
            print(f"  {c}{key}: {p}/{t}{RST}")


if __name__ == "__main__":
    asyncio.run(main())
