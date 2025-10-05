# 📋 CerebrOps Operations Manual

This manual provides detailed instructions for day-to-day operations, maintenance, and administration of the CerebrOps system.

## Daily Operations Checklist

### Morning Health Check (5 minutes)

```bash
#!/bin/bash
# Save as daily_health_check.sh

echo "🔍 CerebrOps Daily Health Check - $(date)"
echo "================================================"

# 1. Check application status
echo "1. Application Health:"
if curl -s http://localhost:5000/health | grep -q "healthy"; then
    echo "   ✅ Application is healthy"
else
    echo "   ❌ Application health check failed"
fi

# 2. Check ELK stack
echo "2. ELK Stack Status:"
if curl -s http://localhost:9200/_cluster/health | grep -q "green\|yellow"; then
    echo "   ✅ Elasticsearch is responding"
else
    echo "   ❌ Elasticsearch is not responding"
fi

if curl -s http://localhost:5601/api/status | grep -q "available"; then
    echo "   ✅ Kibana is available"
else
    echo "   ❌ Kibana is not available"
fi

# 3. Check disk space
echo "3. Disk Space:"
df -h | awk 'NR==1{print "   " $0} /^\/dev/{if($5+0 > 80) print "   ⚠️  " $0; else print "   ✅ " $0}'

# 4. Check recent alerts
echo "4. Recent Alerts (last 24h):"
if [ -f "logs/monitoring.log" ]; then
    alert_count=$(grep -c "ALERT" logs/monitoring.log 2>/dev/null || echo "0")
    echo "   📊 Total alerts: $alert_count"
else
    echo "   ℹ️  No monitoring log found"
fi

# 5. Check running containers/pods
echo "5. Container Status:"
if command -v docker &> /dev/null; then
    docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(cerebrops|elk)"
fi

if command -v kubectl &> /dev/null; then
    echo "   Kubernetes Pods:"
    kubectl get pods -n cerebrops 2>/dev/null || echo "   ℹ️  No Kubernetes deployment found"
fi

echo "================================================"
echo "Health check completed at $(date)"
```

### Weekly Maintenance Tasks

```bash
#!/bin/bash
# Save as weekly_maintenance.sh

echo "🔧 CerebrOps Weekly Maintenance - $(date)"
echo "================================================"

# 1. Clean up old logs
echo "1. Cleaning up old logs..."
find logs/ -name "*.log" -mtime +7 -exec rm {} \;
echo "   ✅ Old logs cleaned"

# 2. Clean up old Elasticsearch indices
echo "2. Cleaning up old Elasticsearch indices..."
# Delete indices older than 30 days
for i in {30..60}; do
    date_str=$(date -d "$i days ago" +%Y.%m.%d)
    curl -X DELETE "localhost:9200/cerebrops-logs-$date_str" 2>/dev/null
    curl -X DELETE "localhost:9200/cerebrops-anomalies-$date_str" 2>/dev/null
done
echo "   ✅ Old indices cleaned"

# 3. Optimize Elasticsearch indices
echo "3. Optimizing Elasticsearch indices..."
curl -X POST "localhost:9200/cerebrops-logs-*/_forcemerge?max_num_segments=1" 2>/dev/null
echo "   ✅ Indices optimized"

# 4. Update anomaly detection model
echo "4. Retraining anomaly detection model..."
python -c "
from anomaly_detector import AnomalyDetector
detector = AnomalyDetector()
if detector.train_model():
    print('   ✅ Model retrained successfully')
else:
    print('   ❌ Model retraining failed')
"

# 5. Generate weekly report
echo "5. Generating weekly report..."
python -c "
import json
from datetime import datetime, timedelta

# Load monitoring results
try:
    with open('logs/monitoring_results.jsonl', 'r') as f:
        results = [json.loads(line) for line in f.readlines()[-1000:]]
    
    # Calculate stats
    total_checks = len(results)
    anomalies = sum(1 for r in results if r.get('anomaly_detection', {}).get('status') == 'anomaly')
    health_issues = sum(1 for r in results if r.get('health_check', {}).get('status') == 'unhealthy')
    
    print(f'   📊 Total monitoring checks: {total_checks}')
    print(f'   🚨 Anomalies detected: {anomalies} ({anomalies/total_checks*100:.1f}%)')
    print(f'   ❤️  Health issues: {health_issues} ({health_issues/total_checks*100:.1f}%)')
    print('   ✅ Weekly report generated')
except:
    print('   ⚠️  Unable to generate report - no monitoring data')
"

echo "================================================"
echo "Weekly maintenance completed at $(date)"
```

## Command Reference

### Application Management

#### Starting the System
```bash
# Development environment
docker-compose -f docker-compose.dev.yml up -d

# Production environment
python monitor.py --interval 300 &

# Kubernetes
kubectl apply -f k8s/ -n cerebrops
```

#### Stopping the System
```bash
# Development environment
docker-compose -f docker-compose.dev.yml down

# Stop monitoring process
pkill -f "python monitor.py"

# Kubernetes
kubectl delete -f k8s/ -n cerebrops
```

