# Deploying the gremlin service (judge link)

The gremlin service is `gremlin_app.py`, packaged by `Dockerfile.gremlins`. It is separate
from Campus Cubbies (`Dockerfile`, deployed by Adam). Judge mode needs no Google login.

```sh
PROJECT=gremlins-511221 REGION=us-west1 SERVICE=gremlins
gcloud config set project $PROJECT
gcloud artifacts repositories create gremlins --repository-format=docker --location=$REGION 2>/dev/null || true
IMAGE=$REGION-docker.pkg.dev/$PROJECT/gremlins/$SERVICE
gcloud builds submit --config cloudbuild.gremlins.yaml --ignore-file Dockerfile.gremlins.dockerignore --substitutions _IMAGE=$IMAGE
gcloud run deploy $SERVICE --image $IMAGE --region $REGION \
  --allow-unauthenticated --max-instances 1 \
  --set-env-vars PUBLIC_URL=https://$SERVICE-331254975906.$REGION.run.app,DEMO_TOKEN=<pick a long random string>,CUBBY_URL=https://cubby.bayleaf.dev \
  --set-secrets GROQ_API_KEY=groq-key:latest,NVIDIA_NIM_API_KEY=nim-key:latest,GEMINI_API_KEY=gemini-key:latest,SESSION_SECRET=session-secret:latest
```

Create the secrets once (`gcloud secrets create groq-key --data-file=-` and paste the key;
never put a key in a file that is committed). There is no Google login to configure here:
students sign in through Campus Cubbies' pairing page, and `PUBLIC_URL` must be the real
service URL so the site's same-origin checks pass.

Judge link: `https://<service url>/demo?token=<DEMO_TOKEN>`. Boxes live on the container's
filesystem (writes do not survive a new instance; `--max-instances 1` keeps one). The
simplest local alternative for the demo: `DEMO_TOKEN=judge LOCAL_HTTP=1 uv run uvicorn
gremlin_app:app --port 8080 --no-access-log` and share the screen.
