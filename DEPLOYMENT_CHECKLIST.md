# ✅ CI/CD Pipeline Deployment Checklist

Use this checklist to ensure your CerebrOps CI/CD pipeline is production-ready.

## Pre-Deployment Checklist

### 🔧 Infrastructure Setup

- [ ] **Kubernetes Cluster Ready**
  - [ ] Cluster is running and accessible
  - [ ] kubectl is installed and configured
  - [ ] Cluster has sufficient resources (8GB RAM, 4 CPU minimum)
  - [ ] Storage class is configured for PersistentVolumeClaims
  
- [ ] **Docker Registry Access**
  - [ ] GitHub Container Registry (ghcr.io) access confirmed
  - [ ] Or alternative registry configured (Docker Hub, ECR, GCR, ACR)
  - [ ] Registry credentials are set up

- [ ] **Monitoring Infrastructure** (Optional but Recommended)
  - [ ] Prometheus installed or planned
  - [ ] Grafana installed or planned
  - [ ] ELK stack installed or planned

### 🔐 Secrets and Credentials

- [ ] **GitHub Secrets Configured**
  ```bash
  # Navigate to: Repository → Settings → Secrets and variables → Actions
  ```
  - [ ] `K8S_SERVER` - Kubernetes API server URL
  - [ ] `K8S_TOKEN` - Kubernetes service account token
  - [ ] `SLACK_WEBHOOK_URL` - Slack webhook for alerts (optional)
  - [ ] `APP_URL` - Production URL (optional)

- [ ] **Kubernetes Secrets Created**
  ```bash
  kubectl create secret generic cerebrops-secrets \
    --from-literal=slack-webhook-url='YOUR_URL' \
    -n cerebrops
  ```
  - [ ] cerebrops-secrets created in cluster
  - [ ] Secret values are base64 encoded in k8s/secrets.yaml

- [ ] **Service Account Created**
  ```bash
  kubectl create serviceaccount cerebrops-deployer -n cerebrops
  kubectl create clusterrolebinding cerebrops-deployer-binding \
    --clusterrole=cluster-admin \
    --serviceaccount=cerebrops:cerebrops-deployer
  ```
  - [ ] Service account exists
  - [ ] Token generated and added to GitHub secrets

### 📝 Configuration Files

- [ ] **Environment Variables**
  - [ ] `.env` file created locally (from `.env.example`)
  - [ ] All required variables filled in
  - [ ] `.env` is in `.gitignore` (security)

- [ ] **Kubernetes Manifests Updated**
  - [ ] Image registry updated in `k8s/deployment.yaml`
  - [ ] Namespace is correct in all manifests
  - [ ] Resource limits are appropriate for your cluster
  - [ ] Secrets reference is correct

- [ ] **Pipeline Configuration**
  - [ ] `.github/workflows/ci-cd.yml` reviewed
  - [ ] Commented kubectl commands uncommented (lines 130-145)
  - [ ] Image registry matches your setup
  - [ ] Branch protection rules configured

### 🧪 Testing

- [ ] **Local Tests Pass**
  ```bash
  pytest tests/ -v --cov
  ```
  - [ ] All unit tests pass
  - [ ] Code coverage is acceptable (>70%)
  - [ ] No flake8 errors

- [ ] **Docker Build Works**
  ```bash
  docker build -t cerebrops:test .
  ```
  - [ ] Image builds successfully
  - [ ] No build errors or warnings
  - [ ] Image size is reasonable (<500MB)

- [ ] **Local Run Works**
  ```bash
  docker run -d -p 5000:5000 --env-file .env cerebrops:test
  curl http://localhost:5000/health
  ```
  - [ ] Container starts successfully
  - [ ] Health endpoint returns 200
  - [ ] No error logs

## Deployment Checklist

### 🚀 Initial Deployment

- [ ] **Namespace Created**
  ```bash
  kubectl create namespace cerebrops
  ```

- [ ] **PersistentVolumeClaims Created**
  ```bash
  kubectl apply -f k8s/persistent-volume.yaml -n cerebrops
  ```
  - [ ] PVCs created successfully
  - [ ] Storage is available

- [ ] **Secrets Applied**
  ```bash
  kubectl apply -f k8s/secrets.yaml -n cerebrops
  ```
  - [ ] Secrets exist in cluster
  - [ ] No sensitive data in Git

- [ ] **Application Deployed**
  ```bash
  kubectl apply -f k8s/deployment.yaml -n cerebrops
  ```
  - [ ] Deployment created
  - [ ] Pods are running
  - [ ] Service is accessible

- [ ] **CronJobs Configured**
  ```bash
  kubectl apply -f k8s/cronjobs.yaml -n cerebrops
  ```
  - [ ] Anomaly detection job created
  - [ ] Log cleanup job created
  - [ ] Jobs are scheduled correctly

