# GitHub Secrets Configuration

This document lists all the GitHub Secrets you need to configure for CI/CD deployment.

## Vercel (Frontend)

1. **VERCEL_TOKEN**
   - Get from: https://vercel.com/account/tokens
   - Create a new token with full access

2. **VERCEL_ORG_ID**
   - Get from: `vercel inspect <project-url>` or Vercel dashboard
   - Found in your Vercel project settings

3. **VERCEL_PROJECT_ID**
   - Get from: Vercel project settings
   - Project ID is in the general settings

## Docker Hub (Backend)

1. **DOCKER_USERNAME**
   - Your Docker Hub username
   - Get from: https://hub.docker.com/settings/general

2. **DOCKER_TOKEN**
   - Create an Access Token in Docker Hub
   - Go to: https://hub.docker.com/settings/security
   - Create a new access token with read/write permissions

## How to Add Secrets

1. Go to your GitHub repository: https://github.com/ydz-auto/trade_sys
2. Navigate to **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret**
4. Add each secret with its corresponding value

## Deployment Flow

### Frontend (Vercel)
- Triggered on: Push to `frontend/**` or `main` branch changes
- Steps: Install → Typecheck → Build → Deploy to Vercel

### Backend (Docker Hub)
- Triggered on: Push to `backend/**` or `main` branch changes
- Steps: Build → Push to Docker Hub
- Images: data-service, event-service, fusion-service, strategy-service, llm-service

## Deployment Commands

### Deploy Backend
```bash
cd backend/deploy
DOCKER_USERNAME=your_username docker-compose -f docker-compose.prod.yml up -d
```

### Check Status
```bash
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f
```

### Stop Services
```bash
docker-compose -f docker-compose.prod.yml down
```
