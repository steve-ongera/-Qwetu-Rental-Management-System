# create-tenant-templates.ps1
$dir = Join-Path -Path (Get-Location) -ChildPath "templates\tenants"

# Ensure directory exists
if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

# Files to create
$files = @(
    'tenant_list.html'
    'tenant_detail.html'
    'tenant_form.html'        # used for both create & edit
    'active_tenant_list.html'
    'tenancy_list.html'
    'tenancy_detail.html'
    'tenancy_form.html'       # used for create & edit
    'tenancy_terminate.html'
)

# Create empty files (overwrites if already present)
foreach ($f in $files) {
    $path = Join-Path $dir $f
    New-Item -ItemType File -Path $path -Force | Out-Null
}

Write-Host "Created templates in: $dir"
