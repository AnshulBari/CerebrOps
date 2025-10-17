# 🔧 GitHub CI/CD Pipeline Setup Guide

This guide walks you through setting up the complete CI/CD pipeline for CerebrOps using GitHub Actions.

## Prerequisites

- [ ] GitHub account with repository access
- [ ] Kubernetes cluster (EKS, GKE, AKS, or self-hosted)
- [ ] Slack workspace with webhook URL (optional but recommended)
- [ ] kubectl installed and configured locally

## Step 1: Fork/Clone the Repository

```bash
# Clone the repository
git clone https://github.com/your-username/CerebrOps.git
cd CerebrOps

# Create your own branch
git checkout -b setup-cicd
```

## Step 2: Create Kubernetes Service Account

The CI/CD pipeline needs credentials to deploy to your Kubernetes cluster.

```bash
# Create namespace
kubectl create namespace cerebrops

# Create service account
kubectl create serviceaccount cerebrops-deployer -n cerebrops

# Create cluster role binding (for full access)
kubectl create clusterrolebinding cerebrops-deployer-binding \
  --clusterrole=cluster-admin \
  --serviceaccount=cerebrops:cerebrops-deployer

# Get the service account token (for authentication)
# For Kubernetes 1.24+:
kubectl create token cerebrops-deployer -n cerebrops --duration=876000h

# Save this token - you'll need it for GitHub Secrets
```

### Get Kubernetes Server URL

```bash
# Get your cluster's API server URL
kubectl cluster-info | grep "Kubernetes control plane"

# Alternative method:
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'

# Save this URL - you'll need it for GitHub Secrets
```

