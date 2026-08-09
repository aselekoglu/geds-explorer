$ErrorActionPreference = 'Stop'
$secretPath = Join-Path $env:APPDATA 'GEDS Explorer\neon-import-url.dpapi'
$cipher = Get-Content -LiteralPath $secretPath -Raw | ConvertTo-SecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($cipher)
try {
    $env:GEDS_PUBLIC_DATABASE_URL_UNPOOLED = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    py.exe (Join-Path $PSScriptRoot '..\work\geds-crawler\scripts\complete_full_crawl.py')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    Remove-Item Env:GEDS_PUBLIC_DATABASE_URL_UNPOOLED -ErrorAction SilentlyContinue
}
