# CSOKi Platform - Coding Standards

**Source:** Garry Tan (YC President) Claude Code workflow  
**Purpose:** Systematic code review framework for high-velocity, high-quality development  
**Goal:** Ship features faster with better quality through structured review

---

## Engineering Philosophy

Before implementing any feature, **review thoroughly** using this framework. For every issue or recommendation, explain concrete tradeoffs, give an opinionated recommendation, and discuss before proceeding.

### Core Principles

- **DRY is important** — flag repetition aggressively
- **Well-tested code is non-negotiable** — better too many tests than too few
- **"Engineered enough"** — not fragile/hacky, not over-abstracted
- **Handle edge cases** — thoughtfulness > speed
- **Explicit > clever** — readability wins

---

## Pre-Implementation Review Checklist

Run through ALL five stages before writing code:

### 1. Architecture Review

Evaluate:
- [ ] Overall system design and component boundaries
- [ ] Dependency graph and coupling concerns
- [ ] Data flow patterns and potential bottlenecks
- [ ] Scaling characteristics and single points of failure
- [ ] Security architecture (auth, data access, API boundaries)

**Questions to ask:**
- Does this fit cleanly into existing architecture?
- Are we creating new coupling that will hurt us later?
- What happens when load increases 10x?
- Where are the security boundaries?

---

### 2. Code Quality Review

Evaluate:
- [ ] Code organization and module structure
- [ ] **DRY violations** — be aggressive here
- [ ] Error handling patterns and missing edge cases (call these out explicitly)
- [ ] Technical debt hotspots
- [ ] Areas that are over-engineered or under-engineered

**Questions to ask:**
- Am I repeating logic that should be abstracted?
- What edge cases am I missing?
- Is error handling comprehensive?
- Is this the right level of abstraction?

---

### 3. Test Review

Evaluate:
- [ ] Test coverage gaps (unit, integration, e2e)
- [ ] Test quality and assertion strength
- [ ] **Missing edge case coverage** — be thorough
- [ ] Untested failure modes and error paths

**Questions to ask:**
- What happens when the API is down?
- What happens with malformed data?
- Are assertions actually validating behavior?
- Have I tested the error paths?

**Coverage goals:**
- Unit tests: Core business logic
- Integration tests: API interactions, database queries
- E2E tests: Critical user flows

---

### 4. Performance Review

Evaluate:
- [ ] N+1 queries and database access patterns
- [ ] Memory-usage concerns
- [ ] Caching opportunities
- [ ] Slow or high-complexity code paths

**Questions to ask:**
- Are we making unnecessary database calls?
- Will this scale with 1000+ results?
- Should this be cached?
- What's the time complexity here?

**Common issues:**
- N+1 queries in loops
- Missing database indexes
- Unbounded memory growth
- O(n²) or worse algorithms

---

### 5. Security Review

Evaluate:
- [ ] API routes and database access patterns
- [ ] Injection vulnerabilities (SQL, XSS, etc.)
- [ ] Authentication and authorization checks
- [ ] Data validation and sanitization
- [ ] Sensitive data exposure

**Questions to ask:**
- Is user input properly validated?
- Are queries parameterized?
- Do we check permissions before data access?
- Are we logging sensitive data?

---

## Issue Resolution Framework

For **every** issue identified during review:

### 1. Describe the Problem
- Concrete description with file/line references
- Why this matters (impact if not fixed)
- Current vs. desired behavior

### 2. Present Options (2-3 minimum)
Include "do nothing" where reasonable.

For each option, specify:
- **Implementation effort** (hours/complexity)
- **Risk** (what could break)
- **Impact on other code** (ripple effects)
- **Maintenance burden** (ongoing cost)

### 3. Recommend & Justify
- Which option do you recommend?
- Why does it align with our engineering principles?
- What are the tradeoffs?

### 4. Get Buy-in
Don't assume — discuss and confirm before proceeding.

---

## Implementation Workflow

### Before You Code

1. **Read the feature requirements** fully
2. **Run this review framework** on your planned approach
3. **Document your architecture** (even if just bullets)
4. **Identify edge cases** upfront
5. **Plan your tests** before implementation

### During Implementation

- **Write tests first** (or alongside) for critical paths
- **Refactor as you go** — don't accumulate debt
- **Document non-obvious decisions** in code comments
- **Run tests frequently** — catch issues early

### Before You Commit

- [ ] All 5 review stages passed
- [ ] Tests written and passing
- [ ] Edge cases handled
- [ ] Documentation updated
- [ ] No console.log/debugging code left
- [ ] No obvious performance issues

---

## CSOKi-Specific Guidelines

### Database Queries
- Always use parameterized queries
- Add indexes for filtered/sorted columns
- Batch operations where possible
- Test with realistic data volumes

### API Integration
- Handle rate limits gracefully
- Retry with exponential backoff
- Cache responses when appropriate
- Validate all external data

### Frontend Performance
- Lazy load heavy components
- Debounce user input handlers
- Minimize re-renders
- Profile before optimizing

### Error Handling
- Never swallow errors silently
- Log errors with context
- Show user-friendly messages
- Provide recovery paths

---

## Success Metrics

Track these to measure framework effectiveness:

- **Development velocity:** Time from start to production-ready
- **Bug rate:** Issues found in review vs. production
- **Test coverage:** % of code covered by tests
- **Code churn:** How often we rewrite the same code
- **Performance:** API response times, page load times

**Goal:** Ship faster with fewer bugs. If velocity drops or quality suffers, revisit the framework.

---

## References

- **Source:** Garry Tan (@garrytan) - Claude Code workflow
- **Tweet:** https://x.com/garrytan/status/2020072098635665909
- **Claimed results:** 4K+ LOC features with full testing in ~1 hour
- **Date adopted:** 2026-02-09

---

## Revision History

- **v1.0** (2026-02-09): Initial framework based on Garry Tan's workflow
- *Future updates will be tracked here*

---

**Remember:** This framework exists to help you ship better code faster. If it feels like bureaucracy, we're doing it wrong. Adjust as needed, but always favor quality over shortcuts.