### 🔍 Verification

- [ ] **Pods Status**
  ```bash
  kubectl get pods -n cerebrops
  ```
  - [ ] All pods are in `Running` state
  - [ ] No `CrashLoopBackOff` or `Error` states
  - [ ] Replicas match desired count

- [ ] **Service Status**
  ```bash
  kubectl get svc -n cerebrops
  ```
  - [ ] Service has ClusterIP assigned
  - [ ] Endpoints are available

- [ ] **Health Checks**
  ```bash
  kubectl port-forward service/cerebrops-service 8080:80 -n cerebrops
  curl http://localhost:8080/health
  ```
  - [ ] Health endpoint returns 200 OK
  - [ ] Response includes status information

- [ ] **Logs Check**
  ```bash
  kubectl logs -f deployment/cerebrops-app -n cerebrops
  ```
  - [ ] No critical errors in logs
  - [ ] Application started successfully
  - [ ] All components initialized

### 📊 Smoke Tests

- [ ] **Run Automated Smoke Tests**
  ```bash
  chmod +x scripts/smoke-tests.sh
  ./scripts/smoke-tests.sh
  ```
  - [ ] Health check passes
  - [ ] Metrics endpoint accessible
  - [ ] Dashboard loads
  - [ ] Logs endpoint works
  - [ ] Pipeline status endpoint responds
  - [ ] Response time is acceptable

- [ ] **Manual Smoke Tests**
  - [ ] Dashboard UI loads correctly
  - [ ] No JavaScript errors in browser console
  - [ ] Metrics are being collected
  - [ ] Logs are being aggregated

### 🔔 Alert Testing

- [ ] **Slack Integration**
  ```bash
  # Test alert
  kubectl exec -it deployment/cerebrops-app -n cerebrops -- python -c "
  from alerts import SlackAlerter
  import os
  alerter = SlackAlerter(os.getenv('SLACK_WEBHOOK_URL'))
  alerter.send_slack_alert('Test Alert', 'low')
  "
  ```
  - [ ] Alert received in Slack channel
  - [ ] Alert formatting is correct
  - [ ] Channel is correct

- [ ] **Anomaly Detection Test**
  ```bash
  kubectl create job --from=cronjob/cerebrops-anomaly-detection test-anomaly -n cerebrops
  kubectl logs job/test-anomaly -n cerebrops
  ```
  - [ ] Job runs successfully
  - [ ] No errors in job logs
  - [ ] Alerts sent if anomalies detected

## CI/CD Pipeline Checklist

### 🔄 Pipeline Stages

- [ ] **Test Stage**
  - [ ] Unit tests run automatically
  - [ ] Code coverage is calculated
  - [ ] Linting checks pass
  - [ ] Test results are uploaded

- [ ] **Build Stage**
  - [ ] Docker image builds successfully
  - [ ] Image is tagged correctly
  - [ ] Image is pushed to registry
  - [ ] Build cache is utilized

- [ ] **Security Scan Stage**
  - [ ] Trivy scan runs on image
  - [ ] Filesystem scan completes
  - [ ] SARIF results uploaded
  - [ ] Critical vulnerabilities fail build

- [ ] **Performance Test Stage**
  - [ ] k6 tests run
  - [ ] Performance metrics collected
  - [ ] Thresholds are met

- [ ] **Deploy Stage**
  - [ ] Only runs on main branch
  - [ ] kubectl configured correctly
  - [ ] Image tag updated in deployment
  - [ ] Manifests applied successfully
  - [ ] Rollout status checked

- [ ] **Anomaly Detection Stage**
  - [ ] Runs after successful deployment
  - [ ] Connects to deployed application
  - [ ] Sends alerts if issues found
  - [ ] Deployment notification sent

### 🔧 Pipeline Configuration

- [ ] **Branch Protection**
  - [ ] Required checks configured
  - [ ] PR reviews required
  - [ ] Status checks must pass
  - [ ] Branches must be up to date

- [ ] **Workflow Permissions**
  - [ ] Read and write permissions enabled
  - [ ] Packages write permission granted
  - [ ] GITHUB_TOKEN has correct scope

- [ ] **Workflow Triggers**
  - [ ] Push to main triggers full pipeline
  - [ ] Push to develop triggers test + build
  - [ ] Pull requests trigger tests
  - [ ] Manual workflow dispatch enabled (optional)

## Post-Deployment Checklist

### 📈 Monitoring Setup

- [ ] **Application Monitoring**
  - [ ] Prometheus scraping metrics
  - [ ] Grafana dashboards created
  - [ ] Alerts configured in Prometheus
  - [ ] SLOs/SLIs defined

