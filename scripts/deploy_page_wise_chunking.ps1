# ============================================================================
# Page-Wise Chunking Deployment Script
# ============================================================================
# This script automates the .env configuration update for page-wise chunking.
# It safely adds the required settings while preserving existing configuration.
#
# Usage: .\scripts\deploy_page_wise_chunking.ps1
# ============================================================================

param(
    [switch]$DryRun = $false,
    [switch]$Force = $false
)

# Color output functions
function Write-Success { param($Message) Write-Host "✓ $Message" -ForegroundColor Green }
function Write-Error { param($Message) Write-Host "✗ $Message" -ForegroundColor Red }
function Write-Info { param($Message) Write-Host "ℹ $Message" -ForegroundColor Cyan }
function Write-Warning { param($Message) Write-Host "⚠ $Message" -ForegroundColor Yellow }

# Script configuration
$envFile = ".\.env"
$backupDir = ".\backups"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  PAGE-WISE CHUNKING DEPLOYMENT SCRIPT" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

if ($DryRun) {
    Write-Warning "DRY RUN MODE - No changes will be made"
    Write-Host ""
}

# ============================================================================
# Step 1: Pre-flight Checks
# ============================================================================

Write-Info "Step 1: Running pre-flight checks..."
Write-Host ""

# Check if .env file exists
if (-not (Test-Path $envFile)) {
    Write-Error ".env file not found at $envFile"
    Write-Host "Please create a .env file first or run from the project root directory."
    exit 1
}
Write-Success ".env file found"

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Success "Python available: $pythonVersion"
} catch {
    Write-Error "Python not found in PATH"
    Write-Host "Please ensure Python is installed and available in PATH."
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    Write-Warning "Virtual environment not found at .\.venv"
    Write-Host "Consider creating a virtual environment first."
} else {
    Write-Success "Virtual environment found"
}

Write-Host ""

# ============================================================================
# Step 2: Read Current Configuration
# ============================================================================

Write-Info "Step 2: Reading current .env configuration..."
Write-Host ""

$envContent = Get-Content $envFile -Raw

# Check if page-wise chunking settings already exist
$hasPageWiseChunking = $envContent -match "PAGE_WISE_CHUNKING"
$hasMaxPageTokens = $envContent -match "MAX_PAGE_TOKENS"

if ($hasPageWiseChunking -and $hasMaxPageTokens) {
    Write-Warning "Page-wise chunking settings already exist in .env"
    
    # Extract current values
    if ($envContent -match "PAGE_WISE_CHUNKING\s*=\s*(\w+)") {
        $currentPageWise = $matches[1]
        Write-Host "  Current PAGE_WISE_CHUNKING: $currentPageWise"
    }
    
    if ($envContent -match "MAX_PAGE_TOKENS\s*=\s*(\d+)") {
        $currentMaxTokens = $matches[1]
        Write-Host "  Current MAX_PAGE_TOKENS: $currentMaxTokens"
    }
    
    Write-Host ""
    
    if (-not $Force) {
        Write-Host "Use -Force flag to overwrite existing settings."
        Write-Host "Exiting without changes."
        exit 0
    } else {
        Write-Warning "Force flag set - will update existing settings"
    }
} else {
    Write-Success "No existing page-wise chunking settings found"
}

Write-Host ""

# ============================================================================
# Step 3: Create Backup
# ============================================================================

Write-Info "Step 3: Creating backup of .env file..."
Write-Host ""

if (-not $DryRun) {
    # Create backup directory if it doesn't exist
    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        Write-Success "Created backup directory: $backupDir"
    }
    
    # Create backup
    $backupFile = "$backupDir\.env.backup_$timestamp"
    Copy-Item -Path $envFile -Destination $backupFile
    
    # Verify backup
    if (Test-Path $backupFile) {
        $originalSize = (Get-Item $envFile).Length
        $backupSize = (Get-Item $backupFile).Length
        
        if ($originalSize -eq $backupSize) {
            Write-Success "Backup created: $backupFile"
        } else {
            Write-Error "Backup verification failed - size mismatch"
            exit 1
        }
    } else {
        Write-Error "Failed to create backup"
        exit 1
    }
} else {
    Write-Info "[DRY RUN] Would create backup at: $backupDir\.env.backup_$timestamp"
}

Write-Host ""

# ============================================================================
# Step 4: Update .env Configuration
# ============================================================================

Write-Info "Step 4: Updating .env configuration..."
Write-Host ""

# Configuration to add
$pageWiseChunkingConfig = @"