#### Restarting Services
```bash
# Restart application only
docker restart cerebrops-app

# Restart ELK stack
cd elk && docker-compose restart

# Restart Kubernetes deployment
kubectl rollout restart deployment/cerebrops-app -n cerebrops
```

### Monitoring Commands

#### Manual Health Checks
```bash
# Application health
curl -s http://localhost:5000/health | jq

# Detailed metrics
curl -s http://localhost:5000/metrics | jq

# Recent logs
curl -s http://localhost:5000/logs | jq '.logs[0:5]'

# Elasticsearch cluster health
curl -s http://localhost:9200/_cluster/health | jq
```

#### Run Anomaly Detection
```bash
# Single check with results
python monitor.py --single-check | jq

# Debug mode
python monitor.py --debug --single-check

# Continuous monitoring (background)
nohup python monitor.py --interval 300 > monitoring.log 2>&1 &
```

#### Test Alerts
```bash
# Test Slack webhook
python -c "
from alerts import SlackAlerter
alerter = SlackAlerter()
alerter.send_slack_alert('Manual test alert 🧠', 'low')
"

# Simulate application error
curl http://localhost:5000/simulate-error
```

### Log Management

#### View Logs
```bash
# Application logs
tail -f logs/app.log

# Monitoring logs
tail -f logs/monitoring.log

# Container logs
docker logs -f cerebrops-app

# Kubernetes logs
kubectl logs -f deployment/cerebrops-app -n cerebrops
```

#### Search Logs
```bash
# Search for errors
grep -i error logs/app.log

# Search for anomalies
grep -i anomaly logs/monitoring.log

# Search with context
grep -B5 -A5 "ERROR" logs/app.log

# Search in Elasticsearch
curl -s "localhost:9200/cerebrops-logs-*/_search?q=level:ERROR" | jq
```

#### Log Rotation
```bash
# Rotate application logs
logrotate -f /etc/logrotate.d/cerebrops

# Manual log cleanup
find logs/ -name "*.log" -mtime +7 -delete

# Compress old logs
gzip logs/*.log.1
```

### Database Operations

#### Elasticsearch Management
```bash
# Check indices
curl -s "localhost:9200/_cat/indices?v"

# Check index size
curl -s "localhost:9200/_cat/indices/cerebrops-logs-*?v&s=store.size:desc"

# Delete old indices
curl -X DELETE "localhost:9200/cerebrops-logs-$(date -d '30 days ago' +%Y.%m.%d)"

# Create index template
curl -X PUT "localhost:9200/_template/cerebrops" -H 'Content-Type: application/json' -d'
{
  "index_patterns": ["cerebrops-*"],
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  }
}
'
```

#### Data Export/Import
```bash
# Export data
curl -s "localhost:9200/cerebrops-logs-*/_search?scroll=1m&size=1000" > export.json

# Import data (using elasticdump if available)
elasticdump \
  --input=export.json \
  --output=http://localhost:9200/cerebrops-logs-restored
```

### Performance Monitoring

#### System Resources
```bash
# Docker container stats
docker stats --no-stream cerebrops-app

# Kubernetes pod resources
kubectl top pods -n cerebrops

# System resources
htop  # or top
df -h  # disk usage
free -h  # memory usage
```

#### Application Performance
```bash
# Response time monitoring
curl -w "@curl-format.txt" -s -o /dev/null http://localhost:5000/

# Load testing with Apache Bench
ab -n 100 -c 10 http://localhost:5000/

# Load testing with curl
for i in {1..100}; do curl -s http://localhost:5000/metrics >/dev/null & done
```

### Configuration Management

#### Environment Variables
```bash
# View current environment
docker exec cerebrops-app env | grep -E "(SLACK|APP|ENVIRONMENT)"

# Update environment variable
docker run -d --name cerebrops-app-new \
  -e MONITORING_INTERVAL=600 \
  -p 5000:5000 cerebrops:latest

# Kubernetes environment update
kubectl set env deployment/cerebrops-app MONITORING_INTERVAL=600 -n cerebrops
```

#### Configuration Files
```bash
# Backup configuration
tar -czf config-backup-$(date +%Y%m%d).tar.gz .env k8s/ elk/

# Update configuration
vim .env  # Edit environment
vim elk/elasticsearch/config/elasticsearch.yml  # Edit ES config

# Apply Kubernetes config changes
kubectl apply -f k8s/ -n cerebrops
```

## Scaling Operations

### Horizontal Scaling

#### Docker Compose Scaling
```bash
# Scale application replicas
docker-compose -f docker-compose.dev.yml up -d --scale app=3

# Check scaled containers
docker-compose -f docker-compose.dev.yml ps
```

#### Kubernetes Scaling
```bash
# Scale deployment
kubectl scale deployment/cerebrops-app --replicas=5 -n cerebrops

# Auto-scaling setup
kubectl autoscale deployment cerebrops-app \
  --cpu-percent=70 \
  --min=2 \
  --max=10 \
  -n cerebrops

# Check HPA status
kubectl get hpa -n cerebrops
```

