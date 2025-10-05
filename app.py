"""
CerebrOps Flask Application
AI-Powered CI/CD Monitoring System
"""

from flask import Flask, jsonify, request, render_template_string
import json
import logging
import os
import time
from datetime import datetime
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/app.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
logger = logging.getLogger('cerebrops')

# In-memory storage for demo purposes
metrics_data = []
health_status = {"status": "healthy", "checks": []}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>CerebrOps - AI-Powered CI/CD Monitoring</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
        .header { text-align: center; color: #2c3e50; margin-bottom: 30px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .metric-card { background: #ecf0f1; padding: 20px; border-radius: 8px; border-left: 4px solid #3498db; }
        .status-healthy { color: #27ae60; font-weight: bold; }
        .status-unhealthy { color: #e74c3c; font-weight: bold; }
        .logs { margin-top: 30px; }
        .log-entry { background: #2c3e50; color: white; padding: 10px; margin: 5px 0; border-radius: 4px; font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 CerebrOps</h1>
            <h2>AI-Powered CI/CD Monitoring System</h2>
            <p>Status: <span class="{{ status_class }}">{{ status }}</span></p>
        </div>
        
        <div class="metrics">
            <div class="metric-card">
                <h3>System Metrics</h3>
                <p><strong>CPU Usage:</strong> {{ cpu_usage }}%</p>
                <p><strong>Memory Usage:</strong> {{ memory_usage }}%</p>
                <p><strong>Disk Usage:</strong> {{ disk_usage }}%</p>
            </div>
            
            <div class="metric-card">
                <h3>Application Health</h3>
                <p><strong>Uptime:</strong> {{ uptime }} seconds</p>
                <p><strong>Request Count:</strong> {{ request_count }}</p>
                <p><strong>Error Rate:</strong> {{ error_rate }}%</p>
            </div>
            
            <div class="metric-card">
                <h3>Pipeline Status</h3>
                <p><strong>Last Build:</strong> {{ last_build }}</p>
                <p><strong>Build Status:</strong> {{ build_status }}</p>
                <p><strong>Tests Passed:</strong> {{ tests_passed }}/{{ total_tests }}</p>
            </div>
        </div>
        
        <div class="logs">
            <h3>Recent Logs</h3>
            {% for log in recent_logs %}
            <div class="log-entry">{{ log }}</div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Main dashboard showing system status and metrics"""
    logger.info("Dashboard accessed")
    
    # Simulate some metrics
    current_time = datetime.now()
    
    # Generate some sample data
    sample_data = {
        'status': 'healthy' if random.random() > 0.1 else 'unhealthy',
        'status_class': 'status-healthy' if random.random() > 0.1 else 'status-unhealthy',
        'cpu_usage': random.randint(20, 80),
        'memory_usage': random.randint(30, 70),
        'disk_usage': random.randint(40, 90),
        'uptime': int(time.time() % 86400),
        'request_count': len(metrics_data),
        'error_rate': random.randint(0, 5),
        'last_build': current_time.strftime('%Y-%m-%d %H:%M:%S'),
        'build_status': 'SUCCESS' if random.random() > 0.2 else 'FAILED',
        'tests_passed': random.randint(18, 20),
        'total_tests': 20,
        'recent_logs': [
            f"{current_time.strftime('%H:%M:%S')} INFO: Application started successfully",
            f"{current_time.strftime('%H:%M:%S')} INFO: Health check passed",
            f"{current_time.strftime('%H:%M:%S')} INFO: Database connection established",
            f"{current_time.strftime('%H:%M:%S')} WARNING: High memory usage detected"
        ]
    }
    
    # Store metrics for anomaly detection
    metrics_data.append({
        'timestamp': current_time.isoformat(),
        'cpu_usage': sample_data['cpu_usage'],
        'memory_usage': sample_data['memory_usage'],
        'disk_usage': sample_data['disk_usage'],
        'error_rate': sample_data['error_rate']
    })
    
    # Keep only last 100 entries
    if len(metrics_data) > 100:
        metrics_data.pop(0)
    
    return render_template_string(HTML_TEMPLATE, **sample_data)

@app.route('/health')
def health_check():
    """Health check endpoint for Kubernetes"""
    logger.info("Health check requested")
    
    health_status["checks"] = [
        {"name": "database", "status": "ok"},
        {"name": "cache", "status": "ok"},
        {"name": "external_api", "status": "ok"}
    ]
    
    return jsonify(health_status)

@app.route('/metrics')
def get_metrics():
    """Get metrics in JSON format for monitoring"""
    logger.info("Metrics requested")
    
    current_metrics = {
        'timestamp': datetime.now().isoformat(),
        'cpu_usage': random.randint(20, 80),
        'memory_usage': random.randint(30, 70),
        'disk_usage': random.randint(40, 90),
        'request_count': len(metrics_data),
        'error_rate': random.randint(0, 5),
        'response_time': random.uniform(0.1, 2.0)
    }
    
    return jsonify(current_metrics)

@app.route('/logs')
def get_logs():
    """Get recent logs for anomaly detection"""
    logger.info("Logs requested")
    
    # Generate sample log entries
    sample_logs = []
    current_time = datetime.now()
    
    log_levels = ['INFO', 'WARNING', 'ERROR', 'DEBUG']
    log_messages = [
        "User authentication successful",
        "Database query executed",
        "Cache miss - fetching from database",
        "High CPU usage detected",
        "Memory allocation successful",
        "Network request timeout",
        "File system operation completed"
    ]
    
    for i in range(20):
        log_entry = {
            'timestamp': current_time.isoformat(),
            'level': random.choice(log_levels),
            'message': random.choice(log_messages),
            'module': 'cerebrops'
        }
        sample_logs.append(log_entry)
    
    return jsonify({'logs': sample_logs})

@app.route('/simulate-error')
def simulate_error():
    """Simulate an error for testing anomaly detection"""
    logger.error("Simulated error occurred")
    
    # Generate some anomalous metrics
    anomalous_metrics = {
        'timestamp': datetime.now().isoformat(),
        'cpu_usage': random.randint(90, 100),
        'memory_usage': random.randint(85, 100),
        'disk_usage': random.randint(95, 100),
        'error_rate': random.randint(20, 50)
    }
    
    metrics_data.append(anomalous_metrics)
    
    return jsonify({'status': 'error simulated', 'metrics': anomalous_metrics}), 500

@app.route('/api/pipeline-status')
def pipeline_status():
    """Get CI/CD pipeline status"""
    logger.info("Pipeline status requested")
    
    pipeline_data = {
        'pipeline_id': f"pipeline-{random.randint(1000, 9999)}",
        'status': random.choice(['running', 'success', 'failed', 'pending']),
        'stage': random.choice(['build', 'test', 'deploy']),
        'duration': random.randint(60, 600),
        'commit_hash': f"abc{random.randint(1000, 9999)}",
        'branch': 'main'
    }
    
    return jsonify(pipeline_data)

if __name__ == '__main__':
    # Create logs directory if it doesn't exist
    os.makedirs('/app/logs', exist_ok=True)
    
    logger.info("Starting CerebrOps application")
    app.run(host='0.0.0.0', port=5000, debug=False)
