"""
Service Registry for Azure Fabric

This module provides a registry pattern for mapping Azure service kinds
to their creation methods. This keeps the main AzureFabric class cleaner
and makes it easier to add new services.
"""

from typing import Dict, Callable, Any


class ServiceRegistry:
    """Registry for Azure service creation methods"""
    
    def __init__(self, fabric_instance):
        """
        Initialize the registry with references to AzureFabric instance methods.
        
        Args:
            fabric_instance: An instance of AzureFabric class
        """
        self.fabric = fabric_instance
        
        # Registry pattern: Map service kinds to their creation methods
       
        self._service_registry: Dict[str, Callable] = {
            "azure.storage": self.fabric._create_storage,  # S3 equivalent
            "azure.servicebus": self.fabric._create_servicebus,  # SQS equivalent
            "azure.containerapp": self.fabric._create_container_app,  # ECS/Fargate equivalent
            "azure.vm": self.fabric._create_virtual_machine,  # EC2 equivalent
            "azure.functionapp": self.fabric._create_function_app,  # Lambda equivalent
            "azure.sql": self.fabric._create_sql_database,  # RDS equivalent
            "azure.cosmosdb": self.fabric._create_cosmos_db,  # DynamoDB equivalent
            "azure.apimanagement": self.fabric._create_api_management,  # API Gateway equivalent
            "azure.keyvault": self.fabric._create_key_vault,  # Secrets Manager equivalent
            "azure.appinsights": self.fabric._create_application_insights,  # CloudWatch equivalent
            "azure.vnet": self.fabric._create_virtual_network,  # VPC equivalent
        }
    
    def get_creator(self, kind: str) -> Callable:
        """
        Get the creation method for a given service kind.
        
        Args:
            kind: The service kind (e.g., "azure.storage")
            
        Returns:
            The creation method callable
            
        Raises:
            ValueError: If the kind is not supported
        """
        creator = self._service_registry.get(kind)
        if creator:
            return creator
        else:
            supported = ", ".join(self._service_registry.keys())
            raise ValueError(
                f"Unsupported kind: {kind}. "
                f"Supported kinds: {supported}"
            )
    
    def get_supported_kinds(self) -> list:
        """Get list of all supported service kinds"""
        return list(self._service_registry.keys())
    
    def is_supported(self, kind: str) -> bool:
        """Check if a service kind is supported"""
        return kind in self._service_registry

