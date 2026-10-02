resource "azurerm_resource_group" "learning" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    environment = "learning"
    managed_by  = "terraform"
  }
}