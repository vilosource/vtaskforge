# vtaskforge K8s Deployment Plan

Status: Ready to implement (2026-03-22)

## Context

vtaskforge needs to deploy to Kubernetes as part of the vafi project.
Currently vtf runs via Docker Compose (`docker-compose.dogfood.yml`)
on the dev machine at localhost:8001. The vafi project has a k3s cluster
running on a dedicated server (`vafi-1.dev.viloforge.com` at 192.168.2.90)
where vtf needs to run in-cluster so agent pods can reach it via k8s DNS.

This is a vtf repo concern — vtf owns its own deployment, just as it
owns `docker-compose.yml` and `docker-compose.dogfood.yml`. vafi expects
vtf to be running at `vtf-api.vafi-system.svc.cluster.local`.

## Infrastructure available

- **k3s cluster:** `vafi-1.dev.viloforge.com` (192.168.2.90)
- **Kubeconfig:** `~/.kube/vafi-dev.yaml`
- **Container registry:** `192.168.2.90:30500` (insecure, internal to LAN)
- **Target namespace:** `vafi-system` (already created)
- **k3s storage:** local-path-provisioner at `/var/lib/rancher/k3s/storage/`

## What to build

### 1. K8s manifests (`k8s/base/`)

Translate `docker-compose.dogfood.yml` services into k8s manifests:

| Docker Compose service | K8s resource | Notes |
|----------------------|--------------|-------|
| `dogfood-db` (postgres:16-alpine) | StatefulSet + Service + PVC | Persistent storage for DB |
| `dogfood-redis` (redis:7-alpine) | Deployment + Service | Ephemeral is fine |
| `dogfood-api` (Dockerfile.prod, gunicorn) | Deployment + Service | 2 workers, gevent, port 8000 |
| `dogfood-celery` (same image, celery worker) | Deployment | Same image, different command |
| `dogfood-celery-beat` (same image, celery beat) | Deployment | Same image, different command |

Additional manifests:
- `vtf-migrate.yaml` — Job: `python manage.py migrate && python manage.py createsuperuser`
- `secrets.yaml` — DB credentials, Django secret key, admin password
- `kustomization.yaml` — lists all resources

**Key env vars from docker-compose.dogfood.yml:**
```
DJANGO_SETTINGS_MODULE=vtaskforge.settings.prod
DATABASE_URL=postgres://vtf:vtfdogfood@dogfood-db:5432/vtf_dogfood
REDIS_URL=redis://dogfood-redis:6379/0
ALLOWED_HOSTS=*
```

These become k8s environment variables referencing the service DNS names.

### 2. Kustomize overlays (`k8s/overlays/vafi-dev/`)

Environment-specific patches:
- Image registry prefix: `192.168.2.90:30500/`
- Namespace: `vafi-system`
- Resource limits (small for dev)
- Replica counts (1 for dev)

### 3. Ansible deploy playbook (`ansible/`)

```
vtaskforge/
  ansible/
    inventory/
      vafi-dev.yml          # registry, kubeconfig, namespace
    playbooks/
      deploy.yml            # build, push, apply, migrate
```

The playbook:
1. Build vtf image from `Dockerfile.prod`
2. Tag and push to target registry
3. `kubectl apply -k k8s/overlays/<env>`
4. Wait for pods to be ready
5. Run migration job
6. Verify API responds

Usage:
```bash
cd ~/GitHub/vtaskforge
ansible-playbook ansible/playbooks/deploy.yml -i ansible/inventory/vafi-dev.yml
```

### 4. Directory structure (new files in vtf repo)

```
vtaskforge/
  k8s/
    base/
      kustomization.yaml
      postgres.yaml         # StatefulSet + Service + PVC
      redis.yaml            # Deployment + Service
      vtf-api.yaml          # Deployment + Service
      vtf-celery.yaml       # Deployment
      vtf-celery-beat.yaml  # Deployment
      vtf-migrate.yaml      # Job
      secrets.yaml          # Template/placeholder
    overlays/
      vafi-dev/
        kustomization.yaml  # Image prefix, namespace, patches
  ansible/
    inventory/
      vafi-dev.yml
    playbooks/
      deploy.yml
```

## Reference: docker-compose.dogfood.yml services

```yaml
dogfood-api:
  build:
    context: .
    dockerfile: Dockerfile.prod
  command: gunicorn vtaskforge.wsgi:application
    --bind 0.0.0.0:8000
    --workers 2
    --worker-class gevent
    --worker-connections 100
    --timeout 120
  ports: 8001:8000
  env: DJANGO_SETTINGS_MODULE=vtaskforge.settings.prod
  depends_on: dogfood-db, dogfood-redis

dogfood-db:
  image: postgres:16-alpine
  env: POSTGRES_USER=vtf, POSTGRES_PASSWORD=vtfdogfood, POSTGRES_DB=vtf_dogfood
  volumes: dogfood-db-data:/var/lib/postgresql/data

dogfood-redis:
  image: redis:7-alpine

dogfood-celery:
  (same image as api)
  command: celery -A vtaskforge worker -l info
  env: same as api

dogfood-celery-beat:
  (same image as api)
  command: celery -A vtaskforge beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
  env: same as api
```

## Reference: Dockerfile.prod

Multi-stage build:
1. Stage 1: `node:20-alpine` — `npm ci && npm run build` React SPA
2. Stage 2: `python:3.12-slim` — pip install, copy source, copy SPA to static, collectstatic
3. CMD: gunicorn

## Verification

After deploy:
1. `kubectl -n vafi-system get pods` — all running
2. `kubectl -n vafi-system port-forward svc/vtf-api 8001:8000` — access web UI
3. Login with admin/admin
4. From a pod in vafi-agents namespace: `curl vtf-api.vafi-system.svc.cluster.local:8000/v1/` — API responds
