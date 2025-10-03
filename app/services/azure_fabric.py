from __future__ import annotations
from typing import Dict, Any
import pulumi
from pulumi_azure_native import (
    storage,
    servicebus,
    eventgrid,
    operationalinsights,
    app as containerapp,
)
from .naming import safe_name


class AzureFabric:
    def __init__(self, rg_name: pulumi.Output[str], location: str):
        self.rg_name = rg_name
        self.location = location
        self.node_index: Dict[str, Dict[str, Any]] = {}
        self._outputs: Dict[str, pulumi.Output[Any]] = {}

    def outputs(self) -> Dict[str, pulumi.Output[Any]]:
        return self._outputs

    def apply_ir(self, ir: Dict[str, Any]):
        nodes = ir.get("nodes", [])
        edges = ir.get("edges", [])
        for n in nodes:
            kind = n.get("kind")
            if kind == "azure.storage":
                self._create_storage(n)
            elif kind == "azure.servicebus":
                self._create_servicebus(n)
            elif kind == "azure.containerapp":
                self._create_container_app(n)
            else:
                raise ValueError(f"Unsupported kind: {kind}")
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

        else:
            pulumi.log.warn(f"No connector for {src.get('kind')} -> {dst.get('kind')}; skipping")
