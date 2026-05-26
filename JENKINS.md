# Jenkins CI/CD Pipeline Setup Guide

This guide describes how to configure and run the Jenkins declarative pipeline for the **AI Video Assistant** application.

---

## Prerequisites

Before setting up the pipeline in Jenkins, ensure that your Jenkins agent/server meets the following requirements:

1. **Required Plugins**:
   - **Pipeline**
   - **Git Plugin**
   - **Credentials Binding Plugin** (for Docker registry login)
   - **Docker Pipeline** (optional, but highly recommended for Docker integration)

2. **System Dependencies**:
   - **Docker** and **Docker Compose** must be installed on the Jenkins agent machine.
   - The Jenkins user (`jenkins`) must have permissions to run Docker commands (e.g., added to the `docker` group on Linux).
   - **Python 3.10+** (optional, used for local static code analysis linting. If not found, the pipeline continues gracefully).

---

## Step-by-Step Setup

### Step 1: Configure Credentials in Jenkins

If you plan to push your Docker image to a registry (like Docker Hub), configure your credentials:

1. Go to **Jenkins Dashboard** -> **Manage Jenkins** -> **Credentials**.
2. Select your store/domain (e.g., *Global*).
3. Click **Add Credentials**.
4. Set **Kind** to `Username with password`.
5. Set **ID** to `docker-hub-credentials` (or match the `DOCKER_CRED_ID` variable in the `Jenkinsfile`).
6. Input your Docker Hub username and password/access token.
7. Click **Create**.

### Step 2: Create a New Pipeline Job

1. On the Jenkins home page, click **New Item**.
2. Enter a name (e.g., `AI-Video-Assistant-Pipeline`).
3. Select **Pipeline** and click **OK**.

### Step 3: Configure Pipeline from Git (SCM)

1. Under the **General** tab, check the box for **This project is parameterized** (the parameters will automatically populate on the first build, but you can also pre-configure them).
2. Go to the **Pipeline** section at the bottom.
3. For **Definition**, select **Pipeline script from SCM**.
4. For **SCM**, select **Git**.
5. Enter your Repository URL (and choose credentials if it's a private repository).
6. Under **Branches to build**, specify your branch (e.g., `*/main`).
7. For **Script Path**, type `Jenkinsfile`.
8. Click **Save**.

---

## Running the Pipeline

### First Run
Since this is a parameterized pipeline, you should run it once manually to register the parameters.
1. Click **Build Now** on the left menu.
2. This initial build might checkout the code and register the parameters, then build with defaults.

### Subsequent Runs
1. Click **Build with Parameters**.
2. Customize the following options:
   - **DEPLOY_ENV**: Select target environment (`dev`, `staging`, or `production`).
   - **RUN_LINTER**: Check to run `flake8` and `bandit` on the codebase.
   - **PUSH_IMAGE**: Check to push the built docker image to your registry.
3. Click **Build**.

---

## Customization

### Docker Registry & Image Name
Open the `Jenkinsfile` in the root of the project and customize the environment block at the top:

```groovy
environment {
    DOCKER_REGISTRY = 'docker.io'                   // Your Docker Registry host
    DOCKER_IMAGE    = 'your-username/video-assistant' // Repository/Image name
    DOCKER_CRED_ID  = 'docker-hub-credentials'       // Jenkins Credentials ID
}
```

### Production Deployment
In the `Deploy` stage of the `Jenkinsfile`, you can replace the placeholder script with your production deployment logic:
- Remote deployment via SSH: `ssh user@prod-host 'docker compose pull && docker compose up -d'`
- Kubernetes deployment: `sh 'kubectl apply -f k8s/deployment.yaml'`
