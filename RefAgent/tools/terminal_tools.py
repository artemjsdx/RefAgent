"""
terminal_tools.py — Инструменты для выполнения shell-команд и Python-скриптов.

execute_command:    запустить shell-команду с таймаутом
write_temp_script:  записать Python-скрипт во временный файл
run_temp_script:    выполнить временный Python-скрипт
cleanup_scripts:    удалить старые временные скрипты
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from config.constants import SCRIPTS_DIR, SCRIPT_TIMEOUT, SCRIPT_MAX_AGE_HOURS


# ════════════════════════════════════════════════════
# EXECUTE COMMAND
# ════════════════════════════════════════════════════

async def execute_command(
    command: str,
    timeout: int = SCRIPT_TIMEOUT,
    cwd:     Optional[str] = None,
) -> dict:
    """
    Выполнить shell-команду асинхронно.
    Возвращает {stdout, stderr, returncode, timeout_exceeded}
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout = asyncio.subprocess.PIPE,
            stderr = asyncio.subprocess.PIPE,
            cwd    = cwd,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=float(timeout)
            )
            return {
                "stdout":          stdout_b.decode("utf-8", errors="replace"),
                "stderr":          stderr_b.decode("utf-8", errors="replace"),
                "returncode":      proc.returncode,
                "timeout_exceeded": False,
            }
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "stdout":          "",
                "stderr":          f"Команда прервана по таймауту ({timeout}с)",
                "returncode":      -1,
                "timeout_exceeded": True,
            }
    except Exception as e:
        return {
            "stdout":          "",
            "stderr":          str(e),
            "returncode":      -1,
            "timeout_exceeded": False,
        }


# ════════════════════════════════════════════════════
# TEMP SCRIPTS
# ════════════════════════════════════════════════════

def write_temp_script(code: str, name: Optional[str] = None) -> Path:
    """
    Записать Python-скрипт во временный файл.
    Возвращает путь к файлу.
    """
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    if not name:
        name = f"script_{int(time.time())}_{uuid.uuid4().hex[:6]}.py"
    elif not name.endswith(".py"):
        name = name + ".py"

    path = SCRIPTS_DIR / name
    path.write_text(code, encoding="utf-8")
    return path


async def run_temp_script(
    code:    str,
    timeout: int = SCRIPT_TIMEOUT,
    name:    Optional[str] = None,
) -> dict:
    """
    Записать и запустить временный Python-скрипт.
    Возвращает {stdout, stderr, returncode, timeout_exceeded, script_path}
    """
    path   = write_temp_script(code, name)
    result = await execute_command(
        f"python3 {path}",
        timeout = timeout,
    )
    result["script_path"] = str(path)
    return result


# ════════════════════════════════════════════════════
# CLEANUP
# ════════════════════════════════════════════════════

def cleanup_scripts(max_age_hours: float = SCRIPT_MAX_AGE_HOURS) -> int:
    """
    Удалить временные скрипты старше max_age_hours.
    Возвращает количество удалённых файлов.
    """
    if not SCRIPTS_DIR.exists():
        return 0

    now     = time.time()
    cutoff  = now - max_age_hours * 3600
    deleted = 0

    for path in SCRIPTS_DIR.glob("*.py"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                deleted += 1
        except OSError:
            pass

    return deleted


# ════════════════════════════════════════════════════
# FORMAT RESULT
# ════════════════════════════════════════════════════

def format_command_result(result: dict, max_chars: int = 2000) -> str:
    """Форматировать результат команды для вывода агенту."""
    lines = []
    rc = result.get("returncode", -1)
    status = "✅" if rc == 0 else "❌"

    if result.get("timeout_exceeded"):
        lines.append("⏱ Команда прервана по таймауту")
    else:
        lines.append(f"{status} Код завершения: {rc}")

    stdout = result.get("stdout", "").strip()
    stderr = result.get("stderr", "").strip()

    if stdout:
        out = stdout[:max_chars]
        if len(stdout) > max_chars:
            out += f"\n[...обрезано, всего {len(stdout)} симв...]"
        lines.append(f"STDOUT:\n{out}")

    if stderr:
        err = stderr[:max_chars]
        if len(stderr) > max_chars:
            err += f"\n[...обрезано...]"
        lines.append(f"STDERR:\n{err}")

    return "\n".join(lines)
