# Deployment Guide

## Overview

This document describes the CI/CD deployment setup for the Trade System project.

## Architecture

- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **Backend**: Python microservices (Kafka + Redis architecture)
- **Container Registry**: GitHub Container Registry (ghcr.io)
- **Frontend Hosting**: Vercel

## Deployment Flow

### Frontend (Vercel)
- Triggered on: Push to `frontend/**` or changes to `main` branch
- Steps: Install → Typecheck → Build → Deploy to Vercel

### Backend (GitHub Container Registry)
- Triggered on: Push to `backend/**` or changes to `main` branch
- Steps: Build → Push to ghcr.io
- Images: data-service, event-service, fusion-service, strategy-service, llm-service

## GitHub Secrets Configuration

For the CI/CD to work, you need to configure the following GitHub Secrets:

### Frontend (Vercel) - Optional
If you want to deploy the frontend to Vercel:

1. **VERCEL_TOKEN**
   - Get from: https://vercel.com/account/tokens
   - Create a new token with full access

2. **VERCEL_ORG_ID**
   - Get from: Vercel project settings

3. **VERCEL_PROJECT_ID**
   - Get from: Vercel project settings

### Backend (Already Configured)
The backend workflow uses GitHub's built-in `GITHUB_TOKEN` for authentication to GitHub Container Registry.
No additional secrets are needed for the backend!

## How to Add Secrets

1. Go to your GitHub repository: https://github.com/ydz-auto/trade_sys
2. Navigate to **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret**
4. Add the secrets if needed

## Image URLs

After the backend CI/CD runs, your images will be available at:
- `ghcr.io/ydz-auto/trade_sys-data-service:latest`
- `ghcr.io/ydz-auto/trade_sys-event-service:latest`
- `ghcr.io/ydz-auto/trade_sys-fusion-service:latest`
- `ghcr.io/ydz-auto/trade_sys-strategy-service:latest`
- `ghcr.io/ydz-auto/trade_sys-llm-service:latest`

## Deployment Commands

### Deploy Backend
```bash
cd backend/deploy
docker-compose -f docker-compose.prod.yml up -d
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

## First Deployment Steps

1. **Push a commit to trigger CI/CD**:
   ```bash
   git add .
   git commit -m "chore: trigger CI/CD"
   git push origin main
   ```

2. **Monitor GitHub Actions**:
   - Go to the Actions tab in your GitHub repository
   - Watch the workflow runs

3. **Pull and deploy images**:
   After the backend workflow completes:
   ```bash
   docker login ghcr.io -u github_username -p github_token
   cd backend/deploy
   docker-compose -f docker-compose.prod.yml pull
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Private Repository Note

All Docker images are stored in your private GitHub Container Registry.
They are only accessible to your GitHub account and cannot be viewed by others.
