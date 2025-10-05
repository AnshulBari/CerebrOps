#!/bin/bash
# CerebrOps Deployment Script for Kubernetes

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

NAMESPACE="cerebrops"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Function to check if kubectl is available and connected
check_kubectl() {
    print_status "Checking kubectl connectivity..."
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        print_error "kubectl is not connected to a Kubernetes cluster"
        exit 1
    fi
    
    print_success "kubectl is ready"
}

# Create namespace
create_namespace() {
    print_status "Creating namespace '$NAMESPACE'..."
    
    if kubectl get namespace $NAMESPACE &> /dev/null; then
        print_warning "Namespace '$NAMESPACE' already exists"
    else
        kubectl create namespace $NAMESPACE
        print_success "Namespace '$NAMESPACE' created"
    fi
}

# Create secrets
create_secrets() {
    print_status "Setting up secrets..."
    
    # Check if SLACK_WEBHOOK_URL is provided
    if [ -z "$SLACK_WEBHOOK_URL" ]; then
        print_warning "SLACK_WEBHOOK_URL not provided. Creating empty secret."
        print_warning "Update the secret later with: kubectl create secret generic cerebrops-secrets --from-literal=slack-webhook-url='YOUR_URL' -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -"
        SLACK_WEBHOOK_URL=""
    fi
    
    # Create secret
    kubectl create secret generic cerebrops-secrets \
        --from-literal=slack-webhook-url="$SLACK_WEBHOOK_URL" \
        --namespace=$NAMESPACE \
        --dry-run=client -o yaml | kubectl apply -f -
    
    print_success "Secrets configured"
}

# Deploy application
deploy_app() {
    print_status "Deploying CerebrOps application..."
    
    # Update image tag in deployment
    sed "s|cerebrops:latest|cerebrops:$IMAGE_TAG|g" k8s/deployment.yaml > /tmp/deployment.yaml
    
    # Apply manifests
    kubectl apply -f k8s/secrets.yaml -n $NAMESPACE
    kubectl apply -f /tmp/deployment.yaml -n $NAMESPACE
    kubectl apply -f k8s/cronjobs.yaml -n $NAMESPACE
    
    print_success "Application manifests applied"
}

# Wait for deployment
wait_for_deployment() {
    print_status "Waiting for deployment to be ready..."
    
    kubectl rollout status deployment/cerebrops-app -n $NAMESPACE --timeout=300s
    
    print_success "Deployment is ready"
}

# Check pod status
check_pods() {
    print_status "Checking pod status..."
    
    kubectl get pods -n $NAMESPACE -l app=cerebrops
    
    # Get pod logs
    POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=cerebrops -o jsonpath='{.items[0].metadata.name}')
    if [ ! -z "$POD_NAME" ]; then
        print_status "Recent logs from $POD_NAME:"
        kubectl logs $POD_NAME -n $NAMESPACE --tail=20
    fi
}

# Setup port forwarding
setup_port_forward() {
    print_status "Setting up port forwarding..."
    print_status "Run the following command to access the application:"
    echo "kubectl port-forward service/cerebrops-service 8080:80 -n $NAMESPACE"
    print_status "Then access the application at: http://localhost:8080"
}

# Setup ingress (optional)
setup_ingress() {
    print_status "Setting up ingress..."
    
    # Check if ingress controller exists
    if kubectl get ingressclass &> /dev/null; then
        kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cerebrops-ingress
  namespace: $NAMESPACE
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: cerebrops.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: cerebrops-service
            port:
              number: 80
EOF
        print_success "Ingress configured"
        print_status "Add '127.0.0.1 cerebrops.local' to /etc/hosts to access via http://cerebrops.local"
    else
        print_warning "No ingress controller found. Skipping ingress setup."
    fi
}

# Verify deployment
verify_deployment() {
    print_status "Verifying deployment..."
    
    # Check if service is running
    kubectl get service cerebrops-service -n $NAMESPACE
    
    # Check deployment status
    READY_REPLICAS=$(kubectl get deployment cerebrops-app -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
    DESIRED_REPLICAS=$(kubectl get deployment cerebrops-app -n $NAMESPACE -o jsonpath='{.spec.replicas}')
    
    if [ "$READY_REPLICAS" = "$DESIRED_REPLICAS" ]; then
        print_success "All replicas are ready ($READY_REPLICAS/$DESIRED_REPLICAS)"
    else
        print_warning "Not all replicas are ready ($READY_REPLICAS/$DESIRED_REPLICAS)"
    fi
}

# Main deployment function
main() {
    echo "============================================"
    echo "🚀 CerebrOps Kubernetes Deployment"
    echo "============================================"
    echo
    
    check_kubectl
    create_namespace
    create_secrets
    deploy_app
    wait_for_deployment
    check_pods
    setup_ingress
    verify_deployment
    setup_port_forward
    
    echo
    echo "============================================"
    print_success "🎉 Deployment completed successfully!"
    echo "============================================"
    echo
    echo "Next steps:"
    echo "1. Set up port forwarding or configure ingress"
    echo "2. Update the secret with your Slack webhook URL if needed"
    echo "3. Monitor the application logs: kubectl logs -f deployment/cerebrops-app -n $NAMESPACE"
    echo
}

# Handle arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo "Options:"
        echo "  --help, -h    Show this help message"
        echo ""
        echo "Environment variables:"
        echo "  SLACK_WEBHOOK_URL   Slack webhook URL for alerts"
        echo "  IMAGE_TAG          Docker image tag (default: latest)"
        echo ""
        echo "Example:"
        echo "  SLACK_WEBHOOK_URL='https://hooks.slack.com/services/YOUR_WORKSPACE/YOUR_CHANNEL/YOUR_TOKEN' IMAGE_TAG='v1.0' $0"
        exit 0
        ;;
esac

# Run main deployment
main
