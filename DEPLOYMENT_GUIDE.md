# 🚀 CerebrOps Deployment & Operations Guide

This comprehensive guide covers everything you need to know to deploy, run, and operate the CerebrOps AI-Powered CI/CD Monitoring System in various environments.

## Table of Contents

- [System Requirements](#system-requirements)
- [Quick Start](#quick-start)
- [Local Development Setup](#local-development-setup)
- [Production Deployment](#production-deployment)
- [Configuration Management](#configuration-management)
- [Operating the System](#operating-the-system)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **OS** | Windows 10+, macOS 10.15+, Linux (Ubuntu 18.04+) |
| **RAM** | 8GB (4GB for application, 4GB for ELK stack) |
| **CPU** | 4 cores, 2.0GHz |
| **Disk** | 20GB free space |
| **Network** | Internet access for container downloads |

### Recommended Requirements

| Component | Requirement |
|-----------|-------------|
| **RAM** | 16GB+ |
| **CPU** | 8+ cores, 3.0GHz+ |
| **Disk** | 50GB+ SSD |
| **Network** | High-speed internet connection |

### Software Prerequisites

- **Docker Desktop** (v4.0+) with Docker Compose
- **Python** 3.11 or higher
- **Git** for version control
- **kubectl** (for Kubernetes deployment)
- **PowerShell Core** (Windows) or **Bash** (Linux/macOS)

## Quick Start

### 🎯 Option 1: One-Command Setup (Recommended)

**For Linux/macOS:**
```bash
# Clone the repository
git clone https://github.com/your-username/CerebrOps.git
cd CerebrOps

# Make script executable and run
chmod +x scripts/setup.sh
./scripts/setup.sh
```

**For Windows:**
```powershell
# Clone the repository
git clone https://github.com/your-username/CerebrOps.git
cd CerebrOps

# Run PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\setup.ps1
```

After successful setup:
- 🌐 **CerebrOps Dashboard**: http://localhost:5000
- 📊 **Kibana Dashboard**: http://localhost:5601
- 🔍 **Elasticsearch**: http://localhost:9200

### 🎯 Option 2: Docker Compose (Development)

```bash
# Clone and navigate
git clone https://github.com/your-username/CerebrOps.git
cd CerebrOps

# Copy environment template
cp .env.example .env
# Edit .env with your Slack webhook URL

# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Check status
docker-compose -f docker-compose.dev.yml ps
```

## Local Development Setup

### Step 1: Environment Preparation

```bash
# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Create `.env` file from template:
```bash
cp .env.example .env
```

Edit `.env` file:
```env
# Required: Slack webhook for alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR_WORKSPACE/YOUR_CHANNEL/YOUR_TOKEN

# Application settings
APP_URL=http://localhost:5000
ENVIRONMENT=development
LOG_LEVEL=INFO

# Monitoring settings
ANOMALY_THRESHOLD=0.1
MONITORING_INTERVAL=300
```

### Step 3: Start ELK Stack

```bash
# Navigate to ELK directory
cd elk

# Start ELK services
docker-compose up -d

# Wait for services to be ready (may take 2-3 minutes)
docker-compose ps

# Check Elasticsearch health
curl http://localhost:9200/_cluster/health

# Return to project root
cd ..
```

### Step 4: Build and Run Application

```bash
# Build Docker image
docker build -t cerebrops:latest .

# Create logs directory
mkdir -p logs

# Run application
docker run -d \
    --name cerebrops-app \
    -p 5000:5000 \
    --network elk_elk-network \
    -v $(pwd)/logs:/app/logs \
    --env-file .env \
    cerebrops:latest

# Check application logs
docker logs -f cerebrops-app
```

### Step 5: Verify Installation

```bash
# Test application endpoints
curl http://localhost:5000/health
curl http://localhost:5000/metrics

# Check ELK stack
curl http://localhost:9200
curl http://localhost:5601/api/status

# Run a single monitoring check
python monitor.py --single-check
```

## Production Deployment

### Kubernetes Deployment

#### Prerequisites for Kubernetes
- Kubernetes cluster (v1.20+)
- kubectl configured and connected
- Sufficient cluster resources (8GB+ RAM, 4+ CPU cores)

#### Step 1: Prepare Kubernetes Environment

```bash
# Verify kubectl connection
kubectl cluster-info

# Create namespace
kubectl create namespace cerebrops

# Verify namespace
kubectl get namespaces | grep cerebrops
```

#### Step 2: Configure Secrets

```bash
# Create Slack webhook secret
kubectl create secret generic cerebrops-secrets \
    --from-literal=slack-webhook-url='YOUR_SLACK_WEBHOOK_URL' \
    --namespace=cerebrops

# Verify secret creation
kubectl get secrets -n cerebrops
```

#### Step 3: Deploy Application

**Option A: Using Deployment Script (Recommended)**
```bash
# Set environment variables
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR_WORKSPACE/YOUR_CHANNEL/YOUR_TOKEN"
export IMAGE_TAG="latest"

# Run deployment script
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

**Option B: Manual Deployment**
```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/secrets.yaml -n cerebrops
kubectl apply -f k8s/deployment.yaml -n cerebrops
kubectl apply -f k8s/cronjobs.yaml -n cerebrops

# Wait for deployment
kubectl rollout status deployment/cerebrops-app -n cerebrops

# Check pod status
kubectl get pods -n cerebrops -l app=cerebrops
```

#### Step 4: Access Application

**Option A: Port Forwarding**
```bash
# Forward port to local machine
kubectl port-forward service/cerebrops-service 8080:80 -n cerebrops

# Access at http://localhost:8080
```

**Option B: Ingress Setup**
```bash
# Apply ingress manifest (if you have ingress controller)
kubectl apply -f k8s/ingress.yaml -n cerebrops

# Add to /etc/hosts (Linux/macOS) or C:\Windows\System32\drivers\etc\hosts (Windows)
echo "127.0.0.1 cerebrops.local" >> /etc/hosts

# Access at http://cerebrops.local
```

### Cloud Platform Deployment

#### Amazon EKS
```bash
# Configure AWS CLI and eks
aws eks update-kubeconfig --region us-west-2 --name your-cluster-name

# Deploy
export SLACK_WEBHOOK_URL="your-webhook"
./scripts/deploy.sh
```

#### Google GKE
```bash
# Configure kubectl for GKE
gcloud container clusters get-credentials your-cluster --zone us-central1-a

# Deploy
export SLACK_WEBHOOK_URL="your-webhook"
./scripts/deploy.sh
```

#### Azure AKS
```bash
# Configure kubectl for AKS
az aks get-credentials --resource-group myResourceGroup --name myAKSCluster

# Deploy
export SLACK_WEBHOOK_URL="your-webhook"
./scripts/deploy.sh
```

## Configuration Management

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SLACK_WEBHOOK_URL` | Slack webhook for alerts | None | No* |
| `APP_URL` | Application URL for monitoring | http://localhost:5000 | No |
| `ENVIRONMENT` | Environment name | development | No |
| `LOG_LEVEL` | Logging level | INFO | No |
| `ANOMALY_THRESHOLD` | ML model contamination rate | 0.1 | No |
| `MONITORING_INTERVAL` | Check interval (seconds) | 300 | No |

*Required for Slack alerts to work

### Application Configuration

#### Anomaly Detection Tuning

Edit `anomaly_detector.py` to customize:
```python
# Adjust sensitivity
detector = AnomalyDetector(contamination=0.05)  # More sensitive

# Custom metrics
detector.feature_columns.extend(['custom_metric'])

# Custom thresholds
def _calculate_severity(self, anomaly_percentage, scores):
    if anomaly_percentage > 20:  # Custom threshold
        return 'critical'
    elif anomaly_percentage > 10:
        return 'high'
    elif anomaly_percentage > 5:
        return 'medium'
    else:
        return 'low'
```

#### Alert Customization

Edit `alerts.py` for custom alerts:
```python
# Custom alert colors
color_map = {
    'low': '#00ff00',      # Green
    'medium': '#ffff00',   # Yellow
    'high': '#ffa500',     # Orange
    'critical': '#ff0000'  # Red
}

# Custom message templates
def create_custom_alert(self, title, message, severity='medium'):
    # Your custom alert logic
    pass
```

### ELK Stack Configuration

#### Elasticsearch
Edit `elk/elasticsearch/config/elasticsearch.yml`:
```yaml
# Increase heap size for production
cluster.name: "cerebrops-prod"
node.name: "cerebrops-es-01"

# Memory settings (adjust based on available RAM)
# Set in docker-compose.yml: "ES_JAVA_OPTS=-Xms2g -Xmx2g"
```

#### Logstash
Edit `elk/logstash/pipeline/logstash.conf`:
```ruby
# Add custom log patterns
if [application] == "cerebrops" {
  # Custom processing for CerebrOps logs
  mutate {
    add_field => { "processed_by" => "cerebrops-logstash" }
  }
}

# Add custom outputs
output {
  # Send critical errors to separate index
  if [severity] == "critical" {
    elasticsearch {
      hosts => ["elasticsearch:9200"]
      index => "cerebrops-critical-%{+YYYY.MM.dd}"
    }
  }
}
```

## Operating the System

### Starting the System

#### Development Environment
```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Check service status
docker-compose -f docker-compose.dev.yml ps

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

#### Production Environment
```bash
# Start monitoring
python monitor.py --interval 300

# Run in background
nohup python monitor.py --interval 300 > monitoring.log 2>&1 &

# Check process
ps aux | grep monitor.py
```

### Monitoring Operations

#### Manual Health Checks
```bash
# Application health
curl http://localhost:5000/health

# Metrics endpoint
curl http://localhost:5000/metrics | jq

# Elasticsearch health
curl http://localhost:9200/_cluster/health | jq

# Check logs
curl http://localhost:5000/logs | jq
```

#### Running Anomaly Detection
```bash
# Single check
python monitor.py --single-check

# Continuous monitoring
python monitor.py --interval 60  # Every minute

# Debug mode
python monitor.py --debug --single-check
```

#### Testing Alerts
```bash
# Test Slack webhook
python -c "
from alerts import SlackAlerter
alerter = SlackAlerter('YOUR_WEBHOOK_URL')
alerter.send_slack_alert('Test alert from CerebrOps! 🧠', 'low')
"

# Simulate error for testing
curl http://localhost:5000/simulate-error
```

### Kubernetes Operations

#### Scaling
```bash
# Scale application
kubectl scale deployment/cerebrops-app --replicas=3 -n cerebrops

# Check scaling status
kubectl get pods -n cerebrops -l app=cerebrops
```

#### Updates
```bash
# Update image
kubectl set image deployment/cerebrops-app cerebrops-web=cerebrops:v2.0 -n cerebrops

# Check rollout status
kubectl rollout status deployment/cerebrops-app -n cerebrops

# Rollback if needed
kubectl rollout undo deployment/cerebrops-app -n cerebrops
```

#### Monitoring Pods
```bash
# Get pod status
kubectl get pods -n cerebrops

# View logs
kubectl logs -f deployment/cerebrops-app -n cerebrops

# Execute commands in pod
kubectl exec -it deployment/cerebrops-app -n cerebrops -- /bin/bash

# Port forward for debugging
kubectl port-forward service/cerebrops-service 8080:80 -n cerebrops
```

## Monitoring & Maintenance

### Log Management

#### Application Logs
```bash
# View application logs
tail -f logs/app.log

# View monitoring logs
tail -f logs/monitoring.log

# View with filtering
tail -f logs/app.log | grep ERROR

# Rotate logs (add to crontab)
find logs/ -name "*.log" -mtime +7 -delete
```

#### Container Logs
```bash
# Docker logs
docker logs -f cerebrops-app

# Kubernetes logs
kubectl logs -f deployment/cerebrops-app -n cerebrops

# Previous container logs
docker logs --since 2h cerebrops-app
kubectl logs --previous deployment/cerebrops-app -n cerebrops
```

### Performance Monitoring

#### System Resources
```bash
# Docker container resources
docker stats cerebrops-app

# Kubernetes pod resources
kubectl top pods -n cerebrops

# ELK stack resources
docker stats elk_elasticsearch_1 elk_kibana_1 elk_logstash_1
```

#### Application Metrics
```bash
# Monitor response times
while true; do
  curl -w "@curl-format.txt" -s -o /dev/null http://localhost:5000/
  sleep 5
done

# Create curl-format.txt:
echo "     time_namelookup:  %{time_namelookup}
        time_connect:  %{time_connect}
     time_appconnect:  %{time_appconnect}
    time_pretransfer:  %{time_pretransfer}
       time_redirect:  %{time_redirect}
  time_starttransfer:  %{time_starttransfer}
                     ----------
          time_total:  %{time_total}" > curl-format.txt
```

### Database Maintenance

#### Elasticsearch Maintenance
```bash
# Check cluster health
curl http://localhost:9200/_cluster/health?pretty

# View indices
curl http://localhost:9200/_cat/indices?v

# Delete old indices (7 days+)
curl -X DELETE "localhost:9200/cerebrops-logs-$(date -d '7 days ago' +%Y.%m.%d)"

# Optimize indices
curl -X POST "localhost:9200/cerebrops-logs-*/_forcemerge?max_num_segments=1"
```

### Backup and Recovery

#### Configuration Backup
```bash
# Backup configuration files
tar -czf cerebrops-config-$(date +%Y%m%d).tar.gz \
  .env k8s/ elk/ scripts/

# Backup Elasticsearch data
docker exec elk_elasticsearch_1 \
  elasticsearch-dump --input=http://localhost:9200 \
  --output=/backup/cerebrops-$(date +%Y%m%d).json
```

#### System Recovery
```bash
# Restart all services
docker-compose -f docker-compose.dev.yml restart

# Or for Kubernetes
kubectl rollout restart deployment/cerebrops-app -n cerebrops

# Restore from backup
tar -xzf cerebrops-config-backup.tar.gz
```

## Troubleshooting

### Common Issues and Solutions

#### 1. ELK Stack Won't Start

**Problem**: Elasticsearch fails to start with memory errors.

**Solution**:
```bash
# Check Docker memory allocation (should be 8GB+)
docker system info | grep Memory

# Increase Docker memory in Docker Desktop settings

# Check disk space
df -h

# Restart ELK stack
cd elk
docker-compose down
docker-compose up -d
```

#### 2. Application Can't Connect to Elasticsearch

**Problem**: Connection refused errors to Elasticsearch.

**Solution**:
```bash
# Check if Elasticsearch is running
curl http://localhost:9200

# Check Docker network
docker network ls | grep elk

# Verify application is on correct network
docker inspect cerebrops-app | grep NetworkMode

# Restart application with correct network
docker run -d --name cerebrops-app \
  --network elk_elk-network \
  -p 5000:5000 cerebrops:latest
```

#### 3. Slack Alerts Not Working

**Problem**: Alerts not being sent to Slack.

**Solution**:
```bash
# Test webhook URL directly
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test message"}' \
  YOUR_WEBHOOK_URL

# Check environment variable
echo $SLACK_WEBHOOK_URL

# Test from application
python -c "
import os
from alerts import SlackAlerter
webhook = os.getenv('SLACK_WEBHOOK_URL')
print(f'Webhook URL: {webhook}')
alerter = SlackAlerter(webhook)
result = alerter.send_slack_alert('Test alert', 'low')
print(f'Result: {result}')
"
```

#### 4. High Memory Usage

**Problem**: System consuming too much memory.

**Solution**:
```bash
# Check memory usage
docker stats --no-stream

# Reduce Elasticsearch heap size
# Edit elk/docker-compose.yml:
# ES_JAVA_OPTS: "-Xms1g -Xmx1g"  # Reduce from 2g to 1g

# Limit application resources
docker run -d --name cerebrops-app \
  --memory="512m" --cpus="1.0" \
  cerebrops:latest
```

#### 5. Kubernetes Pods Failing

**Problem**: Pods in CrashLoopBackOff or Pending state.

**Solution**:
```bash
# Check pod status and events
kubectl get pods -n cerebrops
kubectl describe pod <pod-name> -n cerebrops
kubectl get events -n cerebrops --sort-by='.lastTimestamp'

# Check logs
kubectl logs <pod-name> -n cerebrops

# Check resource availability
kubectl describe node
kubectl top nodes

# Check secrets
kubectl get secrets -n cerebrops
kubectl describe secret cerebrops-secrets -n cerebrops
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Application debug mode
python monitor.py --debug --single-check

# Container debug mode
docker run -it --rm \
  -e LOG_LEVEL=DEBUG \
  --entrypoint /bin/bash \
  cerebrops:latest

# Kubernetes debug mode
kubectl set env deployment/cerebrops-app LOG_LEVEL=DEBUG -n cerebrops
```

### Performance Tuning

#### For High-Traffic Environments

```bash
# Increase application replicas
kubectl scale deployment/cerebrops-app --replicas=5 -n cerebrops

# Tune monitoring interval
python monitor.py --interval 600  # 10 minutes instead of 5

# Optimize Elasticsearch
# Edit elk/elasticsearch/config/elasticsearch.yml:
# indices.memory.index_buffer_size: 20%
# indices.memory.min_index_buffer_size: 96mb
```

#### For Resource-Constrained Environments

```bash
# Reduce ELK stack resources
# Edit elk/docker-compose.yml:
# ES_JAVA_OPTS: "-Xms512m -Xmx512m"

# Use single ELK node
# Remove replica settings from elasticsearch.yml

# Reduce monitoring frequency
python monitor.py --interval 900  # 15 minutes
```

### Getting Support

1. **Check Logs**: Always start with application and container logs
2. **Review Configuration**: Verify all environment variables and config files
3. **Test Components**: Test individual components (app, ELK, alerts) separately
4. **Resource Check**: Monitor CPU, memory, and disk usage
5. **Network Connectivity**: Verify all services can communicate

For additional support:
- Check the GitHub Issues page
- Review the comprehensive README.md
- Consult the API documentation
- Use debug mode for detailed logging

---

**🎉 You're now ready to deploy and operate CerebrOps successfully!**

This guide covers all aspects of running the system. Start with the Quick Start section, then dive deeper into the areas relevant to your deployment scenario.
