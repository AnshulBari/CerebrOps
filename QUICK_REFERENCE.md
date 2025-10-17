# 🚀 CerebrOps CI/CD Quick Reference

## ⚡ Quick Setup (5 Minutes)

### 1. Configure GitHub Secrets
```
Repository → Settings → Secrets and variables → Actions → New repository secret
```

| Secret Name | How to Get It |
|------------|---------------|
| `K8S_SERVER` | `kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'` |
| `K8S_TOKEN` | `kubectl create token cerebrops-deployer -n cerebrops --duration=876000h` |
| `SLACK_WEBHOOK_URL` | Get from https://api.slack.com/apps (optional) |

### 2. Create Kubernetes Service Account
```bash
kubectl create namespace cerebrops
kubectl create serviceaccount cerebrops-deployer -n cerebrops
kubectl create clusterrolebinding cerebrops-deployer-binding \
  --clusterrole=cluster-admin \
  --serviceaccount=cerebrops:cerebrops-deployer
kubectl create token cerebrops-deployer -n cerebrops --duration=876000h
```

### 3. Run Setup Script
```powershell
# Windows PowerShell
.\scripts\setup-cicd.ps1

# Or manually commit
git add .
git commit -m "ci: Configure CI/CD pipeline"
git push origin main
```

### 4. Monitor Deployment
```
https://github.com/AnshulBari/CerebrOps/actions
```

---

## 🔍 Common Commands

### Check Pipeline Status
```bash
# View in GitHub
https://github.com/AnshulBari/CerebrOps/actions

# Check deployment in cluster
kubectl get all -n cerebrops
kubectl get pods -n cerebrops -w
```

### View Application
```bash
# Port forward
kubectl port-forward service/cerebrops-service 8080:80 -n cerebrops

# Open browser
http://localhost:8080
```

### Check Logs
```bash
# Application logs
kubectl logs -f deployment/cerebrops-app -n cerebrops

# All pods
kubectl logs -f -l app=cerebrops -n cerebrops

# Previous container (if crashed)
kubectl logs --previous deployment/cerebrops-app -n cerebrops
```

### Troubleshooting
```bash
# Describe pod (shows events and issues)
kubectl describe pod <pod-name> -n cerebrops

# Get events
kubectl get events -n cerebrops --sort-by='.lastTimestamp'

# Check secrets
kubectl get secrets -n cerebrops
kubectl describe secret cerebrops-secrets -n cerebrops

# Restart deployment
kubectl rollout restart deployment/cerebrops-app -n cerebrops

# Rollback to previous version
kubectl rollout undo deployment/cerebrops-app -n cerebrops
```

---

## 🎯 What Got Fixed

### ✅ Changes Made

1. **GitHub Actions Workflow** (`.github/workflows/ci-cd.yml`)
   - ✅ Uncommented kubectl configuration commands
   - ✅ Uncommented kubectl deployment commands
   - ✅ Added smoke tests execution
   - ✅ Updated namespace to `cerebrops`

2. **Kubernetes Manifests**
   - ✅ Updated image to `ghcr.io/anshulbari/cerebrops:latest`
   - ✅ Fixed namespace references
   - ✅ Created PersistentVolumeClaim definitions

3. **Documentation & Scripts**
   - ✅ Created `GITHUB_SETUP.md` - Complete setup guide
   - ✅ Created `DEPLOYMENT_CHECKLIST.md` - 100+ item checklist
   - ✅ Created `scripts/smoke-tests.sh` - Automated tests
   - ✅ Created `scripts/setup-cicd.ps1` - Interactive setup
   - ✅ Created `.env` - Environment template

---

## 📋 Pre-Deployment Checklist

- [ ] GitHub secrets configured (K8S_SERVER, K8S_TOKEN)
- [ ] Workflow permissions set to "Read and write"
- [ ] Kubernetes cluster accessible
- [ ] Service account created
- [ ] `.env` file configured locally
- [ ] All tests passing (`pytest tests/ -v`)
- [ ] Docker image builds (`docker build -t cerebrops:test .`)

---

## 🔄 Deployment Flow

```
Push to main → GitHub Actions Triggered
    ↓
Run Tests (pytest, flake8)
    ↓
Build Docker Image
    ↓
Security Scan (Trivy)
    ↓
Push to ghcr.io
    ↓
Deploy to Kubernetes
    ↓
Run Smoke Tests
    ↓
Anomaly Detection Active
    ↓
✅ Production Ready!
```

---

## 🚨 If Something Goes Wrong

### Pipeline Fails at Deploy
```bash
# Check GitHub secrets are set correctly
# Verify K8S_TOKEN hasn't expired
kubectl create token cerebrops-deployer -n cerebrops --duration=876000h
# Update GitHub secret with new token
```

### Pods Won't Start
```bash
# Check pod events
kubectl describe pod <pod-name> -n cerebrops

# Common issues:
# - Image pull errors → Check image name and registry
# - Missing secrets → kubectl get secrets -n cerebrops
# - Resource limits → kubectl describe nodes
```

### No Slack Alerts
```bash
# Test webhook directly
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test"}' \
  YOUR_WEBHOOK_URL

# Check secret in k8s
kubectl get secret cerebrops-secrets -n cerebrops -o yaml
```

---

## 📚 Documentation

- **Setup Guide**: `GITHUB_SETUP.md`
- **Complete Checklist**: `DEPLOYMENT_CHECKLIST.md`
- **Operations Manual**: `DEPLOYMENT_GUIDE.md`
- **API Docs**: `API_DOCUMENTATION.md`
- **Quick Start**: `QUICKSTART.md`

---

## 🎓 Learning Resources

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Kubernetes Docs](https://kubernetes.io/docs/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)

---

## ⏱️ Time Estimates

- **GitHub Secrets Setup**: 5 minutes
- **First Deployment**: 10-15 minutes
- **Subsequent Deployments**: 3-5 minutes (automatic)
- **Rollback if needed**: 30 seconds

---

## 🎉 Success Indicators

✅ Pipeline shows all green checkmarks  
✅ `kubectl get pods -n cerebrops` shows Running  
✅ Health check responds: `curl http://localhost:8080/health`  
✅ Smoke tests pass  
✅ Slack alerts received (if configured)  

---

**You're all set! Your CI/CD pipeline is production-ready! 🚀**

For help: Check the documentation files or GitHub Issues
