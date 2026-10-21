# Deploy target recipes

Starting points for `set_deploy_config`. Replace `APP`, `REGION`, `PORT` and the like with the project's values,
and check the commands against the installed CLI version (`<cli> --help`). Every web target needs a health endpoint
such as `GET /health` that returns 200, so the smoke check has something to call.

| Target | Prerequisites the user must do |
|---|---|
| local | none |
| docker | Docker installed; a registry login if you push |
| vercel | `npm i -g vercel`, `vercel login`, `vercel link` |
| netlify | `npm i -g netlify-cli`, `netlify login`, `netlify link` |
| fly | `flyctl` installed, `fly auth login`, `fly launch --no-deploy` once |
| azure-app-service / azure-container-apps | `az login`, a resource group |
| cloud-run | `gcloud auth login`, `gcloud config set project ...` |
| aws-s3-static | `aws configure`, an S3 bucket and a CloudFront distribution |
| kubernetes | `kubectl` context set, an image registry |

## local (a process on this machine; good for demos and CI)
- build_command: the stack's build (such as `npm run build`), or `true` if there is nothing to build
- deploy_command: `node scripts/deploy-local.mjs` (write it: stop the old process using `.deploy/app.pid`, start the
  app in the background with `PORT` set, write the new PID, and log to `.deploy/app.log`)
- url: `http://localhost:PORT`
- smoke_check: `curl -fsS http://localhost:PORT/health`
- rollback_command: `git stash && node scripts/deploy-local.mjs` (or redeploy the previous commit)

## docker (any host that runs containers)
- Files: a multi-stage `Dockerfile` (build stage, then a slim runtime stage with a non-root user), `.dockerignore`
- build_command: `docker build -t APP:$(git rev-parse --short HEAD) -t APP:latest .`
- deploy_command: `docker rm -f APP 2>/dev/null; docker run -d --name APP -p PORT:PORT --restart unless-stopped APP:latest`
- smoke_check: `curl -fsS http://localhost:PORT/health`
- rollback_command: `docker rm -f APP; docker run -d --name APP -p PORT:PORT APP:<previous-sha>`

## vercel (Next.js, static sites, serverless functions)
- build_command: `vercel build --prod`
- deploy_command: `vercel deploy --prebuilt --prod`
- smoke_check: `curl -fsS https://<domain>/` (or `/api/health`)
- rollback_command: `vercel rollback`

## netlify (static sites, Netlify functions)
- build_command: `npm run build`
- deploy_command: `netlify deploy --prod --dir=<build-dir>`
- rollback_command: restore a previous deploy in the Netlify UI, or redeploy the previous commit

## fly (containers close to users)
- Files: `fly.toml` (created by `fly launch --no-deploy`), a `Dockerfile`
- build_command: `true` (Fly builds remotely)
- deploy_command: `fly deploy --remote-only`
- smoke_check: `curl -fsS https://APP.fly.dev/health`
- rollback_command: `fly releases --image` to find the previous image, then `fly deploy --image <image>`

## azure-app-service
- deploy_command: `az webapp up --name APP --resource-group RG --runtime "NODE:22-lts"` (match the stack)
- smoke_check: `curl -fsS https://APP.azurewebsites.net/health`
- rollback_command: use deployment slots (`az webapp deployment slot swap`), or redeploy the previous commit

## azure-container-apps
- deploy_command: `az containerapp up --name APP --resource-group RG --source . --ingress external --target-port PORT`
- rollback_command: `az containerapp revision list`, then move traffic back to the previous revision with `az containerapp ingress traffic set`

## cloud-run (Google Cloud)
- deploy_command: `gcloud run deploy APP --source . --region REGION --allow-unauthenticated`
- smoke_check: `curl -fsS $(gcloud run services describe APP --region REGION --format='value(status.url)')/health`
- rollback_command: `gcloud run services update-traffic APP --region REGION --to-revisions=<previous-revision>=100`

## aws-s3-static (static sites and SPAs)
- build_command: `npm run build`
- deploy_command: `aws s3 sync <build-dir> s3://BUCKET --delete && aws cloudfront create-invalidation --distribution-id DIST --paths "/*"`
- rollback_command: redeploy the previous commit's build (or turn on bucket versioning)

## kubernetes
- Files: `k8s/deployment.yaml` (readiness and liveness probes on `/health`), `k8s/service.yaml`, optionally an ingress
- build_command: `docker build -t REGISTRY/APP:$(git rev-parse --short HEAD) . && docker push REGISTRY/APP:$(git rev-parse --short HEAD)`
- deploy_command: `kubectl set image deployment/APP APP=REGISTRY/APP:$(git rev-parse --short HEAD) && kubectl rollout status deployment/APP --timeout=120s`
- rollback_command: `kubectl rollout undo deployment/APP`

## CI (optional, any target)
When the user wants deploys from CI, add a workflow (such as `.github/workflows/deploy.yml`) that runs the test
command and then the readiness gate (it exits non-zero when the project isn't ready):
`git clone --depth 1 https://github.com/mishrabp/ai-agent-kits /tmp/ai-agent-kits && python3 /tmp/ai-agent-kits/claude/app-lifecycle-kit/src/lifecycle.py status --require-ready`,
followed by the same build and deploy commands. Secrets go in the CI secret store, never in the repo.
