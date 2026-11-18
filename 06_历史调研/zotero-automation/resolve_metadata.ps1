$ErrorActionPreference = 'Stop'
$base = Split-Path $PSScriptRoot
$seeds = Get-Content (Join-Path $PSScriptRoot 'inputs/incoming/2026-09-06-janus-seeds.json') -Raw | ConvertFrom-Json
foreach ($seed in $seeds) {
    $dest = Join-Path $base ('research/reading_route/metadata/' + $seed.order + '.json')
    if (Test-Path -LiteralPath $dest) { continue }
    $query = if ($seed.doi) { 'DOI:' + $seed.doi } else { 'TITLE:"' + $seed.title + '"' }
    try {
        $uri = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&query=' + [Uri]::EscapeDataString($query)
        $data = Invoke-RestMethod -Uri $uri -TimeoutSec 30
        $hit = $data.resultList.result | Select-Object -First 1
        if (-not $hit) { throw 'No match' }
        if ($seed.doi -and $seed.doi -ne $hit.doi) { throw 'DOI mismatch' }
        $hit | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $dest -Encoding utf8
        Write-Output "$($seed.order) $($hit.doi) $($hit.title)"
    } catch { Write-Output "$($seed.order) unresolved: $($_.Exception.Message)" }
}
