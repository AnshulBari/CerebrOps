# GitHub Setup Script for CerebrOps
# Run this after creating your GitHub repository

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubUsername,
    
    [Parameter(Mandatory=$false)]
    [string]$RepositoryName = "CerebrOps"
)

Write-Host "🚀 Setting up GitHub repository for CerebrOps..." -ForegroundColor Cyan

# Construct repository URL
$repoUrl = "https://github.com/$GitHubUsername/$RepositoryName.git"

Write-Host "Repository URL: $repoUrl" -ForegroundColor Yellow

# Add remote origin
Write-Host "Adding remote origin..." -ForegroundColor Green
git remote add origin $repoUrl

# Push to GitHub
Write-Host "Pushing to GitHub..." -ForegroundColor Green
git push -u origin main

Write-Host "✅ Successfully pushed CerebrOps to GitHub!" -ForegroundColor Green
Write-Host "🌐 Your repository: https://github.com/$GitHubUsername/$RepositoryName" -ForegroundColor Cyan

Write-Host "`n📋 Next steps:" -ForegroundColor Yellow
Write-Host "1. Go to your repository on GitHub" -ForegroundColor White
Write-Host "2. Update the clone URL in README.md if needed" -ForegroundColor White
Write-Host "3. Set up GitHub Secrets for CI/CD:" -ForegroundColor White
Write-Host "   - SLACK_WEBHOOK_URL" -ForegroundColor Gray
Write-Host "   - DOCKER_USERNAME (optional)" -ForegroundColor Gray
Write-Host "   - DOCKER_TOKEN (optional)" -ForegroundColor Gray
Write-Host "4. Enable GitHub Actions in repository settings" -ForegroundColor White