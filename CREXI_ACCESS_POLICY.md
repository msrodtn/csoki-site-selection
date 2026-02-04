# Crexi Access Policy

**Version:** 1.0  
**Last Updated:** 2026-02-04  
**Owner:** CSOKi Development Team

---

## Purpose

This document defines the security and usage constraints for automated Crexi access via the CSOKi platform.

---

## Access Constraints

### ✅ Permitted Actions

1. **Read-Only Access**
   - View listings in explicitly tasked markets
   - Export CSV data for analysis
   - Cache listing data for 24 hours

2. **Automated Searches**
   - Search by city/state or ZIP code
   - Apply property type filters (Land, Retail, Office, Industrial)
   - Apply "For Sale" status filter

3. **Data Usage**
   - Import listings to internal database
   - Display on CSOKi platform map
   - Analyze for opportunity scoring

### ❌ Prohibited Actions

1. **Account Modifications**
   - Never modify account settings
   - Never change saved searches
   - Never update user profile

2. **Communications**
   - Never contact brokers via Crexi platform
   - Never send messages or inquiries
   - Never mark properties as favorites or saved

3. **Data Misuse**
   - Never scrape data beyond explicitly tasked markets
   - Never share credentials with third parties
   - Never bypass rate limiting or abuse the platform

---

## Security Requirements

### Credential Management

1. **Storage**
   - Credentials stored in Railway environment variables only
   - Never committed to git repository
   - Never exposed to frontend code
   - Never logged in plain text

2. **Access**
   - Backend-only access to credentials
   - No credential sharing between services
   - Rotate credentials every 90 days

### Session Logging

Every Crexi automation session MUST be logged with:
- Timestamp (UTC)
- Action performed (login, search, export)
- Location searched
- Success/failure status
- Error messages (if any)

**Log location:** `logs/crexi_sessions.log`

**Example log entry:**
```
[2026-02-04T15:30:00Z] Session started
[2026-02-04T15:30:05Z] Logging in as dgreenwood@ballrealty.com
[2026-02-04T15:30:08Z] Login successful
[2026-02-04T15:30:10Z] Searching for location: Des Moines, IA
[2026-02-04T15:30:15Z] Search completed for: Des Moines, IA
[2026-02-04T15:30:20Z] CSV exported: crexi_export_20260204.xlsx
[2026-02-04T15:30:25Z] Session ended
```

### Rate Limiting

1. **Per-Location Limits**
   - Max 1 export per location per hour
   - Enforced via cache check before triggering automation

2. **Global Limits**
   - Max 20 exports per day
   - Max 100 exports per month

3. **Timeout Protection**
   - 90-second timeout per export
   - Graceful failure if timeout exceeded

---

## Compliance

### Terms of Service

- Use Crexi's export feature as intended
- Respect Crexi's rate limits and guidelines
- Do not reverse-engineer or scrape beyond official export

### Data Privacy

- Only process publicly available listing data
- Do not store broker personal information beyond what's in export
- Comply with GDPR/CCPA for end-user data

### Monitoring

- Review session logs weekly
- Alert on anomalies (high failure rate, unusual locations)
- Audit credentials quarterly

---

## Incident Response

### If Credentials Compromised

1. Immediately rotate Crexi password
2. Update Railway environment variables
3. Review recent session logs for suspicious activity
4. Notify team lead

### If Account Flagged/Locked

1. Pause all automation immediately
2. Contact Crexi support to resolve
3. Review logs to identify cause
4. Implement additional safeguards before resuming

### If Terms Violation Suspected

1. Immediately halt all Crexi automation
2. Consult with legal counsel
3. Document incident
4. Implement corrective measures

---

## Approvals

**Approved by:** Michael Greenwood (Product Owner)  
**Date:** 2026-02-04  
**Next Review:** 2026-05-04 (90 days)

---

## Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-02-04 | 1.0 | Initial policy creation | Subagent |
