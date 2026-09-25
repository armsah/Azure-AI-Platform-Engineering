terraform {
  required_version = ">= 1.10.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "rg-tfstate-learning"
    storage_account_name = "sttfarmen246536"
    container_name       = "tfstate"
    key                  = "storage-demo/dev.tfstate"
    use_azuread_auth     = true
  }
}

