$ErrorActionPreference = "Stop"

Push-Location python\storage-demo

try {
    python -m compileall .
    python -m pytest -q
}
finally {
    Pop-Location
}