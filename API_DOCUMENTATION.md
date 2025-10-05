# 🔌 CerebrOps API Documentation

This document provides comprehensive API documentation for developers who want to integrate with or extend the CerebrOps system.

## Table of Contents

- [Authentication](#authentication)
- [REST API Endpoints](#rest-api-endpoints)
- [Response Formats](#response-formats)
- [Error Handling](#error-handling)
- [Python SDK](#python-sdk)
- [Integration Examples](#integration-examples)
- [Webhooks](#webhooks)

## Base URL

- **Development**: `http://localhost:5000`
- **Production**: `https://your-cerebrops-domain.com`

## Authentication

Currently, CerebrOps API endpoints are open for internal use. For production deployments, consider implementing authentication:

```bash
# Future authentication header
Authorization: Bearer YOUR_API_TOKEN
```

## REST API Endpoints

### Health and Status Endpoints

#### GET /health
Returns the current health status of the application.

**Response:**
```json
{
  "status": "healthy",
  "checks": [
    {
      "name": "database",
      "status": "ok"
    },
    {
      "name": "cache",
      "status": "ok"
    }
  ]
}
```

**cURL Example:**
```bash
curl -X GET http://localhost:5000/health
```

#### GET /metrics
Returns current system metrics in JSON format.

**Response:**
```json
{
  "timestamp": "2025-09-21T10:30:00Z",
  "cpu_usage": 45.2,
  "memory_usage": 62.1,
  "disk_usage": 78.5,
  "request_count": 1247,
  "error_rate": 2.1,
  "response_time": 0.245
}
```

**cURL Example:**
```bash
curl -X GET http://localhost:5000/metrics
```

#### GET /logs
Returns recent application logs.

**Query Parameters:**
- `limit` (optional): Number of logs to return (default: 20, max: 1000)
- `level` (optional): Filter by log level (DEBUG, INFO, WARNING, ERROR)
- `since` (optional): ISO timestamp to get logs since

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2025-09-21T10:30:00Z",
      "level": "INFO",
      "message": "User authentication successful",
      "module": "cerebrops"
    }
  ],
  "total": 1,
  "limit": 20
}
```

**cURL Examples:**
```bash
# Get recent logs
curl -X GET http://localhost:5000/logs

# Get last 50 error logs
curl -X GET "http://localhost:5000/logs?limit=50&level=ERROR"

# Get logs since specific time
curl -X GET "http://localhost:5000/logs?since=2025-09-21T09:00:00Z"
```

### Dashboard Endpoint

#### GET /
Returns the main dashboard HTML page with embedded metrics and charts.

**Response:** HTML content

**cURL Example:**
```bash
curl -X GET http://localhost:5000/
```

### Pipeline Management

#### GET /api/pipeline-status
Returns current CI/CD pipeline status.

**Response:**
```json
{
  "pipeline_id": "pipeline-4532",
  "status": "running",
  "stage": "test",
  "duration": 245,
  "commit_hash": "abc1234",
  "branch": "main",
  "started_at": "2025-09-21T10:25:00Z",
  "stages": [
    {
      "name": "build",
      "status": "success",
      "duration": 120
    },
    {
      "name": "test", 
      "status": "running",
      "duration": 125
    }
  ]
}
```

#### POST /api/pipeline-trigger
Triggers a pipeline run (if implemented).

**Request Body:**
```json
{
  "branch": "main",
  "commit_hash": "abc1234"
}
```

**Response:**
```json
{
  "pipeline_id": "pipeline-4533",
  "status": "triggered",
  "message": "Pipeline started successfully"
}
```

### Testing and Simulation

#### GET /simulate-error
Simulates an application error for testing anomaly detection.

**Response:**
```json
{
  "status": "error simulated",
  "metrics": {
    "timestamp": "2025-09-21T10:30:00Z",
    "cpu_usage": 95.2,
    "memory_usage": 88.7,
    "disk_usage": 97.1,
    "error_rate": 25.3
  }
}
```

**HTTP Status:** 500 (Internal Server Error)

## Response Formats

### Success Response Format
All successful API responses follow this structure:

```json
{
  "status": "success",
  "data": { ... },
  "timestamp": "2025-09-21T10:30:00Z",
  "request_id": "req-abc123"
}
```

### Error Response Format
All error responses follow this structure:

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request parameters are invalid",
    "details": { ... }
  },
  "timestamp": "2025-09-21T10:30:00Z",
  "request_id": "req-abc123"
}
```

### Common HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request |
| 404 | Not Found |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

## Error Handling

### Error Codes

| Error Code | Description |
|------------|-------------|
| `INVALID_REQUEST` | Request parameters are invalid |
| `SERVICE_UNAVAILABLE` | External service is unavailable |
| `INTERNAL_ERROR` | Internal server error |
| `NOT_FOUND` | Requested resource not found |
| `RATE_LIMITED` | Too many requests |

### Example Error Responses

```json
// 400 Bad Request
{
  "status": "error",
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid limit parameter",
    "details": {
      "parameter": "limit",
      "value": "invalid",
      "expected": "integer between 1 and 1000"
    }
  }
}

// 503 Service Unavailable
{
  "status": "error",
  "error": {
    "code": "SERVICE_UNAVAILABLE", 
    "message": "Elasticsearch service is unavailable",
    "details": {
      "service": "elasticsearch",
      "retry_after": "60s"
    }
  }
}
```

## Python SDK

### Basic Usage

```python
import requests
from typing import Dict, List, Optional

class CerebrOpsClient:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def get_health(self) -> Dict:
        """Get application health status"""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def get_metrics(self) -> Dict:
        """Get current system metrics"""
        response = self.session.get(f"{self.base_url}/metrics")
        response.raise_for_status()
        return response.json()
    
    def get_logs(self, limit: int = 20, level: Optional[str] = None, 
                 since: Optional[str] = None) -> Dict:
        """Get application logs with optional filtering"""
        params = {"limit": limit}
        if level:
            params["level"] = level
        if since:
            params["since"] = since
        
        response = self.session.get(f"{self.base_url}/logs", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_pipeline_status(self) -> Dict:
        """Get CI/CD pipeline status"""
        response = self.session.get(f"{self.base_url}/api/pipeline-status")
        response.raise_for_status()
        return response.json()
    
    def simulate_error(self) -> Dict:
        """Simulate an error for testing"""
        response = self.session.get(f"{self.base_url}/simulate-error")
        # Note: This endpoint returns 500, so we handle it specially
        return response.json()

# Usage example
client = CerebrOpsClient("http://localhost:5000")

# Check health
health = client.get_health()
print(f"Health status: {health['status']}")

# Get metrics
metrics = client.get_metrics()
print(f"CPU Usage: {metrics['cpu_usage']}%")

# Get recent error logs
logs = client.get_logs(limit=10, level="ERROR")
print(f"Found {len(logs['logs'])} error logs")
```

### Advanced SDK Features

```python
import asyncio
import aiohttp
from datetime import datetime, timedelta

class AsyncCerebrOpsClient:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def get_metrics(self) -> Dict:
        async with self.session.get(f"{self.base_url}/metrics") as response:
            response.raise_for_status()
            return await response.json()
    
    async def monitor_continuously(self, interval: int = 60):
        """Continuously monitor metrics"""
        while True:
            try:
                metrics = await self.get_metrics()
                yield metrics
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"Error fetching metrics: {e}")
                await asyncio.sleep(interval)

# Usage
async def main():
    async with AsyncCerebrOpsClient() as client:
        async for metrics in client.monitor_continuously(30):
            print(f"CPU: {metrics['cpu_usage']}%, Memory: {metrics['memory_usage']}%")

# asyncio.run(main())
```

## Integration Examples

### Prometheus Integration

```python
# prometheus_exporter.py
from prometheus_client import start_http_server, Gauge
import time
import requests

# Create Prometheus metrics
cpu_usage = Gauge('cerebrops_cpu_usage_percent', 'CPU usage percentage')
memory_usage = Gauge('cerebrops_memory_usage_percent', 'Memory usage percentage')
error_rate = Gauge('cerebrops_error_rate_percent', 'Error rate percentage')

def collect_metrics():
    """Collect metrics from CerebrOps and expose to Prometheus"""
    try:
        response = requests.get('http://localhost:5000/metrics')
        response.raise_for_status()
        metrics = response.json()
        
        cpu_usage.set(metrics['cpu_usage'])
        memory_usage.set(metrics['memory_usage'])
        error_rate.set(metrics['error_rate'])
        
        print(f"Updated metrics: CPU={metrics['cpu_usage']}%, Memory={metrics['memory_usage']}%")
    except Exception as e:
        print(f"Error collecting metrics: {e}")

if __name__ == '__main__':
    # Start Prometheus metrics server
    start_http_server(8000)
    
    # Collect metrics every 30 seconds
    while True:
        collect_metrics()
        time.sleep(30)
```

### Grafana Dashboard JSON

```json
{
  "dashboard": {
    "title": "CerebrOps Monitoring",
    "panels": [
      {
        "title": "CPU Usage",
        "type": "stat",
        "targets": [
          {
            "expr": "cerebrops_cpu_usage_percent",
            "legendFormat": "CPU %"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 70},
                {"color": "red", "value": 90}
              ]
            }
          }
        }
      }
    ]
  }
}
```

### Custom Alert Integration

```python
# custom_alerts.py
from alerts import SlackAlerter
import requests
import time

class CustomAlertManager:
    def __init__(self, cerebrops_url="http://localhost:5000"):
        self.cerebrops_url = cerebrops_url
        self.slack_alerter = SlackAlerter()
        self.alert_thresholds = {
            'cpu_usage': 80,
            'memory_usage': 85,
            'error_rate': 5
        }
    
    def check_business_metrics(self):
        """Check custom business metrics and send alerts"""
        try:
            # Get metrics from CerebrOps
            response = requests.get(f"{self.cerebrops_url}/metrics")
            response.raise_for_status()
            metrics = response.json()
            
            # Check thresholds
            for metric, threshold in self.alert_thresholds.items():
                if metric in metrics and metrics[metric] > threshold:
                    self.send_business_alert(metric, metrics[metric], threshold)
            
        except Exception as e:
            print(f"Error checking metrics: {e}")
    
    def send_business_alert(self, metric_name, current_value, threshold):
        """Send custom business alert"""
        message = f"🚨 Business Alert: {metric_name.replace('_', ' ').title()} is {current_value:.1f}% (threshold: {threshold}%)"
        severity = 'critical' if current_value > threshold * 1.2 else 'high'
        
        self.slack_alerter.send_slack_alert(message, severity)
        print(f"Sent business alert for {metric_name}")

# Usage
if __name__ == '__main__':
    alert_manager = CustomAlertManager()
    
    while True:
        alert_manager.check_business_metrics()
        time.sleep(300)  # Check every 5 minutes
```

### Jenkins Integration

```groovy
// Jenkinsfile
pipeline {
    agent any
    
    stages {
        stage('Deploy') {
            steps {
                // Your deployment steps
                sh 'kubectl apply -f k8s/'
            }
        }
        
        stage('Health Check') {
            steps {
                script {
                    // Wait for deployment and check health
                    sh 'kubectl wait --for=condition=available deployment/cerebrops-app'
                    
                    // Check application health via API
                    def response = sh(
                        script: 'curl -s http://cerebrops.local/health',
                        returnStdout: true
                    )
                    
                    def health = readJSON text: response
                    if (health.status != 'healthy') {
                        error "Application health check failed: ${health.status}"
                    }
                }
            }
        }
        
        stage('Trigger Monitoring') {
            steps {
                // Trigger anomaly detection check
                sh '''
                    python -c "
                    from monitor import CerebrOpsMonitor
                    monitor = CerebrOpsMonitor('http://cerebrops.local')
                    result = monitor.run_single_check()
                    print('Monitoring check completed:', result['timestamp'])
                    "
                '''
            }
        }
    }
    
    post {
        always {
            // Send deployment notification
            sh '''
                python -c "
                from alerts import SlackAlerter
                alerter = SlackAlerter()
                status = '${currentBuild.result}' or 'SUCCESS'
                message = f'🚀 Deployment {status.lower()}: Build #${BUILD_NUMBER}'
                severity = 'low' if status == 'SUCCESS' else 'high'
                alerter.send_slack_alert(message, severity)
                "
            '''
        }
    }
}
```

### Terraform Integration

```hcl
# terraform/main.tf
resource "kubernetes_deployment" "cerebrops" {
  metadata {
    name      = "cerebrops-app"
    namespace = "cerebrops"
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = {
        app = "cerebrops"
      }
    }

    template {
      metadata {
        labels = {
          app = "cerebrops"
        }
      }

      spec {
        container {
          image = "cerebrops:${var.image_tag}"
          name  = "cerebrops-web"

          port {
            container_port = 5000
          }

          env {
            name = "SLACK_WEBHOOK_URL"
            value_from {
              secret_key_ref {
                name = "cerebrops-secrets"
                key  = "slack-webhook-url"
              }
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 5000
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }
        }
      }
    }
  }
}

# Output the service endpoint
output "cerebrops_endpoint" {
  value = "http://${kubernetes_service.cerebrops.status.0.load_balancer.0.ingress.0.ip}"
}
```

## Webhooks

CerebrOps supports outgoing webhooks for integration with external systems.

### Webhook Configuration

```python
# webhook_config.py
WEBHOOK_CONFIG = {
    'endpoints': [
        {
            'url': 'https://your-system.com/cerebrops-webhook',
            'events': ['anomaly_detected', 'health_check_failed'],
            'headers': {
                'Authorization': 'Bearer YOUR_TOKEN',
                'Content-Type': 'application/json'
            }
        }
    ]
}
```

### Webhook Payload Format

```json
{
  "event": "anomaly_detected",
  "timestamp": "2025-09-21T10:30:00Z",
  "source": "cerebrops",
  "data": {
    "anomaly_count": 5,
    "total_data_points": 100,
    "anomaly_percentage": 5.0,
    "severity": "high",
    "affected_metrics": ["cpu_usage", "memory_usage"],
    "recommendations": [
      "High CPU usage detected. Consider scaling up.",
      "Memory usage approaching limits."
    ]
  },
  "metadata": {
    "application_version": "1.0.0",
    "environment": "production"
  }
}
```

### Webhook Handler Example

```python
# webhook_handler.py
from flask import Flask, request, jsonify
import json

app = Flask(__name__)

@app.route('/cerebrops-webhook', methods=['POST'])
def handle_cerebrops_webhook():
    try:
        payload = request.get_json()
        
        event_type = payload.get('event')
        
        if event_type == 'anomaly_detected':
            handle_anomaly_event(payload['data'])
        elif event_type == 'health_check_failed':
            handle_health_event(payload['data'])
        
        return jsonify({'status': 'received'}), 200
        
    except Exception as e:
        print(f"Webhook processing error: {e}")
        return jsonify({'error': 'processing_failed'}), 500

def handle_anomaly_event(data):
    """Handle anomaly detection event"""
    severity = data['severity']
    anomaly_count = data['anomaly_count']
    
    print(f"Received {severity} anomaly alert: {anomaly_count} anomalies detected")
    
    # Your custom logic here
    if severity in ['critical', 'high']:
        # Escalate to on-call engineer
        escalate_to_oncall(data)

def handle_health_event(data):
    """Handle health check failure event"""
    print(f"Health check failed: {data}")
    
    # Your custom logic here
    restart_unhealthy_services(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

This comprehensive API documentation provides everything developers need to integrate with and extend the CerebrOps system. The examples show real-world integration scenarios with popular DevOps tools and platforms.