# ─────────────────────────────────────────
# PAGE-WISE CHUNKING SETTINGS
# ─────────────────────────────────────────
# Enable page-wise chunking strategy (one chunk per page)
# Set to False to use legacy text-based chunking
PAGE_WISE_CHUNKING=True

# Maximum tokens per chunk (embedding model limit)
# Default: 8000 (safe for sentence-transformers/all-MiniLM-L6-v2)
MAX_PAGE_TOKENS=8000
"@

if (-not $DryRun) {
    if ($hasPageWiseChunking -and $hasMaxPageTokens) {
        # Update existing settings
        $envContent = $envContent -replace "PAGE_WISE_CHUNKING\s*=\s*\w+", "PAGE_WISE_CHUNKING=True"
        $envContent = $envContent -replace "MAX_PAGE_TOKENS\s*=\s*\d+", "MAX_PAGE_TOKENS=8000"
        
        Set-Content -Path $envFile -Value $envContent -NoNewline
        Write-Success "Updated existing PAGE_WISE_CHUNKING settings"
    } else {
        # Append new settings
        Add-Content -Path $envFile -Value $pageWiseChunkingConfig
        Write-Success "Added PAGE_WISE_CHUNKING settings to .env"
    }
} else {
    Write-Info "[DRY RUN] Would add the following to .env:"
    Write-Host $pageWiseChunkingConfig -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# Step 5: Verify Configuration
# ============================================================================

Write-Info "Step 5: Verifying configuration..."
Write-Host ""

if (-not $DryRun) {
    # Verify settings were added
    $updatedContent = Get-Content $envFile -Raw
    
    if ($updatedContent -match "PAGE_WISE_CHUNKING\s*=\s*True") {
        Write-Success "PAGE_WISE_CHUNKING=True verified"
    } else {
        Write-Error "Failed to verify PAGE_WISE_CHUNKING setting"
        exit 1
    }
    
    if ($updatedContent -match "MAX_PAGE_TOKENS\s*=\s*8000") {
        Write-Success "MAX_PAGE_TOKENS=8000 verified"
    } else {
        Write-Error "Failed to verify MAX_PAGE_TOKENS setting"
        exit 1
    }
    
    # Test Python can load the config
    Write-Host ""
    Write-Info "Testing Python configuration loading..."
    
    $testScript = @"
from src.config import PAGE_WISE_CHUNKING, MAX_PAGE_TOKENS
print(f'PAGE_WISE_CHUNKING={PAGE_WISE_CHUNKING}')
print(f'MAX_PAGE_TOKENS={MAX_PAGE_TOKENS}')
if PAGE_WISE_CHUNKING and MAX_PAGE_TOKENS == 8000:
    print('✓ Configuration loaded successfully')
    exit(0)
else:
    print('✗ Configuration validation failed')
    exit(1)
"@
    
    $testResult = python -c $testScript 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host $testResult
        Write-Success "Python configuration validation passed"
    } else {
        Write-Error "Python configuration validation failed"
        Write-Host $testResult
        Write-Warning "You may need to restart any running Python processes"
    }
} else {
    Write-Info "[DRY RUN] Would verify configuration in .env and test Python loading"
}

Write-Host ""

# ============================================================================
# Step 6: Next Steps
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  DEPLOYMENT CONFIGURATION COMPLETE" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

if (-not $DryRun) {
    Write-Success "Configuration updated successfully!"
    Write-Host ""
    Write-Info "Next Steps:"
    Write-Host ""
    Write-Host "  1. Review the changes in .env file"
    Write-Host "  2. Run re-indexing with page-wise chunking:"
    Write-Host "     python scripts/ingest_all.py --force"
    Write-Host ""
    Write-Host "  3. Monitor the ingestion process for errors"
    Write-Host "  4. Verify chunk count reduction (target: 300-400 chunks)"
    Write-Host "  5. Test query retrieval:"
    Write-Host "     python scripts/test_query.py --q \"your test query\""
    Write-Host ""
    Write-Info "Backup Location:"
    Write-Host "  $backupFile"
    Write-Host ""
    Write-Info "Rollback Instructions:"
    Write-Host "  If you need to rollback, run:"
    Write-Host "  Copy-Item -Path '$backupFile' -Destination '.\.env' -Force"
    Write-Host ""
} else {
    Write-Info "Dry run complete - no changes were made"
    Write-Host ""
    Write-Host "To apply these changes, run:"
    Write-Host "  .\scripts\deploy_page_wise_chunking.ps1"
    Write-Host ""
}

Write-Host "For detailed deployment instructions, see: DEPLOYMENT_CHECKLIST.md"
Write-Host ""
