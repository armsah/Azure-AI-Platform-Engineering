resource "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = var.cluster_name
  kubernetes_version  = var.kubernetes_version
  zones               = ["1", "2", "3"]

  identity {
    type = "SystemAssigned"
  }

  default_node_pool {
    name                 = "system"
    vm_size              = "Standard_D2s_v3"
    auto_scaling_enabled = true
    min_count            = 2
    max_count            = 3

    only_critical_addons_enabled = true
  }

  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_policy      = "azure"
    load_balancer_sku   = "standard"
  }

  role_based_access_control_enabled = true

}

resource "azurerm_kubernetes_cluster_node_pool" "user" {
  name                  = "apps"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = "Standard_D2s_v3"
  zones                 = ["1", "2", "3"]

  auto_scaling_enabled = true
  min_count            = 2
  max_count            = 5

  node_labels = {
    workload = "applications"
  }

  node_taints = [
    "workload=applications:NoSchedule"
  ]
}