- [ ] **Log Aggregation**
  - [ ] Logs forwarded to ELK/Loki
  - [ ] Log retention policy set
  - [ ] Log rotation configured
  - [ ] Log search works

- [ ] **Health Monitoring**
  - [ ] Liveness probes working
  - [ ] Readiness probes working
  - [ ] Health endpoint monitored
  - [ ] Uptime tracking configured

### 🔄 Operational Procedures

- [ ] **Documentation Updated**
  - [ ] Deployment runbook created
  - [ ] Rollback procedure documented
  - [ ] Troubleshooting guide updated
  - [ ] Architecture diagrams current

- [ ] **Backup Strategy**
  - [ ] PersistentVolume backup configured
  - [ ] Configuration backup automated
  - [ ] Disaster recovery plan documented
  - [ ] Backup restoration tested

- [ ] **Scaling Configuration**
  - [ ] HorizontalPodAutoscaler configured (optional)
  - [ ] Resource limits appropriate
  - [ ] Node affinity/anti-affinity set
  - [ ] Pod disruption budget defined

### 🔐 Security Hardening

- [ ] **Security Measures**
  - [ ] Non-root user in container
  - [ ] Read-only root filesystem (if possible)
  - [ ] Security context defined
  - [ ] Network policies configured
  - [ ] Pod security policies/admission controllers

- [ ] **Secrets Management**
  - [ ] Secrets not in Git
  - [ ] Secrets encrypted at rest
  - [ ] Secret rotation policy
  - [ ] Access control configured

- [ ] **Compliance**
  - [ ] Security scanning in CI/CD
  - [ ] Vulnerability reports reviewed
  - [ ] Dependency updates scheduled
  - [ ] Compliance requirements met

## Production Readiness Checklist

### ✅ Final Checks Before Production

- [ ] **Performance**
  - [ ] Load testing completed
  - [ ] Performance benchmarks met
  - [ ] Resource usage is acceptable
  - [ ] No memory leaks detected

- [ ] **Reliability**
  - [ ] Multi-replica deployment tested
  - [ ] Pod restarts work correctly
  - [ ] Rolling updates successful
  - [ ] Rollback tested

- [ ] **Observability**
  - [ ] All metrics being collected
  - [ ] Logs are structured and searchable
  - [ ] Traces configured (if using distributed tracing)
  - [ ] Dashboards are meaningful

- [ ] **Documentation**
  - [ ] README is complete and accurate
  - [ ] API documentation is current
  - [ ] Deployment guide is tested
  - [ ] Troubleshooting guide is helpful

- [ ] **Team Readiness**
  - [ ] Team trained on operations
  - [ ] On-call rotation established
  - [ ] Runbooks are accessible
  - [ ] Escalation procedures defined

### 🚨 Emergency Procedures

- [ ] **Rollback Plan**
  ```bash
  kubectl rollout undo deployment/cerebrops-app -n cerebrops
  ```
  - [ ] Tested and documented
  - [ ] Team knows how to execute
  - [ ] Recovery time objective (RTO) defined

- [ ] **Incident Response**
  - [ ] Incident response plan created
  - [ ] Communication channels defined
  - [ ] Post-mortem template ready
  - [ ] Contact information updated

## Sign-Off

### Development Team
- [ ] Code reviewed and approved
- [ ] Tests passing and coverage acceptable
- [ ] Documentation complete
- Date: ___________  Signature: ___________

### DevOps Team
- [ ] Infrastructure provisioned
- [ ] CI/CD pipeline configured
- [ ] Monitoring and alerting set up
- Date: ___________  Signature: ___________

### Security Team
- [ ] Security scan passed
- [ ] Secrets properly managed
- [ ] Compliance requirements met
- Date: ___________  Signature: ___________

### Product Owner
- [ ] Acceptance criteria met
- [ ] Ready for production deployment
- [ ] Rollback plan approved
- Date: ___________  Signature: ___________

---

## Quick Reference Commands

```bash
# Check deployment status
kubectl get all -n cerebrops

# View logs
kubectl logs -f deployment/cerebrops-app -n cerebrops

# Port forward for testing
kubectl port-forward service/cerebrops-service 8080:80 -n cerebrops

# Restart deployment
kubectl rollout restart deployment/cerebrops-app -n cerebrops

# Scale deployment
kubectl scale deployment/cerebrops-app --replicas=3 -n cerebrops

# Rollback deployment
kubectl rollout undo deployment/cerebrops-app -n cerebrops

# Check pipeline status
# Go to: https://github.com/YOUR_USERNAME/CerebrOps/actions
```

---

**Status**: [ ] Not Started | [ ] In Progress | [ ] Completed | [ ] Blocked

**Notes**:
___________________________________________________________________________
___________________________________________________________________________
___________________________________________________________________________
