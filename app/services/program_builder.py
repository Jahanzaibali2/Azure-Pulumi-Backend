from __future__ import annotations
from typing import Dict, Any
import pulumi
from pulumi_azure_native import resources
from .azure_fabric import AzureFabric

def build_pulumi_program(ir: Dict[str, Any]):
    project = ir.get("project", "canvas")
    env = ir.get("env", "dev")
    location = ir.get("location") or ir.get("region") or "westeurope"

    def program():
        rg = resources.ResourceGroup(f"rg-{project}-{env}")
        fabric = AzureFabric(rg_name=rg.name, location=location)
        fabric.apply_ir(ir)
        pulumi.export("resourceGroupName", rg.name)
        pulumi.export("fabricOutputs", fabric.outputs())

    return program