## Step 3: Set Up Slack Webhook (Optional)

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name it "CerebrOps" and select your workspace
4. Go to "Incoming Webhooks" and activate it
5. Click "Add New Webhook to Workspace"
6. Choose the channel for alerts (e.g., #alerts or #monitoring)
7. Copy the webhook URL (format: `https://hooks.slack.com/services/...`)

## Step 4: Configure GitHub Secrets

Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**

Click **"New repository secret"** and add each of the following:

### Required Secrets

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `K8S_SERVER` | Kubernetes API server URL | `https://kubernetes.default.svc` |
| `K8S_TOKEN` | Service account token from Step 2 | `eyJhbGciOiJSUzI1NiIs...` |

### Optional Secrets

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | `https://hooks.slack.com/services/XXX/YYY/ZZZ` |
| `APP_URL` | Production application URL | `https://cerebrops.yourdomain.com` |

### Screenshot Guide

```
1. Navigate to: Repository → Settings → Secrets and variables → Actions
2. Click: "New repository secret"
3. Enter: Name (e.g., "K8S_SERVER")
4. Paste: Value (your Kubernetes API server URL)
5. Click: "Add secret"
6. Repeat for each secret above
```

## Step 5: Update Pipeline Configuration

### Option A: Using GitHub Secrets (Recommended)

The pipeline is already configured to use GitHub Secrets. Simply uncomment the kubectl configuration lines:

Edit `.github/workflows/ci-cd.yml` and uncomment lines 130-133:

```yaml
- name: Configure kubectl
  run: |
    echo "Configuring kubectl for deployment..."
    kubectl config set-cluster cerebrops --server=${{ secrets.K8S_SERVER }}
    kubectl config set-credentials cerebrops --token=${{ secrets.K8S_TOKEN }}
    kubectl config set-context cerebrops --cluster=cerebrops --user=cerebrops
    kubectl config use-context cerebrops
```

Also uncomment lines 141-145:

```yaml
- name: Deploy to Kubernetes
  run: |
    echo "Deploying to Kubernetes cluster..."
    kubectl apply -f k8s/
    kubectl rollout status deployment/cerebrops-app -n cerebrops
```

### Option B: Using Self-Hosted Runner (For Private Clusters)

If your Kubernetes cluster is not publicly accessible, use a self-hosted GitHub Actions runner:

```bash
# On a machine with kubectl access to your cluster:
# 1. Go to: Repository → Settings → Actions → Runners → New self-hosted runner
# 2. Follow the instructions to install and configure the runner
# 3. Start the runner service
```

Update `.github/workflows/ci-cd.yml`:

```yaml
deploy:
  needs: [test, build]
  runs-on: self-hosted  # Change from 'ubuntu-latest'
  name: Deploy to Kubernetes
  if: github.ref == 'refs/heads/main'
```

## Step 6: Update Kubernetes Manifests

### Set the Container Image

The pipeline will automatically update the image tag, but verify the registry:

Edit `k8s/deployment.yaml`:

```yaml
containers:
- name: cerebrops-web
  image: ghcr.io/YOUR_GITHUB_USERNAME/cerebrops:latest
  # Pipeline will replace :latest with :main-{sha}
```

### Set Your Namespace (Optional)

If you want to use a different namespace than `cerebrops`:

Edit `k8s/deployment.yaml`, `k8s/secrets.yaml`, `k8s/cronjobs.yaml`:

```yaml
metadata:
  namespace: your-namespace  # Change from 'cerebrops'
```

Also update the deploy job in `.github/workflows/ci-cd.yml`:

```yaml
- name: Deploy to Kubernetes
  run: |
    kubectl apply -f k8s/ -n your-namespace
    kubectl rollout status deployment/cerebrops-app -n your-namespace
```

## Step 7: Create Base64 Encoded Secrets

For Kubernetes secrets, you need base64 encoded values:

```bash
# Encode your Slack webhook URL
echo -n "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" | base64

# Example output: aHR0cHM6Ly9ob29rcy5zbGFjay5jb20vc2VydmljZXMvWU9VUi9XRUJIT09LL1VSTA==
```

Update `k8s/secrets.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cerebrops-secrets
type: Opaque
data:
  slack-webhook-url: "aHR0cHM6Ly9ob29rcy5zbGFjay5jb20vc2VydmljZXMvWU9VUi9XRUJIT09LL1VSTA=="
  # ^^^ Replace with your base64 encoded webhook URL
```

## Step 8: Test the Pipeline

### Manual Test Before Commit

Test locally to ensure everything works:

```bash
# 1. Run tests
pytest tests/ -v

# 2. Build Docker image
docker build -t cerebrops:test .

# 3. Run the container
docker run -d -p 5000:5000 cerebrops:test

# 4. Run smoke tests
chmod +x scripts/smoke-tests.sh
./scripts/smoke-tests.sh

# 5. Cleanup
docker stop $(docker ps -q --filter ancestor=cerebrops:test)
```

### Trigger the Pipeline

```bash
# Commit your changes
git add .github/workflows/ci-cd.yml k8s/
git commit -m "ci: Configure CI/CD pipeline for deployment"
git push origin setup-cicd

# Create a pull request
# The pipeline will run automatically on PR creation

# After review, merge to main
# The pipeline will deploy to production
```

## Step 9: Monitor the Pipeline

### View Pipeline Execution

1. Go to: Repository → **Actions** tab
2. Click on your workflow run
3. Monitor each job:
   - ✅ Test
   - ✅ Build
   - ✅ Security Scan
   - ✅ Performance Test
   - ✅ Deploy
   - ✅ Anomaly Detection

### Check Deployment Status

```bash
# Check pods
kubectl get pods -n cerebrops

# Check deployment
kubectl get deployment cerebrops-app -n cerebrops

# View logs
kubectl logs -f deployment/cerebrops-app -n cerebrops

# Check service
kubectl get svc cerebrops-service -n cerebrops
```

### Access the Application

```bash
# Port forward to local machine
kubectl port-forward service/cerebrops-service 8080:80 -n cerebrops

# Access at: http://localhost:8080
```

Or set up ingress:

```bash
# Apply ingress (if you have an ingress controller)
kubectl apply -f k8s/deployment.yaml -n cerebrops

# Add to /etc/hosts (Linux/macOS) or C:\Windows\System32\drivers\etc\hosts
echo "127.0.0.1 cerebrops.local" | sudo tee -a /etc/hosts

# Access at: http://cerebrops.local
```

## Step 10: Verify Alerts

Test that Slack alerts are working:

```bash
# Method 1: Via the application
curl http://localhost:8080/simulate-error

# Method 2: Manually trigger
kubectl exec -it deployment/cerebrops-app -n cerebrops -- python -c "
from alerts import SlackAlerter
import os
alerter = SlackAlerter(os.getenv('SLACK_WEBHOOK_URL'))
alerter.send_slack_alert('🎉 CI/CD Pipeline setup complete!', 'low')
"
```

## Troubleshooting

### Pipeline Fails at Deploy Step

**Issue**: `Error: Unauthorized`

**Solution**: 
```bash
# Verify your K8S_TOKEN secret is correct
# Regenerate token:
kubectl create token cerebrops-deployer -n cerebrops --duration=876000h
# Update the K8S_TOKEN secret in GitHub
```

### Pipeline Fails at Build Step

**Issue**: `Error: denied: permission_denied`

**Solution**:
```bash
# The GITHUB_TOKEN needs packages:write permission
# Go to: Repository → Settings → Actions → General
# Under "Workflow permissions", select:
# ☑️ Read and write permissions
# Click "Save"
```

### Pods are in CrashLoopBackOff

**Issue**: Application fails to start in Kubernetes

**Solution**:
```bash
# Check pod logs
kubectl logs -f deployment/cerebrops-app -n cerebrops

# Common issues:
# 1. Missing secrets - verify secrets are created:
kubectl get secrets -n cerebrops

# 2. Image pull errors - verify image exists:
docker pull ghcr.io/YOUR_USERNAME/cerebrops:latest

# 3. Resource limits - check node resources:
kubectl describe nodes
```

### Slack Alerts Not Working

**Issue**: No alerts received in Slack

**Solution**:
```bash
# Test webhook URL directly:
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test message from CerebrOps"}' \
  YOUR_WEBHOOK_URL

# If that works, check the secret in Kubernetes:
kubectl get secret cerebrops-secrets -n cerebrops -o yaml
# Decode the value:
echo "BASE64_VALUE_HERE" | base64 -d
```

## Security Best Practices

1. **Rotate Tokens Regularly**
   ```bash
   # Every 90 days, regenerate the K8S_TOKEN
   kubectl create token cerebrops-deployer -n cerebrops --duration=876000h
   # Update GitHub secret
   ```

2. **Use Least Privilege**
   ```bash
   # Instead of cluster-admin, create a custom role:
   kubectl apply -f - <<EOF
   apiVersion: rbac.authorization.k8s.io/v1
   kind: Role
   metadata:
     name: cerebrops-deployer-role
     namespace: cerebrops
   rules:
   - apiGroups: ["", "apps", "batch", "networking.k8s.io"]
     resources: ["*"]
     verbs: ["*"]
   EOF
   
   kubectl create rolebinding cerebrops-deployer-binding \
     --role=cerebrops-deployer-role \
     --serviceaccount=cerebrops:cerebrops-deployer \
     -n cerebrops
   ```

3. **Enable Branch Protection**
   - Go to: Repository → Settings → Branches
   - Add rule for `main` branch:
     - ☑️ Require pull request reviews
     - ☑️ Require status checks to pass (select CI/CD checks)
     - ☑️ Require branches to be up to date

4. **Scan for Vulnerabilities**
   - The pipeline already includes Trivy scanning
   - Review security scan results in Actions → Security tab

## Next Steps

After successful setup:

1. ✅ Test the full pipeline with a small change
2. ✅ Set up monitoring dashboards (Grafana/Prometheus)
3. ✅ Configure log aggregation (ELK stack)
4. ✅ Set up backup and disaster recovery
5. ✅ Document your specific deployment process

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [Slack Webhook Documentation](https://api.slack.com/messaging/webhooks)

---

**🎉 Congratulations!** Your CI/CD pipeline is now fully configured and ready for production deployments!

If you encounter any issues not covered here, check the main README.md or open an issue in the repository.
