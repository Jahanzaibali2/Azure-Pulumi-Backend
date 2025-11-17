# app/services/pulumi_engine.py
from __future__ import annotations
import os, shutil
from pathlib import Path
from typing import Dict, Any, Optional
import requests
from pulumi import automation as auto
from .program_builder import build_pulumi_program
from .validator import PayloadValidator

from pathlib import Path

DEFAULT_LOCATION = os.getenv("AZURE_LOCATION", "southeastasia")

def init_pulumi_env() -> None:
    """
    Compute a clean local backend + pulumi home from env (PULUMI_STATE_DIR / PULUMI_WORK_DIR)
    and apply them to the current process so /health can display them before any preview/up.
    Reads values from .env file (loaded via load_dotenv() in main.py).
    """
    os.environ.update(_ensure_pulumi_env())

def _win_path(p: str) -> str:
    # Convert Git Bash style /c/... to C:\...
    if p and p.startswith("/c/"):
        return "C:\\" + p[3:].replace("/", "\\")
    return p

def _ensure_pulumi_env() -> dict:
    env = os.environ.copy()
    # Pulumi secrets configuration (read from .env file, with defaults)
    # These are already in env from load_dotenv(), but set defaults if not present
    env.setdefault("PULUMI_SECRETS_PROVIDER", "passphrase")
    env.setdefault("PULUMI_CONFIG_PASSPHRASE", "local-dev-only")
    
    # --- Build backend from PULUMI_STATE_DIR (read from .env file) ---
    # Default to relative path if not set in .env
    state_raw = os.getenv("PULUMI_STATE_DIR", str(Path.cwd() / "pulumi-state"))
    state_raw = _win_path(state_raw)
    state_dir = Path(state_raw).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)

    # IMPORTANT: use two slashes => file://C:/... to avoid C:/C: duplication
    backend_url = "file://" + state_dir.as_posix()
    env["PULUMI_BACKEND_URL"] = backend_url

    # Pulumi home directory (read from .env file)
    # Default to ~/.pulumi if not set in .env
    home_raw = os.getenv("PULUMI_HOME")
    if home_raw:
        home_raw = _win_path(home_raw)
        pulumi_home = Path(home_raw).resolve()
    else:
        # Default to user's home directory
        pulumi_home = Path.home() / ".pulumi"
    pulumi_home.mkdir(parents=True, exist_ok=True)
    env["PULUMI_HOME"] = str(pulumi_home)

    # Debug (temporary)
    print("Using PULUMI_BACKEND_URL =", env["PULUMI_BACKEND_URL"])
    print("Using PULUMI_HOME        =", env["PULUMI_HOME"])
    return env

def _get_work_dir() -> Path:
    """Get Pulumi work directory from .env file, or use default"""
    work_dir_raw = os.getenv("PULUMI_WORK_DIR", str(Path.cwd() / "pulumi-work"))
    work_dir = Path(_win_path(work_dir_raw)).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir

def _stack(project: str, env_name: str, program):
    pulumi_env = _ensure_pulumi_env()
    os.environ.update(pulumi_env)  # make sure the CLI child sees our env
    
    # Get work directory (reads from .env file)
    work_dir = _get_work_dir()

    stack = auto.create_or_select_stack(
        stack_name=f"{project}-{env_name}",
        project_name=project,
        program=program,
        work_dir=str(work_dir),
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
        
        # Validate payload first
        validation = PayloadValidator.validate(ir)
        
        # Build and run Pulumi preview
        program = build_pulumi_program(ir)
        stack, _ = _stack(project, env_name, program)
        PulumiEngine._set_config(stack, ir)
        res = stack.preview(on_output=print)
        
        # Combine validation results with preview results
        return {
            "preview": True,
            "changeSummary": res.change_summary,
            "validation": {
                "valid": validation["valid"],
                "errors": validation["errors"],
                "warnings": validation["warnings"],
                "suggestions": validation["suggestions"]
            }
        }

    @staticmethod
    def up(ir: Dict[str, Any]):
        project = ir.get("project", "canvas")
        env_name = ir.get("env", "dev")
        program = build_pulumi_program(ir)
        stack, _ = _stack(project, env_name, program)
        PulumiEngine._set_config(stack, ir)
        
        try:
            up_res = stack.up(on_output=print)
        except Exception as e:
            # Extract detailed error information
            error_msg = str(e)
            
            # Try to get more details from the exception
            if hasattr(e, 'args') and e.args:
                error_msg = str(e.args[0]) if e.args else str(e)
            
            # Check for common Azure errors
            if "MaxNumberOfRegionalEnvironmentsInSubExceeded" in error_msg:
                raise ValueError(
                    "Container App Environment limit reached. Your subscription can only have 1 Container App Environment "
                    "in this region. Solutions: 1) Remove Container App from payload, 2) Use a different region, "
                    "3) Delete existing Container App Environment in this region."
                )
            elif "StorageAccountAlreadyTaken" in error_msg or "already taken" in error_msg.lower():
                raise ValueError(
                    "Storage account name is already taken. Storage account names must be globally unique. "
                    "Solution: Use a more unique name or add a random suffix to your storage account name."
                )
            elif "RequestDisallowedByAzure" in error_msg:
                raise ValueError(
                    "Azure subscription policy blocked this region. Your subscription has restrictions on which regions "
                    "can be used. Solution: Try a different region like 'eastus', 'westus2', or 'centralus'."
                )
            else:
                # Re-raise with original message for other errors
                raise ValueError(f"Deployment failed: {error_msg}")

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
    def _get_azure_token(client_id: str, client_secret: str, tenant_id: str) -> str:
        """Get Azure AD access token for Resource Manager API"""
        url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://management.azure.com/.default",
            "grant_type": "client_credentials"
        }
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()["access_token"]
    
    @staticmethod
    def _delete_resource_group_direct(subscription_id: str, resource_group: str, creds: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Delete resource group directly via Azure REST API"""
        if not creds:
            return {"deleted": False, "message": "Azure credentials required for direct deletion"}
        
        try:
            token = PulumiEngine._get_azure_token(
                creds["clientId"],
                creds["clientSecret"],
                creds["tenantId"]
            )
            
            url = f"https://management.azure.com/subscriptions/{subscription_id}/resourcegroups/{resource_group}?api-version=2021-04-01"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 202:
                return {
                    "deleted": True,
                    "message": f"Resource group '{resource_group}' deletion initiated. This may take 5-10 minutes."
                }
            elif response.status_code == 200:
                return {
                    "deleted": True,
                    "message": f"Resource group '{resource_group}' deleted successfully."
                }
            elif response.status_code == 404:
                return {
                    "deleted": False,
                    "message": f"Resource group '{resource_group}' not found (may already be deleted)."
                }
            else:
                return {
                    "deleted": False,
                    "message": f"Failed to delete resource group. Status: {response.status_code}",
                    "error": response.text
                }
        except Exception as e:
            return {
                "deleted": False,
                "message": f"Error deleting resource group: {str(e)}"
            }
    
    @staticmethod
    def destroy(project: str, env_name: str, creds: Optional[Dict[str, Any]] = None):
        def program(): pass
        
        # Try Pulumi destroy first
        try:
            stack, _ = _stack(project, env_name, program)
        except Exception as e:
            # Stack doesn't exist - try direct Azure API deletion
            resource_group = f"rg-{project}-{env_name}"
            if creds:
                return {
                    "destroyed": False,
                    "pulumi_stack": "not_found",
                    "attempting_direct_deletion": True,
                    **PulumiEngine._delete_resource_group_direct(
                        creds.get("subscriptionId", ""),
                        resource_group,
                        creds
                    )
                }
            else:
                return {
                    "destroyed": False,
                    "message": f"Stack '{project}-{env_name}' not found and no credentials provided for direct deletion.",
                    "error": str(e)
                }
        
        try:
            # Actually destroy the resources - this deletes them from Azure
            res = stack.destroy(on_output=print)
            
            # Extract deletion information
            deleted_count = 0
            if hasattr(res, "summary") and res.summary:
                resource_changes = getattr(res.summary, "resource_changes", {})
                if resource_changes:
                    deleted_count = getattr(resource_changes, "delete", 0)
            
            # Remove the stack from Pulumi workspace
            try:
                stack.workspace.remove_stack(stack.name)
            except:
                pass  # Stack might already be removed
            
            return {
                "destroyed": True,
                "resources_deleted": deleted_count,
                "message": f"Destroyed {deleted_count} resources via Pulumi. Deletion may take 5-10 minutes to complete in Azure. Refresh Azure Portal to see updates.",
                "resource_group": f"rg-{project}-{env_name}"
            }
        except Exception as e:
            # If Pulumi destroy fails, try direct Azure API deletion
            resource_group = f"rg-{project}-{env_name}"
            if creds:
                direct_result = PulumiEngine._delete_resource_group_direct(
                    creds.get("subscriptionId", ""),
                    resource_group,
                    creds
                )
                return {
                    "destroyed": direct_result.get("deleted", False),
                    "pulumi_destroy_failed": True,
                    "error": str(e),
                    **direct_result
                }
            else:
                # Try to remove stack even if destroy failed
                try:
                    stack.workspace.remove_stack(stack.name)
                except:
                    pass
                return {
                    "destroyed": False,
                    "error": str(e),
                    "message": "Destroy failed. Some resources may still exist. Provide credentials to attempt direct deletion."
                }