### Vertical Scaling

#### Resource Updates
```bash
# Update container resources
kubectl patch deployment cerebrops-app -n cerebrops -p='
{
  "spec": {
    "template": {
      "spec": {
        "containers": [
          {
            "name": "cerebrops-web",
            "resources": {
              "requests": {"memory": "512Mi", "cpu": "500m"},
              "limits": {"memory": "1Gi", "cpu": "1000m"}
            }
          }
        ]
      }
    }
  }
}'
```

## Security Operations

### Access Control
```bash
# Create service account
kubectl create serviceaccount cerebrops-sa -n cerebrops

# Create RBAC rules
kubectl create role cerebrops-role \
  --verb=get,list,watch \
  --resource=pods,services \
  -n cerebrops

# Bind role to service account
kubectl create rolebinding cerebrops-binding \
  --role=cerebrops-role \
  --serviceaccount=cerebrops:cerebrops-sa \
  -n cerebrops
```

### Secrets Management
```bash
# Update secrets
kubectl create secret generic cerebrops-secrets \
  --from-literal=slack-webhook-url='NEW_URL' \
  --dry-run=client -o yaml | kubectl apply -f - -n cerebrops

# Rotate secrets
kubectl delete secret cerebrops-secrets -n cerebrops
kubectl create secret generic cerebrops-secrets \
  --from-literal=slack-webhook-url='ROTATED_URL' \
  -n cerebrops
```

### Security Scanning
```bash
# Scan Docker image
trivy image cerebrops:latest

# Scan filesystem
trivy fs .

# Kubernetes security scan
kubectl run --rm -it security-scan \
  --image=aquasec/trivy:latest \
  --restart=Never -- image cerebrops:latest
```

## Backup and Recovery

### Backup Procedures
```bash
#!/bin/bash
# Complete backup script

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/cerebrops_$BACKUP_DATE"

mkdir -p "$BACKUP_DIR"

# 1. Backup configuration
echo "Backing up configuration..."
cp -r .env k8s/ elk/ scripts/ "$BACKUP_DIR/"

# 2. Backup Elasticsearch data
echo "Backing up Elasticsearch data..."
docker exec elk_elasticsearch_1 \
  /usr/share/elasticsearch/bin/elasticsearch-dump \
  --input=http://localhost:9200 \
  --output="$BACKUP_DIR/elasticsearch_backup.json"

# 3. Backup application logs
echo "Backing up application logs..."
cp -r logs/ "$BACKUP_DIR/"

# 4. Create archive
echo "Creating backup archive..."
tar -czf "cerebrops_backup_$BACKUP_DATE.tar.gz" -C /backups "cerebrops_$BACKUP_DATE"
rm -rf "$BACKUP_DIR"

echo "Backup completed: cerebrops_backup_$BACKUP_DATE.tar.gz"
```

### Recovery Procedures
```bash
#!/bin/bash
# Recovery script

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file.tar.gz>"
    exit 1
fi

echo "Starting recovery from $BACKUP_FILE..."

# 1. Stop services
echo "Stopping services..."
docker-compose -f docker-compose.dev.yml down
pkill -f "python monitor.py"

# 2. Extract backup
echo "Extracting backup..."
tar -xzf "$BACKUP_FILE"

# 3. Restore configuration
echo "Restoring configuration..."
BACKUP_DIR=$(basename "$BACKUP_FILE" .tar.gz)
cp -r "$BACKUP_DIR"/.env ./
cp -r "$BACKUP_DIR"/k8s/ ./
cp -r "$BACKUP_DIR"/elk/ ./

# 4. Restore logs
echo "Restoring logs..."
cp -r "$BACKUP_DIR"/logs/ ./

# 5. Start services
echo "Starting services..."
docker-compose -f docker-compose.dev.yml up -d

# 6. Restore Elasticsearch data
echo "Restoring Elasticsearch data..."
sleep 30  # Wait for ES to start
curl -X POST "localhost:9200/_all/_close"
# Restore data here
curl -X POST "localhost:9200/_all/_open"

echo "Recovery completed!"
```

## Alerting and Notifications

### Alert Configuration
```bash
# Test different alert severities
python -c "
from alerts import SlackAlerter
alerter = SlackAlerter()

# Test all severity levels
severities = ['low', 'medium', 'high', 'critical']
for severity in severities:
    alerter.send_slack_alert(f'Test {severity} alert', severity)
    print(f'Sent {severity} alert')
"

# Configure alert thresholds
# Edit anomaly_detector.py
vim anomaly_detector.py
```

### Custom Alert Rules
```python
# Add to alerts.py
def send_custom_business_alert(self, metric_name, current_value, threshold):
    if current_value > threshold:
        message = f"Business metric alert: {metric_name} is {current_value}, exceeding threshold of {threshold}"
        severity = 'high' if current_value > threshold * 1.5 else 'medium'
        self.send_slack_alert(message, severity)
```

This operations manual provides comprehensive guidance for managing CerebrOps in production. Keep it handy for day-to-day operations and refer to specific sections as needed.
