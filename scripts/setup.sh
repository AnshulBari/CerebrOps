#!/bin/bash
# CerebrOps Setup Script - Linux/macOS

set -e

echo "🧠 Setting up CerebrOps AI-Powered CI/CD Monitoring System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    command -v docker >/dev/null 2>&1 || { print_error "Docker is required but not installed. Please install Docker first."; exit 1; }
    command -v docker-compose >/dev/null 2>&1 || { print_error "Docker Compose is required but not installed. Please install Docker Compose first."; exit 1; }
    command -v python3 >/dev/null 2>&1 || { print_error "Python 3 is required but not installed. Please install Python 3.11+ first."; exit 1; }
    command -v kubectl >/dev/null 2>&1 || print_warning "kubectl not found. Kubernetes deployment will not be available."
    
    print_success "Prerequisites check completed"
}

# Create Python virtual environment
setup_python_env() {
    print_status "Setting up Python environment..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_warning "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    pip install -r requirements.txt
    
    print_success "Python environment setup completed"
}

# Create environment file
setup_environment() {
    print_status "Setting up environment configuration..."
    
    if [ ! -f ".env" ]; then
        cp .env.example .env
        print_warning "Created .env file from template. Please edit it with your configuration."
        print_warning "Don't forget to set your SLACK_WEBHOOK_URL!"
    else
        print_warning ".env file already exists"
    fi
    
    # Create logs directory
    mkdir -p logs
    print_success "Environment setup completed"
}

# Start ELK stack
start_elk_stack() {
    print_status "Starting ELK stack..."
    
    cd elk
    
    # Check if containers are already running
    if docker-compose ps | grep -q "Up"; then
        print_warning "ELK stack containers are already running"
    else
        docker-compose up -d
        print_success "ELK stack started"
    fi
    
    cd ..
    
    # Wait for Elasticsearch to be ready
    print_status "Waiting for Elasticsearch to be ready..."
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:9200/_cluster/health >/dev/null 2>&1; then
            print_success "Elasticsearch is ready"
            break
        fi
        
        attempt=$((attempt + 1))
        sleep 10
        echo -n "."
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_error "Elasticsearch failed to start after $((max_attempts * 10)) seconds"
        exit 1
    fi
}

# Build and start application
build_and_start_app() {
    print_status "Building and starting CerebrOps application..."
    
    # Build Docker image
    docker build -t cerebrops:latest .
    
    # Stop existing container if running
    docker stop cerebrops-app 2>/dev/null || true
    docker rm cerebrops-app 2>/dev/null || true
    
    # Start application container
    docker run -d \
        --name cerebrops-app \
        -p 5000:5000 \
        --network elk_elk-network \
        -v $(pwd)/logs:/app/logs \
        --env-file .env \
        cerebrops:latest
    
    print_success "CerebrOps application started"
}

# Run tests
run_tests() {
    print_status "Running tests..."
    
    source venv/bin/activate
    pytest tests/ -v --cov=. || print_warning "Some tests failed, but continuing..."
    
    print_success "Tests completed"
}

# Setup Kubernetes (optional)
setup_kubernetes() {
    if command -v kubectl >/dev/null 2>&1; then
        print_status "Setting up Kubernetes manifests..."
        
        # Create namespace if it doesn't exist
        kubectl create namespace cerebrops 2>/dev/null || true
        
        print_success "Kubernetes setup completed"
        print_status "To deploy to Kubernetes, run: kubectl apply -f k8s/"
    else
        print_warning "kubectl not found, skipping Kubernetes setup"
    fi
}

# Verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    # Check if services are responding
    services=(
        "http://localhost:5000|CerebrOps Application"
        "http://localhost:9200|Elasticsearch"
        "http://localhost:5601|Kibana"
    )
    
    for service in "${services[@]}"; do
        url=$(echo $service | cut -d'|' -f1)
        name=$(echo $service | cut -d'|' -f2)
        
        if curl -s "$url" >/dev/null 2>&1; then
            print_success "$name is responding"
        else
            print_warning "$name is not responding at $url"
        fi
    done
}

# Main setup flow
main() {
    echo "============================================"
    echo "🧠 CerebrOps Setup Script"
    echo "============================================"
    echo
    
    check_prerequisites
    setup_python_env
    setup_environment
    start_elk_stack
    build_and_start_app
    run_tests
    setup_kubernetes
    verify_installation
    
    echo
    echo "============================================"
    print_success "🎉 CerebrOps setup completed!"
    echo "============================================"
    echo
    echo "Next steps:"
    echo "1. Edit .env file with your Slack webhook URL"
    echo "2. Access CerebrOps dashboard: http://localhost:5000"
    echo "3. Access Kibana dashboard: http://localhost:5601"
    echo "4. Start monitoring: python monitor.py --single-check"
    echo
    echo "For more information, see README.md"
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo "Options:"
        echo "  --help, -h    Show this help message"
        echo "  --skip-tests  Skip running tests"
        exit 0
        ;;
    --skip-tests)
        SKIP_TESTS=true
        ;;
esac

# Run main setup
main
