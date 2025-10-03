# app/services/pulumi_engine.py
from __future__ import annotations
import os, shutil
from pathlib import Path
from typing import Dict, Any
from pulumi import automation as auto
from .program_builder import build_pulumi_program

DEFAULT_LOCATION = os.getenv("AZURE_LOCATION", "westeurope")

def init_pulumi_env() -> None:
    """
    Compute a clean local backend + pulumi home from env (PULUMI_STATE_DIR / PULUMI_WORK_DIR)
    and apply them to the current process so /health can display them before any preview/up.
    """
    
    os.environ.update(_ensure_pulumi_env())


DEFAULT_LOCATION = os.getenv("AZURE_LOCATION", "westeurope")

# at top of file
from pathlib import Path

def _win_path(p: str) -> str:
    # Convert Git Bash style /c/... to C:\...
    if p and p.startswith("/c/"):
        return "C:\\" + p[3:].replace("/", "\\")
    return p

def _ensure_pulumi_env() -> dict:
    env = os.environ.copy()
    # (keep your pulumi.exe PATH logic as-is above)
    env.setdefault("PULUMI_SECRETS_PROVIDER", "passphrase")         # NEW
    env.setdefault("PULUMI_CONFIG_PASSPHRASE", "local-dev-only")  
    # --- Build backend from PULUMI_STATE_DIR (your absolute path) ---
    state_raw = _win_path(os.getenv("PULUMI_STATE_DIR", r"C:\jahanzaib-git\pulumi-state")) # e.g., C:\jahanzaib-git\pulumi-state will change for bobby and abdulah
    state_dir = Path(state_raw).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)

    # IMPORTANT: use two slashes => file://C:/... to avoid C:/C: duplication
    backend_url = "file://" + state_dir.as_posix()   # e.g., file://C:/jahanzaib-git/pulumi-state
    env["PULUMI_BACKEND_URL"] = backend_url

    # Optional: stable Pulumi home
    home_raw = _win_path(os.getenv("PULUMI_HOME", r"C:\jahanzaib-git\.pulumi-home"))
    pulumi_home = Path(home_raw).resolve()
    pulumi_home.mkdir(parents=True, exist_ok=True)
    env["PULUMI_HOME"] = str(pulumi_home)

    # Debug (temporary)
    print("Using PULUMI_BACKEND_URL =", env["PULUMI_BACKEND_URL"])
    print("Using PULUMI_HOME        =", env["PULUMI_HOME"])
    return env

# Work dir: use PULUMI_WORK_DIR if set
WORK_DIR = Path(_win_path(os.getenv("PULUMI_WORK_DIR", str(Path.cwd() / "pulumi-work")))).resolve()
WORK_DIR.mkdir(parents=True, exist_ok=True)

def _stack(project: str, env_name: str, program):
    pulumi_env = _ensure_pulumi_env()
    os.environ.update(pulumi_env)  # make sure the CLI child sees our env

    stack = auto.create_or_select_stack(
        stack_name=f"{project}-{env_name}",
        project_name=project,
        program=program,
        work_dir=str(WORK_DIR),
    )
    return stack, pulumi_env

class PulumiEngine:
    @staticmethod
    def _set_config(stack, ir: Dict[str, Any]):
        location = ir.get("location") or ir.get("region") or DEFAULT_LOCATION
        stack.set_config("azure-native:location", auto.ConfigValue(value=location))

    @staticmethod
    def preview(ir: Dict[str, Any]):
        project = ir.get("project", "canvas")
        env_name = ir.get("env", "dev")
        program = build_pulumi_program(ir)
        stack, _ = _stack(project, env_name, program)
        PulumiEngine._set_config(stack, ir)
        res = stack.preview(on_output=print)
        return {"preview": True, "changeSummary": res.change_summary}

    @staticmethod
    def up(ir: Dict[str, Any]):
        project = ir.get("project", "canvas")
        env_name = ir.get("env", "dev")
        program = build_pulumi_program(ir)
        stack, _ = _stack(project, env_name, program)
        PulumiEngine._set_config(stack, ir)
        up_res = stack.up(on_output=print)

        def _unwrap(x):
            if hasattr(x, "value"):
                return _unwrap(x.value)
            if isinstance(x, dict):
                return {k: _unwrap(v) for k, v in x.items()}
            if isinstance(x, (list, tuple)):
                return type(x)(_unwrap(v) for v in x)
            return x

        outputs = {k: _unwrap(v) for k, v in (up_res.outputs or {}).items()}

        # Be defensive about summary members (SDK versions differ)
        duration_sec = None
        resource_changes = None
        if getattr(up_res, "summary", None):
            s = up_res.summary
            resource_changes = getattr(s, "resource_changes", None)
            dur = getattr(s, "duration", None)
            if hasattr(dur, "seconds"):
                duration_sec = dur.seconds
            elif isinstance(dur, (int, float)):
                duration_sec = dur  # some SDKs return number of seconds
            else:
                duration_sec = None

        return {
            "preview": False,
            "outputs": outputs,
            "summary": {
                "resources": resource_changes,
                "duration_sec": duration_sec,
            },
        }

    @staticmethod
    def destroy(project: str, env_name: str):
        def program(): pass
        stack, _ = _stack(project, env_name, program)
        res = stack.destroy(on_output=print)
        stack.workspace.remove_stack(stack.name)
        return {"destroyed": True}
