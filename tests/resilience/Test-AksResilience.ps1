$ErrorActionPreference = 'Stop'

$manifest = & helm.exe template storage-demo ./helm/storage-demo -f ./gitops/environments/dev/values.yaml
if ($LASTEXITCODE -ne 0) {
    throw 'Helm rendering failed.'
}

$documents = ($manifest -join "`n") -split '(?m)^---\s*$'

function Get-Resource {
    param([string]$Kind)

    $resources = @(
        $documents | Where-Object {
            $_ -match "(?m)^kind:\s*$([regex]::Escape($Kind))\s*$"
        }
    )

    if ($resources.Count -ne 1) {
        throw "Expected exactly one $Kind; found $($resources.Count)."
    }

    return $resources[0]
}

$deployment = Get-Resource 'Deployment'
$hpa = Get-Resource 'HorizontalPodAutoscaler'
$pdb = Get-Resource 'PodDisruptionBudget'

$checks = [ordered]@{
    'Deployment replicas managed by HPA' = ($deployment -notmatch '(?m)^\s*replicas:')
    'Required pod anti-affinity' = ($deployment -match 'requiredDuringSchedulingIgnoredDuringExecution:')
    'Hostname topology key' = ($deployment -match 'topologyKey:\s*kubernetes\.io/hostname')
    'Deployment maxSurge = 0' = ($deployment -match 'maxSurge:\s*0')
    'Deployment maxUnavailable = 1' = ($deployment -match 'maxUnavailable:\s*1')
    'PDB exists' = ($null -ne $pdb)
    'PDB minAvailable = 1' = ($pdb -match 'minAvailable:\s*1')
    'HPA exists' = ($null -ne $hpa)
    'HPA minReplicas = 2' = ($hpa -match 'minReplicas:\s*2')
    'HPA maxReplicas = 3' = ($hpa -match 'maxReplicas:\s*3')
}

$failed = 0
foreach ($check in $checks.GetEnumerator()) {
    if ($check.Value) {
        Write-Host "PASS: $($check.Key)"
    } else {
        Write-Host "FAIL: $($check.Key)"
        $failed++
    }
}

if ($failed -gt 0) {
    throw "B6.23: $failed resilience checks failed."
}

Write-Host 'B6.23: All 10 resource-aware resilience checks passed.'
