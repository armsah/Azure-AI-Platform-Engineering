$ErrorActionPreference = "Stop"

$chart = "helm/storage-demo"
$devValues = "gitops/environments/dev/values.yaml"

$manifest = helm template storage-demo $chart -f $devValues

if ($LASTEXITCODE -ne 0) {
    throw "FAIL: Helm dev template rendering"
}

$checks = [ordered]@{
    "Two dev replicas"                  = 'replicas:\s*2'
    "Required pod anti-affinity"        = 'requiredDuringSchedulingIgnoredDuringExecution:'
    "Node-level separation"            = 'topologyKey:\s*kubernetes.io/hostname'
    "No rollout surge"                 = 'maxSurge:\s*0'
    "One unavailable during rollout"   = 'maxUnavailable:\s*1'
    "PodDisruptionBudget present"       = 'kind:\s*PodDisruptionBudget'
    "PDB minimum available one"         = 'minAvailable:\s*1'
    "HorizontalPodAutoscaler present"   = 'kind:\s*HorizontalPodAutoscaler'
    "HPA minimum two replicas"          = 'minReplicas:\s*2'
    "HPA maximum three replicas"        = 'maxReplicas:\s*3'
}

$failed = 0

foreach ($check in $checks.GetEnumerator()) {
    if ($manifest -match $check.Value) {
        Write-Host "PASS: $($check.Key)" -ForegroundColor Green
    }
    else {
        Write-Host "FAIL: $($check.Key)" -ForegroundColor Red
        $failed++
    }
}

if ($failed -gt 0) {
    throw "$failed resilience checks failed."
}

Write-Host "B6.18: All dev resilience checks passed." -ForegroundColor Green
