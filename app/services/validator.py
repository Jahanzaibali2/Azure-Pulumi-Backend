"""
Validation service for IR payloads
Checks for common issues that would cause deployment failures
"""

from typing import Dict, Any, List, Optional
import re


class PayloadValidator:
    """Validates IR payloads and returns warnings/errors"""
    
    # Common storage account names that are likely taken
    COMMON_STORAGE_NAMES = [
        "test", "storage", "mystorage", "teststorage", "stor", "data",
        "files", "blob", "container", "backup", "archive"
    ]
    
    @staticmethod
    def validate(ir: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate IR payload and return warnings/errors
        
        Returns:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str],
                "suggestions": List[str]
            }
        """
        errors = []
        warnings = []
        suggestions = []
        
        nodes = ir.get("nodes", [])
        location = ir.get("location") or ir.get("region") or "westeurope"
        project = ir.get("project", "")
        env = ir.get("env", "")
        
        # Validate each node
        for node in nodes:
            kind = node.get("kind")
            node_id = node.get("id")
            name = node.get("name") or node_id
            props = node.get("props", {})
            
            if kind == "azure.storage":
                # Check storage account name
                storage_name = props.get("accountName") or name
                storage_name_lower = storage_name.lower()
                
                # Check if name is too short or too common
                if len(storage_name_lower) < 8:
                    warnings.append(
                        f"Storage account '{storage_name}' (node: {node_id}) is very short. "
                        f"Short names are more likely to be taken globally. "
                        f"Consider using a longer, more unique name."
                    )
                    suggestions.append(
                        f"Try: '{storage_name}{project}{env}' or add random suffix"
                    )
                
                # Check against common names
                if storage_name_lower in PayloadValidator.COMMON_STORAGE_NAMES:
                    warnings.append(
                        f"Storage account '{storage_name}' (node: {node_id}) uses a very common name. "
                        f"This name is likely already taken globally. "
                        f"Storage account names must be globally unique across all Azure."
                    )
                    suggestions.append(
                        f"Use a more unique name like '{storage_name}{project}{env}2025' or add random characters"
                    )
                
                # Check naming rules
                if not re.match(r'^[a-z0-9]+$', storage_name_lower):
                    errors.append(
                        f"Storage account '{storage_name}' (node: {node_id}) contains invalid characters. "
                        f"Storage account names must be 3-24 characters, lowercase letters and numbers only."
                    )
                
                if len(storage_name_lower) > 24:
                    errors.append(
                        f"Storage account '{storage_name}' (node: {node_id}) is too long ({len(storage_name_lower)} chars). "
                        f"Maximum length is 24 characters."
                    )
                
                if len(storage_name_lower) < 3:
                    errors.append(
                        f"Storage account '{storage_name}' (node: {node_id}) is too short ({len(storage_name_lower)} chars). "
                        f"Minimum length is 3 characters."
                    )
            
            elif kind == "azure.containerapp":
                # Check for Container App Environment limits
                warnings.append(
                    f"Container App (node: {node_id}) requires a Container App Environment. "
                    f"Azure subscriptions typically allow only 1 Container App Environment per region. "
                    f"If you already have one in '{location}', this deployment will fail."
                )
                suggestions.append(
                    f"Option 1: Remove Container App from payload if limit reached\n"
                    f"Option 2: Use a different region\n"
                    f"Option 3: Delete existing Container App Environment in '{location}'"
                )
            
            elif kind == "azure.keyvault":
                # Check Key Vault naming
                kv_name = name.lower()
                if not re.match(r'^[a-zA-Z0-9-]{3,24}$', kv_name):
                    errors.append(
                        f"Key Vault '{name}' (node: {node_id}) has invalid characters. "
                        f"Key Vault names must be 3-24 characters, alphanumeric and hyphens only (no underscores)."
                    )
            
            elif kind == "azure.functionapp":
                # Function App naming
                func_name = name.lower()
                if len(func_name) > 60:
                    warnings.append(
                        f"Function App '{name}' (node: {node_id}) name is very long. "
                        f"Function App names should be under 60 characters."
                    )
        
        # Check for duplicate node IDs
        node_ids = [n.get("id") for n in nodes]
        duplicates = [nid for nid in node_ids if node_ids.count(nid) > 1]
        if duplicates:
            errors.append(
                f"Duplicate node IDs found: {', '.join(set(duplicates))}. "
                f"Each node must have a unique ID."
            )
        
        # Check edges reference valid nodes
        edges = ir.get("edges", [])
        node_id_set = set(node_ids)
        for edge in edges:
            from_id = edge.get("from") or edge.get("from_")
            to_id = edge.get("to")
            
            if from_id and from_id not in node_id_set:
                errors.append(
                    f"Edge references unknown source node: '{from_id}'. "
                    f"Available nodes: {', '.join(node_ids)}"
                )
            
            if to_id and to_id not in node_id_set:
                errors.append(
                    f"Edge references unknown destination node: '{to_id}'. "
                    f"Available nodes: {', '.join(node_ids)}"
                )
        
        # Check region policy (common blocked regions)
        blocked_regions = ["westeurope"]  # Based on your experience
        if location.lower() in blocked_regions:
            warnings.append(
                f"Region '{location}' may be blocked by your Azure subscription policy. "
                f"Consider using 'eastus', 'westus2', 'southeastasia', or 'centralus' instead."
            )
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions
        }

