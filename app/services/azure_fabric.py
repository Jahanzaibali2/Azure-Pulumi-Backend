from __future__ import annotations
from typing import Dict, Any
import pulumi
from pulumi_azure_native import (
    storage,
    servicebus,
    eventgrid,
    operationalinsights,
    app as containerapp,
    compute,
    network,
    web,
    sql,
    cosmosdb,
    apimanagement,
    keyvault,
    redis,
    applicationinsights,
)
from .naming import safe_name


class AzureFabric:
    def __init__(self, rg_name: pulumi.Output[str], location: str):
        self.rg_name = rg_name
        self.location = location
        self.node_index: Dict[str, Dict[str, Any]] = {}
        self._outputs: Dict[str, pulumi.Output[Any]] = {}
        
        # Registry pattern: Map service kinds to their creation methods
        # AWS Equivalents:
        # EC2 → azure.vm, Lambda → azure.functionapp, RDS → azure.sql, 
        # DynamoDB → azure.cosmosdb, Elastic Beanstalk → azure.appservice,
        # API Gateway → azure.apimanagement, Secrets Manager → azure.keyvault,
        # ElastiCache → azure.redis, CloudWatch → azure.appinsights, VPC → azure.vnet
        self._service_registry: Dict[str, callable] = {
            "azure.storage": self._create_storage,  # S3 equivalent
            "azure.servicebus": self._create_servicebus,  # SQS equivalent
            "azure.containerapp": self._create_container_app,  # ECS/Fargate equivalent
            "azure.vm": self._create_virtual_machine,  # EC2 equivalent
            "azure.functionapp": self._create_function_app,  # Lambda equivalent
            "azure.sql": self._create_sql_database,  # RDS equivalent
            "azure.cosmosdb": self._create_cosmos_db,  # DynamoDB equivalent
            "azure.appservice": self._create_app_service,  # Elastic Beanstalk equivalent
            "azure.apimanagement": self._create_api_management,  # API Gateway equivalent
            "azure.keyvault": self._create_key_vault,  # Secrets Manager equivalent
            "azure.redis": self._create_redis_cache,  # ElastiCache equivalent
            "azure.appinsights": self._create_application_insights,  # CloudWatch equivalent
            "azure.vnet": self._create_virtual_network,  # VPC equivalent
        }

    def outputs(self) -> Dict[str, pulumi.Output[Any]]:
        return self._outputs

    def apply_ir(self, ir: Dict[str, Any]):
        nodes = ir.get("nodes", [])
        edges = ir.get("edges", [])
        
        # Use registry pattern instead of if/elif chain
        for n in nodes:
            kind = n.get("kind")
            creator = self._service_registry.get(kind)
            if creator:
                creator(n)
            else:
                supported = ", ".join(self._service_registry.keys())
                raise ValueError(
                    f"Unsupported kind: {kind}. "
                    f"Supported kinds: {supported}"
                )
        
        for e in edges:
            self._connect(e)

    # -------------------- Nodes --------------------

    def _create_storage(self, node: Dict[str, Any]):
        # Logical name (for Pulumi resource) can have hyphens; Azure account name cannot.
        logical = safe_name(node.get("name") or node["id"])[:20]
        props = node.get("props", {})

        # Allow explicit override via props.accountName if provided by caller
        desired = props.get("accountName") or (node.get("name") or node["id"])

        # Sanitize to Azure Storage account rules: [a-z0-9], length 3-24
        raw = (desired or "storage").lower()
        sa_name = "".join(ch for ch in raw if ch.isalnum())
        if len(sa_name) < 3:
            sa_name = (sa_name + "stx")[:3]
        if len(sa_name) > 24:
            sa_name = sa_name[:24]

        # Make sure it starts with a letter (not mandatory, but avoids some org policies)
        if not sa_name[0].isalpha():
            sa_name = "st" + sa_name
            sa_name = sa_name[:24]

        account_kind = props.get("accountKind", "StorageV2")
        sku_name = props.get("sku", "Standard_LRS")

        # IMPORTANT: set account_name=sa_name (the Azure name); logical name can be anything
        acct = storage.StorageAccount(
            f"st-{logical}",
            resource_group_name=self.rg_name,
            account_name=sa_name,  # <-- this is the Azure-visible name and must be sanitized
            sku=storage.SkuArgs(name=sku_name),
            kind=account_kind,
            enable_https_traffic_only=True,
            minimum_tls_version="TLS1_2",
            allow_blob_public_access=False,
        )

        container = None
        container_name = props.get("containerName")
        if container_name:
            container = storage.BlobContainer(
                f"bc-{logical}",
                resource_group_name=self.rg_name,
                account_name=acct.name,
                public_access=storage.PublicAccess.NONE,
                container_name=container_name,
            )

        keys = storage.list_storage_account_keys_output(
            resource_group_name=self.rg_name, account_name=acct.name
        )
        def _key_value(k):
            # Works for both dict payloads and typed objects
            if isinstance(k, dict):
                return k.get("value")
            return getattr(k, "value", None)

        conn_str = pulumi.Output.all(acct.name, keys.keys).apply(
            lambda args: (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={args[0]};"
                f"AccountKey={_key_value(args[1][0])};"
                f"EndpointSuffix=core.windows.net"
            )
        )
        
        self.node_index[node["id"]] = {
            "kind": "azure.storage",
            "account": acct,
            "container": container,
            "connectionString": conn_str,
        }
        self._outputs[f"storage-{logical}-accountName"] = acct.name
        self._outputs[f"storage-{logical}-conn"] = conn_str

    def _create_servicebus(self, node: Dict[str, Any]):
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})

        ns = servicebus.Namespace(
            f"sb-{name}",
            resource_group_name=self.rg_name,
            location=self.location,
            sku=servicebus.SBSkuArgs(name=props.get("sku", "Basic")),
        )

        q = servicebus.Queue(
            f"sbq-{name}",
            resource_group_name=self.rg_name,
            namespace_name=ns.name,
            queue_name=props.get("queueName", f"q-{name}"),
            enable_partitioning=props.get("partition", False),
        )

        rule = servicebus.NamespaceAuthorizationRule(
            f"sbrule-{name}",
            resource_group_name=self.rg_name,
            namespace_name=ns.name,
            rights=["Listen", "Send", "Manage"],
        )

        keys = servicebus.list_namespace_keys_output(
            resource_group_name=self.rg_name,
            namespace_name=ns.name,
            authorization_rule_name=rule.name,
        )
        conn = keys.primary_connection_string

        self.node_index[node["id"]] = {
            "kind": "azure.servicebus",
            "namespace": ns,
            "queue": q,
            "connectionString": conn,
        }
        self._outputs[f"servicebus-{name}-queueName"] = q.name
        self._outputs[f"servicebus-{name}-conn"] = conn

    def _create_container_app(self, node: Dict[str, Any]):
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        image = props.get("image", "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest")
        cpu = props.get("cpu", 0.25)
        memory = props.get("memory", "0.5Gi")
        env_vars = props.get("env", {})

        # Log Analytics workspace (no shared_keys property on the resource!)
        law = operationalinsights.Workspace(
            f"log-{name}",
            resource_group_name=self.rg_name,
            sku=operationalinsights.WorkspaceSkuArgs(name="PerGB2018"),
            retention_in_days=30,
        )

        # Fetch shared keys via data source/invoke:
        law_keys = operationalinsights.get_shared_keys_output(
            resource_group_name=self.rg_name,
            workspace_name=law.name,
        )

        ca_env = containerapp.ManagedEnvironment(
            f"cae-{name}",
            resource_group_name=self.rg_name,
            app_logs_configuration=containerapp.AppLogsConfigurationArgs(
                destination="log-analytics",
                log_analytics_configuration=containerapp.LogAnalyticsConfigurationArgs(
                    customer_id=law.customer_id,
                    shared_key=law_keys.primary_shared_key,
                ),
            ),
        )

        plain_env = [containerapp.EnvironmentVarArgs(name=k, value=str(v)) for k, v in env_vars.items()]

        app = containerapp.ContainerApp(
            f"ca-{name}",
            resource_group_name=self.rg_name,
            managed_environment_id=ca_env.id,
            configuration=containerapp.ConfigurationArgs(
                ingress=containerapp.IngressArgs(external=True, target_port=8000),
            ),
            template=containerapp.TemplateArgs(
                containers=[
                    containerapp.ContainerArgs(
                        name=name,
                        image=image,
                        resources=containerapp.ContainerResourcesArgs(cpu=cpu, memory=memory),
                        env=plain_env or None,
                    )
                ]
            ),
        )

        self.node_index[node["id"]] = {"kind": "azure.containerapp", "env": ca_env, "app": app}
        self._outputs[f"containerapp-{name}-fqdn"] = app.configuration.apply(
            lambda c: c.ingress.fqdn if c and c.ingress else None
        )

    def _create_virtual_machine(self, node: Dict[str, Any]):
        """Create Azure Virtual Machine (EC2 equivalent) - Full server control with SSH/RDP access"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # VM Configuration
        vm_size = props.get("vmSize", "Standard_B1s")  # Default: Basic tier
        admin_username = props.get("adminUsername", "azureuser")
        admin_password = props.get("adminPassword") or pulumi.Output.secret("TempPassword123!")
        image_publisher = props.get("imagePublisher", "Canonical")
        image_offer = props.get("imageOffer", "0001-com-ubuntu-server-jammy")
        image_sku = props.get("imageSku", "22_04-lts-gen2")
        
        # Create Virtual Network and Subnet (required for VM)
        vnet = network.VirtualNetwork(
            f"vnet-{name}",
            resource_group_name=self.rg_name,
            address_space=network.AddressSpaceArgs(address_prefixes=[props.get("vnetAddressSpace", "10.0.0.0/16")]),
        )
        
        subnet = network.Subnet(
            f"subnet-{name}",
            resource_group_name=self.rg_name,
            virtual_network_name=vnet.name,
            address_prefix=props.get("subnetAddressPrefix", "10.0.1.0/24"),
        )
        
        # Public IP
        public_ip = network.PublicIPAddress(
            f"pip-{name}",
            resource_group_name=self.rg_name,
            public_ip_allocation_method=network.IPAllocationMethod.DYNAMIC,
        )
        
        # Network Interface
        nic = network.NetworkInterface(
            f"nic-{name}",
            resource_group_name=self.rg_name,
            ip_configurations=[network.NetworkInterfaceIPConfigurationArgs(
                name="ipconfig1",
                subnet=network.SubnetArgs(id=subnet.id),
                public_ip_address=network.PublicIPAddressArgs(id=public_ip.id),
            )],
        )
        
        # Virtual Machine
        vm = compute.VirtualMachine(
            f"vm-{name}",
            resource_group_name=self.rg_name,
            hardware_profile=compute.HardwareProfileArgs(vm_size=vm_size),
            os_profile=compute.OSProfileArgs(
                computer_name=name,
                admin_username=admin_username,
                admin_password=admin_password,
                linux_configuration=compute.LinuxConfigurationArgs(
                    disable_password_authentication=False,
                ) if props.get("osType", "Linux") == "Linux" else None,
                windows_configuration=compute.WindowsConfigurationArgs(
                    enable_automatic_updates=True,
                ) if props.get("osType") == "Windows" else None,
            ),
            network_profile=compute.NetworkProfileArgs(
                network_interfaces=[compute.NetworkInterfaceReferenceArgs(id=nic.id)],
            ),
            storage_profile=compute.StorageProfileArgs(
                image_reference=compute.ImageReferenceArgs(
                    publisher=image_publisher,
                    offer=image_offer,
                    sku=image_sku,
                    version="latest",
                ),
            ),
        )
        
        self.node_index[node["id"]] = {
            "kind": "azure.vm",
            "vm": vm,
            "public_ip": public_ip,
            "vnet": vnet,
            "nic": nic,
        }
        self._outputs[f"vm-{name}-publicIp"] = public_ip.ip_address
        self._outputs[f"vm-{name}-adminUsername"] = pulumi.Output.from_input(admin_username)

    def _create_function_app(self, node: Dict[str, Any]):
        """Create Azure Function App (Lambda equivalent) - Serverless compute"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # Storage Account for Function App (required)
        func_storage = storage.StorageAccount(
            f"funcst-{name}",
            resource_group_name=self.rg_name,
            account_name=f"{name.replace('-', '')[:20]}func",
            sku=storage.SkuArgs(name="Standard_LRS"),
            kind="StorageV2",
        )
        
        # Get storage account keys to build connection string
        func_keys = storage.list_storage_account_keys_output(
            resource_group_name=self.rg_name,
            account_name=func_storage.name,
        )
        
        def _key_value(k):
            if isinstance(k, dict):
                return k.get("value")
            return getattr(k, "value", None)
        
        func_conn_str = pulumi.Output.all(func_storage.name, func_keys.keys).apply(
            lambda args: (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={args[0]};"
                f"AccountKey={_key_value(args[1][0])};"
                f"EndpointSuffix=core.windows.net"
            )
        )
        
        # App Service Plan
        plan = web.AppServicePlan(
            f"plan-{name}",
            resource_group_name=self.rg_name,
            kind="FunctionApp",
            sku=web.SkuDescriptionArgs(
                name=props.get("sku", "Y1"),  # Consumption plan (serverless)
                tier="Dynamic",
            ),
        )
        
        # Function App
        func_app = web.WebApp(
            f"func-{name}",
            resource_group_name=self.rg_name,
            server_farm_id=plan.id,
            site_config=web.SiteConfigArgs(
                app_settings=[
                    web.NameValuePairArgs(name="AzureWebJobsStorage", value=func_conn_str),
                    web.NameValuePairArgs(name="FUNCTIONS_EXTENSION_VERSION", value="~4"),
                    web.NameValuePairArgs(name="WEBSITE_CONTENTAZUREFILECONNECTIONSTRING", value=func_conn_str),
                    web.NameValuePairArgs(name="WEBSITE_CONTENTSHARE", value=name),
                ],
            ),
        )
        
        self.node_index[node["id"]] = {
            "kind": "azure.functionapp",
            "app": func_app,
            "plan": plan,
            "storage": func_storage,
        }
        self._outputs[f"functionapp-{name}-url"] = pulumi.Output.concat("https://", func_app.default_host_name)
        self._outputs[f"functionapp-{name}-name"] = func_app.name

    def _create_sql_database(self, node: Dict[str, Any]):
        """Create Azure SQL Database (RDS equivalent) - Managed relational database"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # SQL Server
        admin_login = props.get("adminLogin", "sqladmin")
        admin_password = props.get("adminPassword") or pulumi.Output.secret("TempPassword123!")
        
        sql_server = sql.Server(
            f"sql-{name}",
            resource_group_name=self.rg_name,
            administrator_login=admin_login,
            administrator_login_password=admin_password,
            version="12.0",
        )
        
        # SQL Database
        db = sql.Database(
            f"db-{name}",
            resource_group_name=self.rg_name,
            server_name=sql_server.name,
            sku=sql.SkuArgs(
                name=props.get("serviceTier", "S0"),
                tier="Standard",
            ),
        )
        
        # Firewall rule to allow Azure services
        firewall_rule = sql.FirewallRule(
            f"fw-{name}-azure",
            resource_group_name=self.rg_name,
            server_name=sql_server.name,
            start_ip_address="0.0.0.0",
            end_ip_address="0.0.0.0",  # Allow Azure services
        )
        
        self.node_index[node["id"]] = {
            "kind": "azure.sql",
            "server": sql_server,
            "database": db,
        }
        self._outputs[f"sql-{name}-serverName"] = sql_server.fully_qualified_domain_name
        self._outputs[f"sql-{name}-databaseName"] = db.name
        self._outputs[f"sql-{name}-connectionString"] = pulumi.Output.all(
            sql_server.fully_qualified_domain_name, db.name, admin_login, admin_password
        ).apply(lambda args: f"Server={args[0]};Database={args[1]};User Id={args[2]};Password={args[3]};")

    def _create_cosmos_db(self, node: Dict[str, Any]):
        """Create Azure Cosmos DB (DynamoDB equivalent) - NoSQL database"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # Cosmos DB Account
        account = cosmosdb.DatabaseAccount(
            f"cosmos-{name}",
            resource_group_name=self.rg_name,
            database_account_offer_type="Standard",
            locations=[cosmosdb.LocationArgs(
                location_name=self.location,
                failover_priority=0,
            )],
            consistency_policy=cosmosdb.ConsistencyPolicyArgs(
                default_consistency_level=cosmosdb.DefaultConsistencyLevel.SESSION,
            ),
            kind=props.get("kind", "GlobalDocumentDB"),  # MongoDB, Table, etc.
        )
        
        # Database
        database = cosmosdb.SqlResourceSqlDatabase(
            f"cosmosdb-{name}",
            resource_group_name=self.rg_name,
            account_name=account.name,
            resource=cosmosdb.SqlDatabaseResourceArgs(id=props.get("databaseName", f"db-{name}")),
        )
        
        # Container (like a table)
        container = cosmosdb.SqlResourceSqlContainer(
            f"cosmoscontainer-{name}",
            resource_group_name=self.rg_name,
            account_name=account.name,
            database_name=database.name,
            resource=cosmosdb.SqlContainerResourceArgs(
                id=props.get("containerName", f"container-{name}"),
                partition_key=cosmosdb.ContainerPartitionKeyArgs(
                    paths=[props.get("partitionKey", "/id")],
                    kind="Hash",
                ),
            ),
        )
        
        # Get connection strings
        keys = cosmosdb.list_database_account_keys_output(
            resource_group_name=self.rg_name,
            account_name=account.name,
        )
        
        self.node_index[node["id"]] = {
            "kind": "azure.cosmosdb",
            "account": account,
            "database": database,
            "container": container,
        }
        self._outputs[f"cosmosdb-{name}-endpoint"] = account.document_endpoint
        self._outputs[f"cosmosdb-{name}-primaryKey"] = keys.primary_master_key

    def _create_app_service(self, node: Dict[str, Any]):
        """Create Azure App Service (Elastic Beanstalk equivalent) - Web app hosting"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # App Service Plan
        plan = web.AppServicePlan(
            f"plan-{name}",
            resource_group_name=self.rg_name,
            kind="app",
            sku=web.SkuDescriptionArgs(
                name=props.get("sku", "F1"),  # Free tier
                tier=props.get("tier", "Free"),
            ),
        )
        
        # App Service
        site_config_args = web.SiteConfigArgs()
        
        # Set runtime only if specified and valid
        if props.get("osType") == "Linux" and props.get("runtime"):
            # Validate runtime format (e.g., "PYTHON|3.9" or "DOCKER|nginx")
            runtime = props.get("runtime")
            if "|" in runtime:
                site_config_args.linux_fx_version = runtime
        elif props.get("osType") == "Linux":
            # Default Python runtime for Linux
            site_config_args.linux_fx_version = "PYTHON|3.11"
        
        # Add environment variables
        if props.get("env"):
            site_config_args.app_settings = [
                web.NameValuePairArgs(name=k, value=str(v))
                for k, v in props.get("env", {}).items()
            ]
        
        app = web.WebApp(
            f"app-{name}",
            resource_group_name=self.rg_name,
            server_farm_id=plan.id,
            site_config=site_config_args,
        )
        
        self.node_index[node["id"]] = {
            "kind": "azure.appservice",
            "app": app,
            "plan": plan,
        }
        self._outputs[f"appservice-{name}-url"] = pulumi.Output.concat("https://", app.default_host_name)

    def _create_api_management(self, node: Dict[str, Any]):
        """Create Azure API Management (API Gateway equivalent) - API gateway service"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # API Management Service
        apim = apimanagement.ApiManagementService(
            f"apim-{name}",
            resource_group_name=self.rg_name,
            publisher_name=props.get("publisherName", "Contoso"),
            publisher_email=props.get("publisherEmail", "admin@contoso.com"),
            sku=apimanagement.ApiManagementServiceSkuPropertiesArgs(
                name=props.get("sku", "Developer"),  # Developer tier (cheapest)
                capacity=1,
            ),
        )
        
        self.node_index[node["id"]] = {
            "kind": "azure.apimanagement",
            "service": apim,
        }
        self._outputs[f"apimanagement-{name}-gatewayUrl"] = apim.gateway_url
        self._outputs[f"apimanagement-{name}-portalUrl"] = apim.portal_url

    def _create_key_vault(self, node: Dict[str, Any]):
        """Create Azure Key Vault (Secrets Manager equivalent) - Secrets management"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # Key Vault
        vault = keyvault.Vault(
            f"kv-{name}",
            resource_group_name=self.rg_name,
            properties=keyvault.VaultPropertiesArgs(
                tenant_id=props.get("tenantId", "00000000-0000-0000-0000-000000000000"),
                sku=keyvault.SkuArgs(
                    family="A",
                    name="standard",
                ),
                enabled_for_deployment=True,
                enabled_for_disk_encryption=True,
                enabled_for_template_deployment=True,
            ),
        )
        
        self.node_index[node["id"]] = {
            "kind": "azure.keyvault",
            "vault": vault,
        }
        self._outputs[f"keyvault-{name}-uri"] = vault.properties.vault_uri

    def _create_redis_cache(self, node: Dict[str, Any]):
        """Create Azure Redis Cache (ElastiCache equivalent) - In-memory cache"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # Redis Cache
        redis_cache = redis.Redis(
            f"redis-{name}",
            resource_group_name=self.rg_name,
            sku=redis.SkuArgs(
                name=props.get("sku", "Basic"),
                family=props.get("family", "C"),
                capacity=props.get("capacity", 0),  # Basic C0 (250MB)
            ),
            enable_non_ssl_port=False,
            minimum_tls_version="1.2",
        )
        
        # Get access keys
        keys = redis.list_redis_keys_output(
            resource_group_name=self.rg_name,
            name=redis_cache.name,
        )
        
        self.node_index[node["id"]] = {
            "kind": "azure.redis",
            "cache": redis_cache,
        }
        self._outputs[f"redis-{name}-hostname"] = redis_cache.host_name
        self._outputs[f"redis-{name}-port"] = redis_cache.port
        self._outputs[f"redis-{name}-primaryKey"] = keys.primary_key
        self._outputs[f"redis-{name}-sslPort"] = redis_cache.ssl_port

    def _create_application_insights(self, node: Dict[str, Any]):
        """Create Azure Application Insights (CloudWatch equivalent) - Application monitoring"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # Application Insights (without LogAnalytics ingestion mode to avoid workspace requirement)
        app_insights = applicationinsights.Component(
            f"appi-{name}",
            resource_group_name=self.rg_name,
            kind="web",
            application_type=applicationinsights.ApplicationType.WEB,
            ingestion_mode=applicationinsights.IngestionMode.APPLICATION_INSIGHTS,
        )
        
        self.node_index[node["id"]] = {
            "kind": "azure.appinsights",
            "insights": app_insights,
        }
        self._outputs[f"appinsights-{name}-instrumentationKey"] = app_insights.instrumentation_key
        self._outputs[f"appinsights-{name}-connectionString"] = app_insights.connection_string
        self._outputs[f"appinsights-{name}-appId"] = app_insights.app_id

    def _create_virtual_network(self, node: Dict[str, Any]):
        """Create Azure Virtual Network (VPC equivalent) - Network isolation"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # Virtual Network
        vnet = network.VirtualNetwork(
            f"vnet-{name}",
            resource_group_name=self.rg_name,
            address_space=network.AddressSpaceArgs(
                address_prefixes=props.get("addressSpaces", ["10.0.0.0/16"])
            ),
        )
        
        # Subnets
        subnets = []
        subnet_configs = props.get("subnets", [{"name": "default", "addressPrefix": "10.0.1.0/24"}])
        
        for i, subnet_config in enumerate(subnet_configs):
            subnet = network.Subnet(
                f"subnet-{name}-{i}",
                resource_group_name=self.rg_name,
                virtual_network_name=vnet.name,
                address_prefix=subnet_config.get("addressPrefix", "10.0.1.0/24"),
            )
            subnets.append(subnet)
        
        self.node_index[node["id"]] = {
            "kind": "azure.vnet",
            "vnet": vnet,
            "subnets": subnets,
        }
        self._outputs[f"vnet-{name}-id"] = vnet.id
        self._outputs[f"vnet-{name}-addressSpace"] = vnet.address_space.address_prefixes

    # -------------------- Edges --------------------
    def _connect(self, edge: Dict[str, Any]):
    # Accept both "from" (alias) and "from_" (field name), same for "to"
        from_id = edge.get("from") or edge.get("from_")
        to_id = edge.get("to") or edge.get("to_")
        intent = edge.get("intent", "notify")

        if not from_id or not to_id:
            pulumi.log.warn(f"Edge missing endpoints: {edge}; skipping")
            return

        src = self.node_index.get(from_id) or {}
        dst = self.node_index.get(to_id) or {}

        if intent != "notify":
            pulumi.log.warn(f"Unsupported intent: {intent}; skipping")
            return

        if src.get("kind") == "azure.storage" and dst.get("kind") == "azure.servicebus":
            acct = src["account"]
            queue = dst["queue"]

            # Use stable, plain string for resource name (avoid Outputs in names)
            sub_name = f"egsub-{safe_name(from_id)}-to-{safe_name(to_id)}"

            eventgrid.EventSubscription(
                sub_name,
                scope=acct.id,
                destination=eventgrid.ServiceBusQueueEventSubscriptionDestinationArgs(
                    resource_id=queue.id,
                    endpoint_type="ServiceBusQueue",
                ),
                event_delivery_schema="EventGridSchema",
                filter=eventgrid.EventSubscriptionFilterArgs(
                    included_event_types=["Microsoft.Storage.BlobCreated"],
                ),
            )


        elif src.get("kind") == "azure.servicebus" and dst.get("kind") == "azure.containerapp":
            # Export bindings; extend to inject as secrets/env if desired
            pulumi.export(f"bind-{safe_name(to_id)}-queue", src["queue"].name)
            pulumi.export(f"bind-{safe_name(to_id)}-conn", src["connectionString"])

        elif src.get("kind") == "azure.servicebus" and dst.get("kind") == "azure.functionapp":
            # Export Service Bus connection for Function App
            pulumi.export(f"bind-{safe_name(to_id)}-queue", src["queue"].name)
            pulumi.export(f"bind-{safe_name(to_id)}-conn", src["connectionString"])

        elif src.get("kind") == "azure.functionapp" and dst.get("kind") == "azure.appservice":
            # Export Function App URL for App Service
            func_url = pulumi.Output.concat("https://", src["app"].default_host_name)
            pulumi.export(f"bind-{safe_name(to_id)}-functionUrl", func_url)

        else:
            pulumi.log.warn(f"No connector for {src.get('kind')} -> {dst.get('kind')}; skipping")
