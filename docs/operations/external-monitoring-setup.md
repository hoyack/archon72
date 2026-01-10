# External Monitoring Setup Guide

## Overview

This guide describes how to configure external monitoring services for the Archon 72 Conclave Backend. External monitoring enables independent detection of system unavailability without relying on self-reporting (FR54, CT-11).

## Constitutional Context

**FR54**: System unavailability SHALL be independently detectable by external parties.

**CT-11**: Silent failure destroys legitimacy.

External monitoring ensures that system failures are detected even if the system itself cannot report its status. This is critical for constitutional integrity - observers should not have to trust our self-reporting.

## External Health Endpoint

### Endpoint Details

```
GET /health/external
```

**Characteristics:**
- No authentication required
- Response time target: <50ms
- Returns minimal JSON response
- No database queries in hot path

### Response Format

```json
{
  "status": "up",
  "timestamp": "2026-01-08T12:00:00.000000Z"
}
```

### Status Values

| Status | Description | Action |
|--------|-------------|--------|
| `up` | System operational | No action needed |
| `halted` | Constitutional halt active | Investigate immediately |
| `frozen` | System ceased (read-only) | System is permanently frozen |
| (timeout) | System down | Alert operations team |

**Note**: "down" is inferred by monitors when they receive no response (timeout), not returned by the endpoint.

## Recommended External Services

### Tier 1: Production-Ready Services

#### UptimeRobot (Recommended)
- **Free tier**: 50 monitors, 5-minute intervals
- **Pro tier**: Unlimited monitors, 1-minute intervals
- **Features**: Multi-location, SMS/email alerts
- **Setup**: See [UptimeRobot Configuration](#uptimerobot-configuration)

#### Pingdom
- **Plans**: Commercial, starts at $10/month
- **Features**: 100+ locations, advanced analytics
- **Best for**: Enterprise with SLA requirements

#### Better Uptime
- **Free tier**: Limited monitors
- **Pro tier**: Full features, status pages
- **Features**: Incident management, on-call schedules

### Tier 2: Additional Options

- **StatusCake**: Free tier with 10 monitors
- **Site24x7**: Comprehensive monitoring suite
- **Datadog Synthetics**: If already using Datadog

## Multi-Geographic Configuration

### Why Multiple Locations?

Single-location monitoring can produce false positives due to:
- Regional network issues
- ISP-specific problems
- DNS propagation delays

**Best Practice**: Monitor from at least 3 geographic regions.

### Recommended Regions

| Priority | Region | Rationale |
|----------|--------|-----------|
| 1 | US East (Virginia) | Primary infrastructure region |
| 2 | EU West (Ireland/Frankfurt) | European users |
| 3 | Asia Pacific (Singapore/Tokyo) | Asian users |
| 4 | US West (California) | West coast redundancy |

## Configuration Examples

### UptimeRobot Configuration

1. **Create New Monitor**
   - Monitor Type: HTTP(s)
   - URL: `https://your-domain.com/health/external`
   - Friendly Name: `Archon72 External Health`

2. **Configure Check Settings**
   - Monitoring Interval: 5 minutes (free) or 1 minute (pro)
   - Timeout: 30 seconds (generous for edge cases)
   - Keyword: `"status"` (optional, validates JSON response)

3. **Configure Alerts**
   - Alert after: 2 failed checks (reduces flapping)
   - Alert contacts: PagerDuty, Slack, Email
   - Recovery notification: Yes

4. **Multi-Location Settings** (Pro only)
   - Enable: All available locations
   - Alert threshold: Alert when majority fail

### Pingdom Configuration

```yaml
check:
  name: Archon72 External Health
  host: your-domain.com
  url: /health/external
  type: http
  resolution: 1  # minutes

probe_filters:
  - region: NA
  - region: EU
  - region: APAC

alert_policy:
  alert_when_down_for: 2  # checks
  alert_via:
    - pagerduty
    - slack
```

### StatusCake Configuration

1. **New Website Test**
   - Test Type: HTTP
   - Website URL: `https://your-domain.com/health/external`
   - Check Rate: 5 minutes

2. **Advanced Settings**
   - Confirmation: 2 (wait for 2 failures)
   - Timeout: 30 seconds
   - SSL Check: Yes

3. **Contact Groups**
   - Add PagerDuty/Slack integrations
   - Enable recovery alerts

## Alert Integration

### PagerDuty Integration

Most monitoring services support PagerDuty integration:

1. Create a PagerDuty Service for Archon72
2. Get the Integration Key
3. Add to your monitoring service's webhook/integration settings

**Severity Mapping:**
- System down (timeout): P1 (Critical)
- System halted: P1 (Critical)
- System frozen: P2 (High) - investigate but system is stable

### Slack Integration

Configure Slack webhooks for non-critical notifications:

```
Channel: #archon72-alerts
Webhook URL: https://hooks.slack.com/services/...
```

**Message Template:**
```
:warning: Archon72 External Health Alert
Status: {status}
Location: {check_location}
Time: {timestamp}
```

## Response Verification

### Expected Responses

**Healthy System:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"up","timestamp":"2026-01-08T12:00:00.000000Z"}
```

**Halted System:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"halted","timestamp":"2026-01-08T12:00:00.000000Z"}
```

