# B8.2 FinOps — Azure Operational Evidence

## Evidence status

- Requirement: B8.2-finops
- Status: PARTIAL
- Observation date: 2026-10-14
- Environment: Azure_Armen_Sub
- Evidence source: Read-only Azure CLI and Cost Management API queries.
- Review status: Pending independent acceptance review.

## Verified Azure budget

Budget name: budget-azure-learning-20eur

Scope: Azure subscription

Monthly amount: EUR 20

Configured notifications:

| Notification | Threshold | Recipient | Enabled |
| --- | --- | --- | --- |
| Actual spending | 80% (EUR 16) | Owner role | Yes |
| Forecast spending | 100% (EUR 20) | Owner role | Yes |

Verification method:

- Azure Consumption budget inventory.
- Azure Resource Manager GET request using Microsoft.Consumption/budgets.
- API response confirmed the budget amount, scope, notification thresholds, and enabled state.

An existing EUR 80 budget named budget-pricing-api-dev remains
configured for resource group rg-pricing-api-dev-weu.

## Observed Azure costs

Azure Cost Management query:

- Cost type: ActualCost
- Timeframe: MonthToDate
- Grouping: ResourceGroupName
- Currency: EUR

| Resource group | Observed cost (EUR) |
| --- | ---: |
| mc_rg-terraform-learning_aks-armen-learning-2026_northeurope | 5.3590337 |
| rg-terraform-learning | 0.3032317 |
| rg-tfstate-learning | 0.0000269 |
| Total returned | Approximately 5.6623 |

These figures are a point-in-time observation, not a forecast
or a guaranteed final monthly invoice.

## AKS safety

Cluster: aks-armen-learning-2026

Resource group: rg-terraform-learning

Observed power state: Stopped

No cluster restart, application deployment, or infrastructure
provisioning was performed during evidence collection.

## Outstanding acceptance requirements

- Verify that budget notifications are actually delivered.
- Validate Azure pricing assumptions and forecast accuracy.
- Document and review budget-exception approvals.
- Define and validate spending controls beyond budget notifications.
- Obtain independent reviewer sign-off.

Azure budget notifications do not impose a hard spending cap.

B8.2-finops remains PARTIAL until the outstanding acceptance
requirements are independently verified.
