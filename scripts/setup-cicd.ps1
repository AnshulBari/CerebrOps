# CerebrOps CI/CD Setup Script
# Run this script to configure your CI/CD pipeline for deployment

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CerebrOps CI/CD Pipeline Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if command exists
function Test-Command($cmdname) {
    return [bool](Get-Command -Name $cmdname -ErrorAction SilentlyContinue)
}

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow
Write-Host ""

$missingTools = @()

if (-not (Test-Command kubectl)) {
    $missingTools += "kubectl"
    Write-Host "  [X] kubectl is not installed" -ForegroundColor Red
} else {
    Write-Host "  [✓] kubectl is installed" -ForegroundColor Green
}

if (-not (Test-Command docker)) {
    $missingTools += "docker"
    Write-Host "  [X] docker is not installed" -ForegroundColor Red
} else {
    Write-Host "  [✓] docker is installed" -ForegroundColor Green
}

if (-not (Test-Command git)) {
    $missingTools += "git"
    Write-Host "  [X] git is not installed" -ForegroundColor Red
} else {
    Write-Host "  [✓] git is installed" -ForegroundColor Green
}

if ($missingTools.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing tools: $($missingTools -join ', ')" -ForegroundColor Red
    Write-Host "Please install missing tools and try again." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Step 1: GitHub Secrets Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "You need to configure these GitHub Secrets:" -ForegroundColor Yellow
Write-Host "  Repository → Settings → Secrets and variables → Actions" -ForegroundColor White
Write-Host ""
Write-Host "Required Secrets:" -ForegroundColor Yellow
Write-Host "  1. K8S_SERVER   - Your Kubernetes API server URL" -ForegroundColor White
Write-Host "  2. K8S_TOKEN    - Service account token" -ForegroundColor White
Write-Host "  3. SLACK_WEBHOOK_URL - Slack webhook for alerts (optional)" -ForegroundColor White
Write-Host ""

# Try to get K8s server URL
Write-Host "Attempting to get your Kubernetes server URL..." -ForegroundColor Yellow
try {
    $k8sServer = kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>$null
    if ($k8sServer) {
        Write-Host ""
        Write-Host "  K8S_SERVER = $k8sServer" -ForegroundColor Green
        Write-Host "  Copy this value to GitHub Secrets as 'K8S_SERVER'" -ForegroundColor Cyan
        Write-Host ""
    }
} catch {
    Write-Host "  Could not retrieve K8s server URL. Ensure kubectl is configured." -ForegroundColor Red
}

Write-Host "To create a service account and get the token:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  # Create namespace" -ForegroundColor Gray
Write-Host "  kubectl create namespace cerebrops" -ForegroundColor White
Write-Host ""
Write-Host "  # Create service account" -ForegroundColor Gray
Write-Host "  kubectl create serviceaccount cerebrops-deployer -n cerebrops" -ForegroundColor White
Write-Host ""
Write-Host "  # Create cluster role binding" -ForegroundColor Gray
Write-Host "  kubectl create clusterrolebinding cerebrops-deployer-binding --clusterrole=cluster-admin --serviceaccount=cerebrops:cerebrops-deployer" -ForegroundColor White
Write-Host ""
Write-Host "  # Get the token" -ForegroundColor Gray
Write-Host "  kubectl create token cerebrops-deployer -n cerebrops --duration=876000h" -ForegroundColor White
Write-Host ""

$createServiceAccount = Read-Host "Do you want to create the service account now? (y/N)"
if ($createServiceAccount -eq 'y' -or $createServiceAccount -eq 'Y') {
    Write-Host ""
    Write-Host "Creating Kubernetes service account..." -ForegroundColor Yellow
    
    kubectl create namespace cerebrops 2>$null
    kubectl create serviceaccount cerebrops-deployer -n cerebrops 2>$null
    kubectl create clusterrolebinding cerebrops-deployer-binding --clusterrole=cluster-admin --serviceaccount=cerebrops:cerebrops-deployer 2>$null
    
    Write-Host ""
    Write-Host "Generating token..." -ForegroundColor Yellow
    $token = kubectl create token cerebrops-deployer -n cerebrops --duration=876000h 2>$null
    
    if ($token) {
        Write-Host ""
        Write-Host "  K8S_TOKEN = $token" -ForegroundColor Green
        Write-Host "  Copy this value to GitHub Secrets as 'K8S_TOKEN'" -ForegroundColor Cyan
        Write-Host "  WARNING: This token will only be shown once!" -ForegroundColor Red
        Write-Host ""
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Step 2: Local Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "  [✓] .env file created" -ForegroundColor Green
        Write-Host "  Please edit .env and add your SLACK_WEBHOOK_URL" -ForegroundColor Cyan
    }
} else {
    Write-Host "  [✓] .env file already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Step 3: Test Locally" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$runTests = Read-Host "Do you want to run tests now? (y/N)"
if ($runTests -eq 'y' -or $runTests -eq 'Y') {
    Write-Host ""
    Write-Host "Running tests..." -ForegroundColor Yellow
    
    # Check if Python venv exists
    if (Test-Path ".venv") {
        Write-Host "Activating virtual environment..." -ForegroundColor Yellow
        & .\.venv\Scripts\Activate.ps1
    }
    
    Write-Host "Running pytest..." -ForegroundColor Yellow
    pytest tests/ -v --tb=short
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "  [✓] All tests passed!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "  [X] Some tests failed. Please fix before deploying." -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Step 4: Commit and Push Changes" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "The following files have been updated:" -ForegroundColor Yellow
git status --short

Write-Host ""
$commitChanges = Read-Host "Do you want to commit these changes? (y/N)"
if ($commitChanges -eq 'y' -or $commitChanges -eq 'Y') {
    Write-Host ""
    Write-Host "Staging files..." -ForegroundColor Yellow
    
    git add .github/workflows/ci-cd.yml
    git add k8s/deployment.yaml
    git add k8s/cronjobs.yaml
    git add k8s/persistent-volume.yaml
    git add scripts/smoke-tests.sh
    git add GITHUB_SETUP.md
    git add DEPLOYMENT_CHECKLIST.md
    git add .env
    
    Write-Host "Committing changes..." -ForegroundColor Yellow
    git commit -m "ci: Configure CI/CD pipeline for production deployment

- Uncomment kubectl deployment commands in GitHub Actions
- Update image registry to ghcr.io/anshulbari/cerebrops
- Fix namespace references in cronjobs
- Add persistent volume claims for logs and data
- Add smoke tests script
- Add comprehensive setup and deployment documentation"
    
    Write-Host ""
    Write-Host "  [✓] Changes committed" -ForegroundColor Green
    
    Write-Host ""
    $pushChanges = Read-Host "Do you want to push to GitHub now? (y/N)"
    if ($pushChanges -eq 'y' -or $pushChanges -eq 'Y') {
        Write-Host ""
        Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
        git push origin main
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "  [✓] Changes pushed successfully!" -ForegroundColor Green
            Write-Host ""
            Write-Host "The CI/CD pipeline will now run automatically!" -ForegroundColor Cyan
        } else {
            Write-Host ""
            Write-Host "  [X] Push failed. Please check your credentials and try again." -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Next Steps" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. Add GitHub Secrets:" -ForegroundColor Yellow
Write-Host "   Go to: https://github.com/AnshulBari/CerebrOps/settings/secrets/actions" -ForegroundColor White
Write-Host "   Add: K8S_SERVER, K8S_TOKEN, SLACK_WEBHOOK_URL" -ForegroundColor White
Write-Host ""

Write-Host "2. Enable Workflow Permissions:" -ForegroundColor Yellow
Write-Host "   Go to: https://github.com/AnshulBari/CerebrOps/settings/actions" -ForegroundColor White
Write-Host "   Under 'Workflow permissions', select 'Read and write permissions'" -ForegroundColor White
Write-Host ""

Write-Host "3. Monitor Pipeline:" -ForegroundColor Yellow
Write-Host "   Go to: https://github.com/AnshulBari/CerebrOps/actions" -ForegroundColor White
Write-Host "   Watch your pipeline run and deploy!" -ForegroundColor White
Write-Host ""

Write-Host "4. Verify Deployment:" -ForegroundColor Yellow
Write-Host "   kubectl get all -n cerebrops" -ForegroundColor White
Write-Host "   kubectl port-forward service/cerebrops-service 8080:80 -n cerebrops" -ForegroundColor White
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "For detailed instructions, see:" -ForegroundColor Yellow
Write-Host "  - GITHUB_SETUP.md" -ForegroundColor White
Write-Host "  - DEPLOYMENT_CHECKLIST.md" -ForegroundColor White
Write-Host ""
