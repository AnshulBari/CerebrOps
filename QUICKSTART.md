# 🚀 CerebrOps Quick Start Guide

Welcome to CerebrOps! This guide will get you up and running in minutes.

## Prerequisites Checklist

Before you start, make sure you have:

- [ ] **Docker** and **Docker Compose** installed
- [ ] **Python 3.11+** installed
- [ ] **Git** installed
- [ ] **8GB+ RAM** available (for ELK stack)
- [ ] **Slack webhook URL** (optional, for alerts)

## 5-Minute Setup

### Option 1: Automated Setup (Recommended)

**Linux/macOS:**
```bash
# Make setup script executable
chmod +x scripts/setup.sh

# Run automated setup
./scripts/setup.sh
```

**Windows:**
```powershell
# Run PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Run automated setup
.\scripts\setup.ps1
```

### Option 2: Manual Setup

1. **Clone and Setup Environment:**
```bash
git clone https://github.com/YOUR_USERNAME/CerebrOps.git
cd CerebrOps
cp .env.example .env
# Edit .env file with your Slack webhook URL
```2. **Start ELK Stack:**
   ```bash
   cd elk
   docker-compose up -d
   cd ..
   ```

3. **Install Python Dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Build and Run Application:**
   ```bash
   docker build -t cerebrops:latest .
   docker run -d -p 5000:5000 --name cerebrops-app cerebrops:latest
   ```

## Verification

After setup, verify everything is working:

1. **CerebrOps Dashboard:** http://localhost:5000
2. **Kibana:** http://localhost:5601  
3. **Elasticsearch:** http://localhost:9200

## First Steps

### 1. Run Your First Anomaly Detection

```bash
# Single check
python monitor.py --single-check

# Continuous monitoring (every 5 minutes)
python monitor.py --interval 300
```

### 2. Simulate an Anomaly

Visit http://localhost:5000/simulate-error to trigger a test anomaly and see the system in action!

### 3. Set Up Slack Alerts

1. Create a Slack webhook URL:
   - Go to https://api.slack.com/apps
   - Create new app → Incoming Webhooks
   - Copy webhook URL

2. Update your `.env` file:
   ```bash
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   ```

3. Test alerts:
   ```bash
   python -c "from alerts import SlackAlerter; SlackAlerter().send_slack_alert('Hello from CerebrOps! 🧠', 'low')"
   ```

### 4. Explore the Dashboard

The main dashboard shows:
- **System Metrics:** CPU, Memory, Disk usage
- **Application Health:** Uptime, error rates
- **Pipeline Status:** CI/CD pipeline information
- **Recent Logs:** Application log entries

## What's Next?

### Development Workflow

1. **Make Changes:** Edit the code as needed
2. **Run Tests:** `pytest tests/ -v`
3. **Rebuild:** `docker build -t cerebrops:latest .`
4. **Deploy:** `docker run...` or `kubectl apply -f k8s/`

### Production Deployment

#### Kubernetes
```bash
# Set your Slack webhook URL
export SLACK_WEBHOOK_URL="your-webhook-url"

# Deploy to Kubernetes
./scripts/deploy.sh
```

#### GitHub Actions
1. Add secrets to your GitHub repository:
   - `SLACK_WEBHOOK_URL`
   - `DOCKER_USERNAME` (optional)
   - `DOCKER_TOKEN` (optional)

2. Push to main branch - the CI/CD pipeline will automatically:
   - Run tests
   - Build Docker image
   - Deploy to Kubernetes
   - Run anomaly detection

### Customization

#### Add Custom Metrics
```python
# In anomaly_detector.py
detector.feature_columns.extend(['your_custom_metric'])
```

#### Modify Alert Thresholds
```python
# In anomaly_detector.py
def _calculate_severity(self, anomaly_percentage, scores):
    if anomaly_percentage > 15:  # Custom threshold
        return 'critical'
    # ...
```

#### Custom Slack Messages
```python
# In alerts.py
def send_custom_alert(self, message):
    payload = {
        "text": f"🧠 {message}",
        "username": "CerebrOps-Custom"
    }
    # ...
```

## Troubleshooting

### Common Issues

**ELK Stack won't start:**
```bash
# Increase Docker memory to 8GB
# Check available disk space
df -h

# Restart ELK stack
cd elk && docker-compose restart
```

**Python dependencies fail:**
```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install with no cache
pip install --no-cache-dir -r requirements.txt
```

**Slack alerts not working:**
```bash
# Test webhook URL
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test message"}' \
  YOUR_WEBHOOK_URL
```

### Getting Help

- **Documentation:** Check README.md for detailed information
- **Logs:** Check application logs at `logs/` directory
- **Container Logs:** `docker logs cerebrops-app`
- **Kubernetes Logs:** `kubectl logs -f deployment/cerebrops-app`

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub Repo   │───▶│  GitHub Actions │───▶│   Docker Hub    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐    ┌─────────▼─────────┐
│     Slack       │◀───│   AI Anomaly    │◀───│   Kubernetes     │
│    Alerts       │    │   Detection     │    │    Cluster       │
└─────────────────┘    └─────────────────┘    └─────────┬─────────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐    ┌─────────▼─────────┐
│     Kibana      │◀───│   ELK Stack     │◀───│  CerebrOps App   │
│   Dashboard     │    │   (Logs)        │    │   (Flask)        │
└─────────────────┘    └─────────────────┘    └───────────────────┘
```

## Success! 🎉

You now have a fully functional AI-powered CI/CD monitoring system!

**Key Features Available:**
- 🔍 Real-time monitoring
- 🤖 AI anomaly detection  
- 🚨 Smart Slack alerts
- 📊 Rich dashboards
- 🚀 Automated CI/CD
- 🔒 Security scanning

Happy monitoring! 🧠✨
