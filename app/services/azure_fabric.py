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
        # DynamoDB → azure.cosmosdb, API Gateway → azure.apimanagement, 
        # Secrets Manager → azure.keyvault, CloudWatch → azure.appinsights, VPC → azure.vnet
        self._service_registry: Dict[str, callable] = {
            "azure.storage": self._create_storage,  # S3 equivalent
            "azure.servicebus": self._create_servicebus,  # SQS equivalent
            "azure.containerapp": self._create_container_app,  # ECS/Fargate equivalent
            "azure.vm": self._create_virtual_machine,  # EC2 equivalent
            "azure.functionapp": self._create_function_app,  # Lambda equivalent
            "azure.sql": self._create_sql_database,  # RDS equivalent
            "azure.cosmosdb": self._create_cosmos_db,  # DynamoDB equivalent
            "azure.apimanagement": self._create_api_management,  # API Gateway equivalent
            "azure.keyvault": self._create_key_vault,  # Secrets Manager equivalent
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
        
        # App Service Plan for Function App (Consumption plan)
        sku_name = props.get("sku", "Y1")
        plan = web.AppServicePlan(
            f"plan-{name}",
            resource_group_name=self.rg_name,
            kind="FunctionApp",
            reserved=True,  # Required for Linux Function Apps
            sku=web.SkuDescriptionArgs(
                name=sku_name,  # Y1 = Consumption plan
                tier="Dynamic" if sku_name == "Y1" else "ElasticPremium",
            ),
        )
        
        # Function App
        func_app = web.WebApp(
            f"func-{name}",
            resource_group_name=self.rg_name,
            server_farm_id=plan.id,
            kind="functionapp",  # Explicitly set kind
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
        
        # Database - ensure name consistency
        # Use the databaseName from props, or derive from node name/id
        db_name = props.get("databaseName")
        if not db_name:
            # If no databaseName provided, use a safe version of the node name/id
            db_name = safe_name(node.get("name") or node["id"])[:40]
            # Remove any prefixes that might have been added
            if db_name.startswith("cosmos-") or db_name.startswith("cosmosdb-"):
                db_name = db_name.replace("cosmos-", "").replace("cosmosdb-", "")
            if not db_name.startswith("db-"):
                db_name = f"db-{db_name}"
        
        # Database - use db_name for database ID, and also as database_name parameter
        # The database_name parameter (used in URI) should match the id in the resource body
        database = cosmosdb.SqlResourceSqlDatabase(
            f"cosmosdb-{name}",
            resource_group_name=self.rg_name,
            account_name=account.name,
            database_name=db_name,  # This is used in the URI path
            resource=cosmosdb.SqlDatabaseResourceArgs(id=db_name),  # This is the database ID
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

    def _create_api_management(self, node: Dict[str, Any]):
        """Create Azure API Management (API Gateway equivalent) - API gateway service"""
        name = safe_name(node.get("name") or node["id"])[:40]
        props = node.get("props", {})
        
        # Handle SKU - can be string or object
        sku_prop = props.get("sku", "Developer")
        if isinstance(sku_prop, dict):
            sku_name = sku_prop.get("name", "Developer")
            sku_capacity = sku_prop.get("capacity", 1)
        else:
            # If it's a string, use it as the SKU name
            sku_name = sku_prop if isinstance(sku_prop, str) else "Developer"
            sku_capacity = 1
        
        # API Management Service
        # Note: Developer SKU has restrictions on some settings
        apim = apimanagement.ApiManagementService(
            f"apim-{name}",
            resource_group_name=self.rg_name,
            publisher_name=props.get("publisherName", "Contoso"),
            publisher_email=props.get("publisherEmail", "admin@contoso.com"),
            sku=apimanagement.ApiManagementServiceSkuPropertiesArgs(
                name=sku_name,
                capacity=sku_capacity if sku_name != "Consumption" else None,
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

        elif src.get("kind") == "azure.keyvault" and dst.get("kind") == "azure.functionapp":
            # Key Vault → Function App: Export Key Vault URI for Function App to use
            vault_uri = src["vault"].properties.vault_uri
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-uri", vault_uri)
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-name", src["vault"].name)

        elif src.get("kind") == "azure.keyvault" and dst.get("kind") == "azure.containerapp":
            # Key Vault → Container App: Export Key Vault URI
            vault_uri = src["vault"].properties.vault_uri
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-uri", vault_uri)
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-name", src["vault"].name)

        elif src.get("kind") == "azure.cosmosdb" and dst.get("kind") == "azure.functionapp":
            # Cosmos DB → Function App: Export connection info
            endpoint = src["account"].document_endpoint
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-endpoint", endpoint)
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-database", src["database"].name)
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-container", src["container"].name)

        elif src.get("kind") == "azure.cosmosdb" and dst.get("kind") == "azure.containerapp":
            # Cosmos DB → Container App: Export connection info
            endpoint = src["account"].document_endpoint
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-endpoint", endpoint)
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-database", src["database"].name)
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-container", src["container"].name)

        elif src.get("kind") == "azure.sql" and dst.get("kind") == "azure.functionapp":
            # SQL → Function App: Export connection string
            server_fqdn = src["server"].fully_qualified_domain_name
            db_name = src["database"].name
            pulumi.export(f"bind-{safe_name(to_id)}-sql-server", server_fqdn)
            pulumi.export(f"bind-{safe_name(to_id)}-sql-database", db_name)

        elif src.get("kind") == "azure.sql" and dst.get("kind") == "azure.containerapp":
            # SQL → Container App: Export connection info
            server_fqdn = src["server"].fully_qualified_domain_name
            db_name = src["database"].name
            pulumi.export(f"bind-{safe_name(to_id)}-sql-server", server_fqdn)
            pulumi.export(f"bind-{safe_name(to_id)}-sql-database", db_name)

        elif src.get("kind") == "azure.storage" and dst.get("kind") == "azure.functionapp":
            # Storage → Function App: Export storage connection for blob triggers
            storage_conn = src["connectionString"]
            pulumi.export(f"bind-{safe_name(to_id)}-storage-conn", storage_conn)
            pulumi.export(f"bind-{safe_name(to_id)}-storage-account", src["account"].name)

        elif src.get("kind") == "azure.storage" and dst.get("kind") == "azure.containerapp":
            # Storage → Container App: Export storage connection
            storage_conn = src["connectionString"]
            pulumi.export(f"bind-{safe_name(to_id)}-storage-conn", storage_conn)
            pulumi.export(f"bind-{safe_name(to_id)}-storage-account", src["account"].name)

        elif src.get("kind") == "azure.appinsights" and dst.get("kind") == "azure.functionapp":
            # App Insights → Function App: Export instrumentation key
            app_insights = src["insights"]
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-key", app_insights.instrumentation_key)
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-conn", app_insights.connection_string)

        elif src.get("kind") == "azure.appinsights" and dst.get("kind") == "azure.containerapp":
            # App Insights → Container App: Export instrumentation key
            app_insights = src["insights"]
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-key", app_insights.instrumentation_key)
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-conn", app_insights.connection_string)

        elif src.get("kind") == "azure.apimanagement" and dst.get("kind") == "azure.functionapp":
            # API Management → Function App: Export API Management gateway URL
            apim = src["service"]
            pulumi.export(f"bind-{safe_name(to_id)}-apim-gateway", apim.gateway_url)
            pulumi.export(f"bind-{safe_name(to_id)}-apim-portal", apim.portal_url)

        elif src.get("kind") == "azure.apimanagement" and dst.get("kind") == "azure.containerapp":
            # API Management → Container App: Export gateway URL
            apim = src["service"]
            pulumi.export(f"bind-{safe_name(to_id)}-apim-gateway", apim.gateway_url)
            pulumi.export(f"bind-{safe_name(to_id)}-apim-portal", apim.portal_url)

        # Storage → Other Services
        elif src.get("kind") == "azure.storage" and dst.get("kind") == "azure.sql":
            # Storage → SQL: Export storage connection for backups/data import
            storage_conn = src["connectionString"]
            pulumi.export(f"bind-{safe_name(to_id)}-storage-conn", storage_conn)
            pulumi.export(f"bind-{safe_name(to_id)}-storage-account", src["account"].name)

        elif src.get("kind") == "azure.storage" and dst.get("kind") == "azure.cosmosdb":
            # Storage → Cosmos DB: Export storage connection for backups/data import
            storage_conn = src["connectionString"]
            pulumi.export(f"bind-{safe_name(to_id)}-storage-conn", storage_conn)
            pulumi.export(f"bind-{safe_name(to_id)}-storage-account", src["account"].name)

        elif src.get("kind") == "azure.storage" and dst.get("kind") == "azure.vm":
            # Storage → VM: Export storage connection for VM disk/file shares
            storage_conn = src["connectionString"]
            pulumi.export(f"bind-{safe_name(to_id)}-storage-conn", storage_conn)
            pulumi.export(f"bind-{safe_name(to_id)}-storage-account", src["account"].name)

        elif src.get("kind") == "azure.storage" and dst.get("kind") == "azure.apimanagement":
            # Storage → API Management: Export storage connection for API documentation
            storage_conn = src["connectionString"]
            pulumi.export(f"bind-{safe_name(to_id)}-storage-conn", storage_conn)
            pulumi.export(f"bind-{safe_name(to_id)}-storage-account", src["account"].name)

        # Service Bus → Other Services
        elif src.get("kind") == "azure.servicebus" and dst.get("kind") == "azure.sql":
            # Service Bus → SQL: Export queue info for database notifications
            pulumi.export(f"bind-{safe_name(to_id)}-queue", src["queue"].name)
            pulumi.export(f"bind-{safe_name(to_id)}-conn", src["connectionString"])

        elif src.get("kind") == "azure.servicebus" and dst.get("kind") == "azure.cosmosdb":
            # Service Bus → Cosmos DB: Export queue info for database notifications
            pulumi.export(f"bind-{safe_name(to_id)}-queue", src["queue"].name)
            pulumi.export(f"bind-{safe_name(to_id)}-conn", src["connectionString"])

        elif src.get("kind") == "azure.servicebus" and dst.get("kind") == "azure.vm":
            # Service Bus → VM: Export queue info for VM notifications
            pulumi.export(f"bind-{safe_name(to_id)}-queue", src["queue"].name)
            pulumi.export(f"bind-{safe_name(to_id)}-conn", src["connectionString"])

        elif src.get("kind") == "azure.servicebus" and dst.get("kind") == "azure.apimanagement":
            # Service Bus → API Management: Export queue info for API events
            pulumi.export(f"bind-{safe_name(to_id)}-queue", src["queue"].name)
            pulumi.export(f"bind-{safe_name(to_id)}-conn", src["connectionString"])

        # Database → Other Services
        elif src.get("kind") == "azure.sql" and dst.get("kind") == "azure.storage":
            # SQL → Storage: Export SQL info for backups
            server_fqdn = src["server"].fully_qualified_domain_name
            db_name = src["database"].name
            pulumi.export(f"bind-{safe_name(to_id)}-sql-server", server_fqdn)
            pulumi.export(f"bind-{safe_name(to_id)}-sql-database", db_name)

        elif src.get("kind") == "azure.sql" and dst.get("kind") == "azure.servicebus":
            # SQL → Service Bus: Export SQL info for database events
            server_fqdn = src["server"].fully_qualified_domain_name
            db_name = src["database"].name
            pulumi.export(f"bind-{safe_name(to_id)}-sql-server", server_fqdn)
            pulumi.export(f"bind-{safe_name(to_id)}-sql-database", db_name)

        elif src.get("kind") == "azure.cosmosdb" and dst.get("kind") == "azure.storage":
            # Cosmos DB → Storage: Export Cosmos info for backups
            endpoint = src["account"].document_endpoint
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-endpoint", endpoint)
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-database", src["database"].name)

        elif src.get("kind") == "azure.cosmosdb" and dst.get("kind") == "azure.servicebus":
            # Cosmos DB → Service Bus: Export Cosmos info for database events
            endpoint = src["account"].document_endpoint
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-endpoint", endpoint)
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-database", src["database"].name)

        # Key Vault → Other Services
        elif src.get("kind") == "azure.keyvault" and dst.get("kind") == "azure.sql":
            # Key Vault → SQL: Export Key Vault URI for database credentials
            vault_uri = src["vault"].properties.vault_uri
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-uri", vault_uri)
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-name", src["vault"].name)

        elif src.get("kind") == "azure.keyvault" and dst.get("kind") == "azure.cosmosdb":
            # Key Vault → Cosmos DB: Export Key Vault URI for database credentials
            vault_uri = src["vault"].properties.vault_uri
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-uri", vault_uri)
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-name", src["vault"].name)

        elif src.get("kind") == "azure.keyvault" and dst.get("kind") == "azure.vm":
            # Key Vault → VM: Export Key Vault URI for VM secrets
            vault_uri = src["vault"].properties.vault_uri
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-uri", vault_uri)
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-name", src["vault"].name)

        elif src.get("kind") == "azure.keyvault" and dst.get("kind") == "azure.apimanagement":
            # Key Vault → API Management: Export Key Vault URI for API keys
            vault_uri = src["vault"].properties.vault_uri
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-uri", vault_uri)
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-name", src["vault"].name)

        elif src.get("kind") == "azure.keyvault" and dst.get("kind") == "azure.storage":
            # Key Vault → Storage: Export Key Vault URI for storage account keys
            vault_uri = src["vault"].properties.vault_uri
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-uri", vault_uri)
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-name", src["vault"].name)

        elif src.get("kind") == "azure.keyvault" and dst.get("kind") == "azure.servicebus":
            # Key Vault → Service Bus: Export Key Vault URI for queue credentials
            vault_uri = src["vault"].properties.vault_uri
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-uri", vault_uri)
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-name", src["vault"].name)

        # App Insights → Other Services
        elif src.get("kind") == "azure.appinsights" and dst.get("kind") == "azure.sql":
            # App Insights → SQL: Export instrumentation for database monitoring
            app_insights = src["insights"]
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-key", app_insights.instrumentation_key)
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-conn", app_insights.connection_string)

        elif src.get("kind") == "azure.appinsights" and dst.get("kind") == "azure.cosmosdb":
            # App Insights → Cosmos DB: Export instrumentation for database monitoring
            app_insights = src["insights"]
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-key", app_insights.instrumentation_key)
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-conn", app_insights.connection_string)

        elif src.get("kind") == "azure.appinsights" and dst.get("kind") == "azure.vm":
            # App Insights → VM: Export instrumentation for VM monitoring
            app_insights = src["insights"]
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-key", app_insights.instrumentation_key)
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-conn", app_insights.connection_string)

        elif src.get("kind") == "azure.appinsights" and dst.get("kind") == "azure.apimanagement":
            # App Insights → API Management: Export instrumentation for API monitoring
            app_insights = src["insights"]
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-key", app_insights.instrumentation_key)
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-conn", app_insights.connection_string)

        elif src.get("kind") == "azure.appinsights" and dst.get("kind") == "azure.storage":
            # App Insights → Storage: Export instrumentation for storage monitoring
            app_insights = src["insights"]
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-key", app_insights.instrumentation_key)
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-conn", app_insights.connection_string)

        elif src.get("kind") == "azure.appinsights" and dst.get("kind") == "azure.servicebus":
            # App Insights → Service Bus: Export instrumentation for queue monitoring
            app_insights = src["insights"]
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-key", app_insights.instrumentation_key)
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-conn", app_insights.connection_string)

        # API Management → Other Services
        elif src.get("kind") == "azure.apimanagement" and dst.get("kind") == "azure.sql":
            # API Management → SQL: Export gateway URL for database APIs
            apim = src["service"]
            pulumi.export(f"bind-{safe_name(to_id)}-apim-gateway", apim.gateway_url)
            pulumi.export(f"bind-{safe_name(to_id)}-apim-portal", apim.portal_url)

        elif src.get("kind") == "azure.apimanagement" and dst.get("kind") == "azure.cosmosdb":
            # API Management → Cosmos DB: Export gateway URL for database APIs
            apim = src["service"]
            pulumi.export(f"bind-{safe_name(to_id)}-apim-gateway", apim.gateway_url)
            pulumi.export(f"bind-{safe_name(to_id)}-apim-portal", apim.portal_url)

        elif src.get("kind") == "azure.apimanagement" and dst.get("kind") == "azure.vm":
            # API Management → VM: Export gateway URL for VM APIs
            apim = src["service"]
            pulumi.export(f"bind-{safe_name(to_id)}-apim-gateway", apim.gateway_url)
            pulumi.export(f"bind-{safe_name(to_id)}-apim-portal", apim.portal_url)

        elif src.get("kind") == "azure.apimanagement" and dst.get("kind") == "azure.storage":
            # API Management → Storage: Export gateway URL for storage APIs
            apim = src["service"]
            pulumi.export(f"bind-{safe_name(to_id)}-apim-gateway", apim.gateway_url)
            pulumi.export(f"bind-{safe_name(to_id)}-apim-portal", apim.portal_url)

        elif src.get("kind") == "azure.apimanagement" and dst.get("kind") == "azure.servicebus":
            # API Management → Service Bus: Export gateway URL for queue APIs
            apim = src["service"]
            pulumi.export(f"bind-{safe_name(to_id)}-apim-gateway", apim.gateway_url)
            pulumi.export(f"bind-{safe_name(to_id)}-apim-portal", apim.portal_url)

        # VNet → All Services (Network connectivity)
        elif src.get("kind") == "azure.vnet" and dst.get("kind") == "azure.vm":
            # VNet → VM: Export VNet info for VM networking
            vnet = src["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        elif src.get("kind") == "azure.vnet" and dst.get("kind") == "azure.containerapp":
            # VNet → Container App: Export VNet info for container networking
            vnet = src["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        elif src.get("kind") == "azure.vnet" and dst.get("kind") == "azure.functionapp":
            # VNet → Function App: Export VNet info for function networking
            vnet = src["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        elif src.get("kind") == "azure.vnet" and dst.get("kind") == "azure.sql":
            # VNet → SQL: Export VNet info for database networking
            vnet = src["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        elif src.get("kind") == "azure.vnet" and dst.get("kind") == "azure.cosmosdb":
            # VNet → Cosmos DB: Export VNet info for database networking
            vnet = src["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        elif src.get("kind") == "azure.vnet" and dst.get("kind") == "azure.storage":
            # VNet → Storage: Export VNet info for storage networking
            vnet = src["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        elif src.get("kind") == "azure.vnet" and dst.get("kind") == "azure.servicebus":
            # VNet → Service Bus: Export VNet info for queue networking
            vnet = src["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        elif src.get("kind") == "azure.vnet" and dst.get("kind") == "azure.apimanagement":
            # VNet → API Management: Export VNet info for API gateway networking
            vnet = src["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        elif src.get("kind") == "azure.vnet" and dst.get("kind") == "azure.keyvault":
            # VNet → Key Vault: Export VNet info for key vault networking
            vnet = src["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        elif src.get("kind") == "azure.vnet" and dst.get("kind") == "azure.appinsights":
            # VNet → App Insights: Export VNet info (for reference)
            vnet = src["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        # Function App ↔ Container App connections
        elif src.get("kind") == "azure.functionapp" and dst.get("kind") == "azure.containerapp":
            # Function App → Container App: Export Function App URL for Container App to call
            func_app = src["app"]
            func_url = pulumi.Output.concat("https://", func_app.default_host_name)
            pulumi.export(f"bind-{safe_name(to_id)}-functionapp-url", func_url)
            pulumi.export(f"bind-{safe_name(to_id)}-functionapp-name", func_app.name)

        elif src.get("kind") == "azure.containerapp" and dst.get("kind") == "azure.functionapp":
            # Container App → Function App: Export Container App FQDN for Function App to call
            container_app = src["app"]
            container_fqdn = container_app.configuration.apply(
                lambda c: c.ingress.fqdn if c and c.ingress else None
            )
            pulumi.export(f"bind-{safe_name(to_id)}-containerapp-fqdn", container_fqdn)
            pulumi.export(f"bind-{safe_name(to_id)}-containerapp-name", container_app.name)

        # VM → All Services (VM can connect to everything)
        elif src.get("kind") == "azure.vm" and dst.get("kind") == "azure.storage":
            # VM → Storage: Export storage connection for VM to access
            storage_conn = dst["connectionString"]
            pulumi.export(f"bind-{safe_name(to_id)}-storage-conn", storage_conn)
            pulumi.export(f"bind-{safe_name(to_id)}-storage-account", dst["account"].name)

        elif src.get("kind") == "azure.vm" and dst.get("kind") == "azure.servicebus":
            # VM → Service Bus: Export queue connection for VM
            pulumi.export(f"bind-{safe_name(to_id)}-queue", dst["queue"].name)
            pulumi.export(f"bind-{safe_name(to_id)}-conn", dst["connectionString"])

        elif src.get("kind") == "azure.vm" and dst.get("kind") == "azure.containerapp":
            # VM → Container App: Export Container App FQDN for VM to call
            container_app = dst["app"]
            container_fqdn = container_app.configuration.apply(
                lambda c: c.ingress.fqdn if c and c.ingress else None
            )
            pulumi.export(f"bind-{safe_name(to_id)}-containerapp-fqdn", container_fqdn)
            pulumi.export(f"bind-{safe_name(to_id)}-containerapp-name", container_app.name)

        elif src.get("kind") == "azure.vm" and dst.get("kind") == "azure.functionapp":
            # VM → Function App: Export Function App URL for VM to call
            func_app = dst["app"]
            func_url = pulumi.Output.concat("https://", func_app.default_host_name)
            pulumi.export(f"bind-{safe_name(to_id)}-functionapp-url", func_url)
            pulumi.export(f"bind-{safe_name(to_id)}-functionapp-name", func_app.name)

        elif src.get("kind") == "azure.vm" and dst.get("kind") == "azure.sql":
            # VM → SQL: Export SQL connection info for VM
            server_fqdn = dst["server"].fully_qualified_domain_name
            db_name = dst["database"].name
            pulumi.export(f"bind-{safe_name(to_id)}-sql-server", server_fqdn)
            pulumi.export(f"bind-{safe_name(to_id)}-sql-database", db_name)

        elif src.get("kind") == "azure.vm" and dst.get("kind") == "azure.cosmosdb":
            # VM → Cosmos DB: Export Cosmos connection info for VM
            endpoint = dst["account"].document_endpoint
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-endpoint", endpoint)
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-database", dst["database"].name)
            pulumi.export(f"bind-{safe_name(to_id)}-cosmos-container", dst["container"].name)

        elif src.get("kind") == "azure.vm" and dst.get("kind") == "azure.keyvault":
            # VM → Key Vault: Export Key Vault URI for VM
            vault_uri = dst["vault"].properties.vault_uri
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-uri", vault_uri)
            pulumi.export(f"bind-{safe_name(to_id)}-keyvault-name", dst["vault"].name)

        elif src.get("kind") == "azure.vm" and dst.get("kind") == "azure.appinsights":
            # VM → App Insights: Export instrumentation for VM monitoring
            app_insights = dst["insights"]
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-key", app_insights.instrumentation_key)
            pulumi.export(f"bind-{safe_name(to_id)}-appinsights-conn", app_insights.connection_string)

        elif src.get("kind") == "azure.vm" and dst.get("kind") == "azure.apimanagement":
            # VM → API Management: Export gateway URL for VM
            apim = dst["service"]
            pulumi.export(f"bind-{safe_name(to_id)}-apim-gateway", apim.gateway_url)
            pulumi.export(f"bind-{safe_name(to_id)}-apim-portal", apim.portal_url)

        elif src.get("kind") == "azure.vm" and dst.get("kind") == "azure.vnet":
            # VM → VNet: Export VNet info (VM is already in the VNet, but export for reference)
            vnet = dst["vnet"]
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-id", vnet.id)
            pulumi.export(f"bind-{safe_name(to_id)}-vnet-name", vnet.name)

        else:
            pulumi.log.warn(f"No connector for {src.get('kind')} -> {dst.get('kind')}; skipping")
