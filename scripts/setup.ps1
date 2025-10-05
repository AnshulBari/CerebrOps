# CerebrOps Setup Script - Windows PowerShell

param(
    [switch]$SkipTests = $false,
    [switch]$Help = $false
)

# Colors for output
$Red = "Red"
$Green = "Green" 
$Yellow = "Yellow"
$Blue = "Cyan"

function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor $Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor $Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $Red
}

function Show-Help {
    Write-Host "CerebrOps Setup Script for Windows"
    Write-Host "Usage: .\scripts\setup.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Help         Show this help message"
    Write-Host "  -SkipTests    Skip running tests"
    Write-Host ""
    Write-Host "Example:"
    Write-Host "  .\scripts\setup.ps1"
    Write-Host "  .\scripts\setup.ps1 -SkipTests"
    exit 0
}

function Test-Prerequisites {
    Write-Status "Checking prerequisites..."
    
    # Check Docker
    try {
        $null = Get-Command docker -ErrorAction Stop
        Write-Success "Docker found"
    }
    catch {
        Write-Error "Docker is required but not installed. Please install Docker Desktop first."
        exit 1
    }
    
    # Check Docker Compose
    try {
        $null = Get-Command docker-compose -ErrorAction Stop
        Write-Success "Docker Compose found"
    }
    catch {
        Write-Error "Docker Compose is required but not installed."
        exit 1
    }
    
    # Check Python
    try {
        $pythonVersion = python --version 2>&1
        if ($pythonVersion -match "Python 3\.([0-9]+)\.") {
            $majorVersion = [int]$matches[1]
            if ($majorVersion -ge 11) {
                Write-Success "Python $pythonVersion found"
            } else {
                Write-Warning "Python 3.11+ recommended, found $pythonVersion"
            }
        } else {
            Write-Error "Python 3.11+ is required"
            exit 1
        }
    }
    catch {
        Write-Error "Python is required but not installed. Please install Python 3.11+ first."
        exit 1
    }
    
    # Check kubectl (optional)
    try {
        $null = Get-Command kubectl -ErrorAction Stop
        Write-Success "kubectl found"
    }
    catch {
        Write-Warning "kubectl not found. Kubernetes deployment will not be available."
    }
    
    Write-Success "Prerequisites check completed"
}

function Setup-PythonEnvironment {
    Write-Status "Setting up Python environment..."
    
    if (!(Test-Path "venv")) {
        python -m venv venv
        Write-Success "Virtual environment created"
    } else {
        Write-Warning "Virtual environment already exists"
    }
    
    # Activate virtual environment
    & ".\venv\Scripts\Activate.ps1"
    
    # Upgrade pip
    python -m pip install --upgrade pip
    
    # Install requirements
    pip install -r requirements.txt
    
    Write-Success "Python environment setup completed"
}

function Setup-Environment {
    Write-Status "Setting up environment configuration..."
    
    if (!(Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Warning "Created .env file from template. Please edit it with your configuration."
        Write-Warning "Don't forget to set your SLACK_WEBHOOK_URL!"
    } else {
        Write-Warning ".env file already exists"
    }
    
    # Create logs directory
    if (!(Test-Path "logs")) {
        New-Item -ItemType Directory -Path "logs" | Out-Null
    }
    
    Write-Success "Environment setup completed"
}

function Start-ELKStack {
    Write-Status "Starting ELK stack..."
    
    Set-Location "elk"
    
    # Check if containers are already running
    $runningContainers = docker-compose ps --services --filter "status=running"
    if ($runningContainers) {
        Write-Warning "ELK stack containers are already running"
    } else {
        docker-compose up -d
        Write-Success "ELK stack started"
    }
    
    Set-Location ".."
    
    # Wait for Elasticsearch to be ready
    Write-Status "Waiting for Elasticsearch to be ready..."
    $maxAttempts = 30
    $attempt = 0
    
    while ($attempt -lt $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:9200/_cluster/health" -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Success "Elasticsearch is ready"
                break
            }
        }
        catch {
            # Continue waiting
        }
        
        $attempt++
        Start-Sleep -Seconds 10
        Write-Host "." -NoNewline
    }
    
    if ($attempt -eq $maxAttempts) {
        Write-Error "Elasticsearch failed to start after $($maxAttempts * 10) seconds"
        exit 1
    }
}

function Build-AndStartApp {
    Write-Status "Building and starting CerebrOps application..."
    
    # Build Docker image
    docker build -t cerebrops:latest .
    
    # Stop existing container if running
    docker stop cerebrops-app 2>$null | Out-Null
    docker rm cerebrops-app 2>$null | Out-Null
    
    # Get current directory path for volume mounting
    $currentPath = (Get-Location).Path
    
    # Start application container
    docker run -d `
        --name cerebrops-app `
        -p 5000:5000 `
        --network elk_elk-network `
        -v "${currentPath}\logs:/app/logs" `
        --env-file .env `
        cerebrops:latest
    
    Write-Success "CerebrOps application started"
}

function Invoke-Tests {
    if (!$SkipTests) {
        Write-Status "Running tests..."
        
        & ".\venv\Scripts\Activate.ps1"
        try {
            pytest tests/ -v --cov=.
            Write-Success "Tests completed"
        }
        catch {
            Write-Warning "Some tests failed, but continuing..."
        }
    } else {
        Write-Warning "Skipping tests as requested"
    }
}

function Setup-Kubernetes {
    try {
        $null = Get-Command kubectl -ErrorAction Stop
        Write-Status "Setting up Kubernetes manifests..."
        
        # Create namespace if it doesn't exist
        kubectl create namespace cerebrops 2>$null | Out-Null
        
        Write-Success "Kubernetes setup completed"
        Write-Status "To deploy to Kubernetes, run: kubectl apply -f k8s/"
    }
    catch {
        Write-Warning "kubectl not found, skipping Kubernetes setup"
    }
}

function Test-Installation {
    Write-Status "Verifying installation..."
    
    $services = @(
        @{Url="http://localhost:5000"; Name="CerebrOps Application"},
        @{Url="http://localhost:9200"; Name="Elasticsearch"},
        @{Url="http://localhost:5601"; Name="Kibana"}
    )
    
    foreach ($service in $services) {
        try {
            $response = Invoke-WebRequest -Uri $service.Url -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Success "$($service.Name) is responding"
            }
        }
        catch {
            Write-Warning "$($service.Name) is not responding at $($service.Url)"
        }
    }
}

function Main {
    Write-Host "============================================" -ForegroundColor $Blue
    Write-Host "🧠 CerebrOps Setup Script" -ForegroundColor $Blue
    Write-Host "============================================" -ForegroundColor $Blue
    Write-Host ""
    
    Test-Prerequisites
    Setup-PythonEnvironment
    Setup-Environment
    Start-ELKStack
    Build-AndStartApp
    Invoke-Tests
    Setup-Kubernetes
    Test-Installation
    
    Write-Host ""
    Write-Host "============================================" -ForegroundColor $Blue
    Write-Success "🎉 CerebrOps setup completed!"
    Write-Host "============================================" -ForegroundColor $Blue
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "1. Edit .env file with your Slack webhook URL"
    Write-Host "2. Access CerebrOps dashboard: http://localhost:5000"
    Write-Host "3. Access Kibana dashboard: http://localhost:5601"
    Write-Host "4. Start monitoring: python monitor.py --single-check"
    Write-Host ""
    Write-Host "For more information, see README.md"
}

# Handle help parameter
if ($Help) {
    Show-Help
}

# Run main setup
Main
