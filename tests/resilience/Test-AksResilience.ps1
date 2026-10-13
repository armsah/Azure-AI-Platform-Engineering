$ErrorActionPreference = "Stop"

$chart = "helm/storage-demo"
$manifest = helm template storage-demo $chart

if ($LASTEXITCODE -ne 0) {
    throw "FAIL: Helm template rendering"
}

$checks = @{
    "Two replicas configured" = 'replicas:\s*2'
    "Required pod anti-affinity" = 'requiredDuringSchedulingIgnoredDuringExecution:'
    "Node-level separation" = 'topologyKey:\s*kubernetes.io/hostname'
    "No rollout surge" = 'maxSurge:\s*0'
    "One unavailable replica permitted" = 'maxUnavailable:\s*1'
    "PodDisruptionBudget present" = 'kind:\s*PodDisruptionBudget'
    "Minimum one available replica" = 'minAvailable:\s*1'
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

Write-Host "B6.16: All resilience configuration checks passed." -ForegroundColor Green