**Frozen System:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"frozen","timestamp":"2026-01-08T12:00:00.000000Z"}
```

### Keyword Monitoring

Configure keyword checks to validate response:

```
Required keyword: "status"
Content type: application/json
```

This ensures the endpoint returns valid JSON, not an error page.

## False Positive Mitigation

### Common False Positive Sources

1. **Single Location Failure**: Network issue at one monitoring location
2. **Transient Timeout**: Brief spike in response time
3. **DNS Issues**: DNS propagation or resolver problems
4. **SSL Certificate**: Certificate renewal in progress

### Mitigation Strategies

1. **Confirmation Threshold**: Wait for 2+ consecutive failures
2. **Multi-Location**: Alert only when majority of locations fail
3. **Timeout Buffer**: Use 30-second timeout (generous)
4. **Separate SSL Check**: Monitor SSL expiry separately

## Runbook: External Monitor Alert

### Alert: System Down (Timeout)

1. **Verify the alert**
   - Check from multiple locations (curl from different regions)
   - Check internal monitoring dashboards

2. **If confirmed down**
   - Check infrastructure status (AWS/GCP/Supabase)
   - Check recent deployments
   - Check error logs
   - Escalate to on-call

3. **If false positive**
   - Document the false positive
   - Consider adjusting thresholds

### Alert: System Halted

1. **Do NOT attempt to clear halt automatically**
   - Halt is a constitutional protection mechanism
   - Requires deliberate recovery procedure

2. **Investigate halt reason**
   - Check internal logs for halt trigger
   - Review recent events for fork/conflict

3. **Follow halt recovery procedure**
   - See: [Halt & Fork Recovery Runbook](runbooks/epic-3-halt-fork.md)

### Alert: System Frozen

1. **Verify cessation occurred**
   - Check internal logs for cessation event
   - Frozen state is permanent

2. **Ensure read-only access works**
   - Observer API should still function
   - Historical data must be accessible

3. **No recovery possible**
   - Frozen state is by design
   - Focus on preserving historical access

## Monitoring Dashboard

Consider creating a unified dashboard that shows:

1. External monitor status (from monitoring service)
2. Internal health metrics (Prometheus/Grafana)
3. Constitutional health (separate from operational)

This helps distinguish between:
- **Operational health**: Is the system running?
- **Constitutional health**: Is the system operating correctly?

## Testing the Setup

### Manual Verification

```bash
# Test endpoint response
curl -v https://your-domain.com/health/external

# Test from multiple locations using online tools
# - https://www.uptrends.com/tools/uptime-checker
# - https://check-host.net/check-http
```

### Chaos Testing

Periodically verify that monitors detect failures:

1. **Simulated outage**: Temporarily block the endpoint
2. **Simulated halt**: Trigger a test halt (staging only!)
3. **Verify alert flow**: Confirm alerts reach PagerDuty/Slack

## Maintenance

### Regular Tasks

- [ ] Weekly: Review alert history for false positives
- [ ] Monthly: Verify all monitoring locations are active
- [ ] Quarterly: Test alert flow end-to-end
- [ ] Annually: Review and update monitoring configuration

### SSL Certificate Monitoring

Set up separate SSL certificate monitoring:
- Alert 30 days before expiry
- Alert 7 days before expiry (critical)

This prevents SSL-related false positives.
