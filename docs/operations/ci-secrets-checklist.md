# Archon 72 - CI Secrets Checklist

## Required Secrets

The CI pipeline requires the following secrets to be configured in GitHub repository settings.

### Core Secrets (Required)

| Secret | Purpose | Where to Get |
|--------|---------|--------------|
| None required | Basic pipeline runs without secrets | N/A |

The basic test pipeline runs without any secrets. PostgreSQL and Redis are provided as service containers.

### Optional Secrets (Enhanced Features)

| Secret | Purpose | Where to Get |
|--------|---------|--------------|
| `CODECOV_TOKEN` | Upload coverage to Codecov | [codecov.io](https://codecov.io) |
| `SLACK_WEBHOOK` | Failure notifications | Slack Incoming Webhooks |

## Configuration Steps

### 1. Access Repository Settings

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

### 2. Add Codecov Token (Optional)

If you want coverage reports on Codecov:

1. Sign up at [codecov.io](https://codecov.io) with GitHub
2. Add your repository
3. Copy the upload token
4. Add secret: `CODECOV_TOKEN` = `your-token`

### 3. Add Slack Notifications (Optional)

To receive Slack notifications on failures:

1. Go to your Slack workspace
2. Create an Incoming Webhook
3. Copy the webhook URL
4. Add secret: `SLACK_WEBHOOK` = `https://hooks.slack.com/...`

Then uncomment the notification step in `.github/workflows/test.yml`:

```yaml
- name: Notify on failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    text: 'Test failures detected'
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Security Best Practices

### DO

- ✅ Use repository secrets (not organization secrets) for project-specific tokens
- ✅ Rotate tokens periodically
- ✅ Use minimal permissions for service accounts
- ✅ Review secret access in audit logs

### DON'T

- ❌ Commit secrets to the repository
- ❌ Print secrets in logs (GitHub auto-masks, but be careful)
- ❌ Share secrets across unrelated projects
- ❌ Use personal tokens for CI (use service accounts)

## Verifying Secrets

After adding secrets, verify they work:

1. Trigger a workflow run manually
2. Check the workflow logs for authentication errors
3. For Codecov, check if coverage appears on codecov.io
4. For Slack, check if notifications arrive

## Production Secrets (Future)

When adding production deployments, you may need:

| Secret | Purpose |
|--------|---------|
| `SUPABASE_URL` | Production Supabase URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `REDIS_URL` | Production Redis URL |
| `OPENAI_API_KEY` | CrewAI LLM access |

**Note**: These should be environment-specific and managed separately from CI test secrets.
