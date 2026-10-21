---
name: deploy
description: Deploys the app to its configured target (Docker, Vercel, Netlify, Fly.io, Azure, AWS, Google Cloud Run, Kubernetes or local) after checking that it is verified, then smoke-tests it and records the deployment. Use when the user asks to deploy, release or ship, or to set up deployment.
argument-hint: "[environment, default: production]"
allowed-tools: mcp__plugin_app-lifecycle_lifecycle Bash(git rev-parse:*) Bash(git status:*)
---

# Deploy

Environment: $ARGUMENTS

## 1. Readiness gate
Call `status`. If `deploy_ready` is false, show the `deploy_blockers` and stop. Offer the fix for each one
(`/app-lifecycle:test`, `/app-lifecycle:build` and so on). Deploy anyway only if the user explicitly insists, and
then put the reason in the deployment `notes`.

## 2. Deployment setup (first time only)
If the environment has no `deploy_command` yet:
- Read [targets.md](targets.md) for the recorded `deploy.target` and adapt it to this stack.
- Create the files the target needs (such as Dockerfile, `.dockerignore`, `vercel.json`, `fly.toml`, k8s manifests,
  a CI workflow) and add a health endpoint if the app doesn't have one.
- Call `set_deploy_config` with the environment's `build_command`, `deploy_command`, `url`, `smoke_check` and
  `rollback_command`. Write and record any design changes as in the build skill (the `deployment` section).
- Tell the user about prerequisites you can't do for them, such as the CLI login, the cloud project and the secrets.

## 3. Confirm, then deploy
Deploying is visible to users and may cost money. Show the environment, version, commit and the exact commands,
and **wait for an explicit yes**. Then:
1. Get the version and commit: `git rev-parse --short HEAD`, and the version from the package manifest.
   Warn if `git status` shows uncommitted changes.
2. Run `build_command`, then `deploy_command`. Stop at the first failure.
3. Run `smoke_check` against the deployed URL, retrying for up to about a minute while it starts.

## 4. Record the outcome
- **Success:** call `record_deployment` with `status: "success"`, the version, the commit and the URL.
- **Failure:** call `record_deployment` with `status: "failed"` and the error in `notes`. Offer to run
  `rollback_command`. If the user agrees and it works, record another deployment with `status: "rolled_back"`.

Report the URL, the version and the requirements that are now live (from `status`).
