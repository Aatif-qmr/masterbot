# GitHub Advanced Features - Setup Guide

This document explains the advanced GitHub free-tier features that have been configured for this repository.

## 🚀 Activated Features

### 1. Dependabot (Automatic Dependency Updates)
**File:** `.github/dependabot.yml`

**What it does:**
- Automatically checks for outdated Python packages weekly
- Creates pull requests to update dependencies
- Groups minor updates together to reduce PR noise
- Updates GitHub Actions workflows automatically
- Labels updates as "security" or "dependencies"

**Schedule:** Every Monday at 09:00 UTC

**You'll see:**
- PRs titled `chore(deps): bump package-name`
- Automatic security alerts for vulnerable dependencies
- Grouped updates for non-breaking changes

---

### 2. CodeQL Security Analysis
**File:** `.github/workflows/codeql.yml`

**What it does:**
- Scans Python code for security vulnerabilities
- Detects common coding errors and bugs
- Runs on every push and pull request
- Provides detailed reports in the Security tab
- Integrates with GitHub's security advisory database

**Schedule:** 
- On every push/PR to main/master/develop branches
- Weekly scan every Monday at 02:00 UTC

**You'll see:**
- Security alerts in the "Security" tab
- Code scanning results on PRs
- Recommendations for fixing vulnerabilities

---

### 3. Stale Issue/PR Management
**File:** `.github/workflows/stale.yml`

**What it does:**
- Automatically marks inactive issues as "stale" after 30 days
- Closes stale issues after 14 more days of inactivity
- Marks inactive PRs as "stale" after 14 days
- Closes stale PRs after 7 more days
- Exempts important labels (bug, enhancement, security, pinned)

**Schedule:** Daily at 03:00 UTC

**Benefits:**
- Keeps issue tracker clean and focused
- Encourages timely responses
- Reduces maintenance overhead

---

### 4. Structured Issue Templates
**Files:** `.github/ISSUE_TEMPLATE/*.yml`

**Templates created:**
1. **Bug Report** (`bug_report.yml`)
   - Captures environment details
   - Requests reproduction steps
   - Asks for log output
   - Component selection dropdown

2. **Feature Request** (`feature_request.yml`)
   - Priority level selection
   - Component impact analysis
   - Alternative solutions section

3. **Performance Issue** (`performance_issue.yml`)
   - Benchmark metrics capture
   - Target performance goals
   - Hardware/environment specs

**Benefits:**
- Standardized issue reporting
- Faster triage and resolution
- Better context for developers

---

### 5. Pull Request Template
**File:** `.github/pull_request_template.md`

**What it includes:**
- Change type checklist
- Related issues linking
- Testing requirements
- Code review checklist
- Screenshots/logs section

**Benefits:**
- Consistent PR descriptions
- Ensures testing is documented
- Reminds contributors of best practices

---

## 📊 How to Monitor

### Dependabot
- Go to **Insights → Dependency graph → Dependabot**
- View pending updates and security alerts

### CodeQL
- Go to **Security → Code scanning alerts**
- Review vulnerability reports and fix recommendations

### Stale Bot
- Watch for comments on old issues/PRs
- Look for "stale" label additions
- Check workflow runs in **Actions → Close Stale Issues and PRs**

### Issues
- New issues will use templates automatically
- Filter by template type using labels

---

## ⚙️ Customization

### Adjust Dependabot Schedule
Edit `.github/dependabot.yml`:
```yaml
schedule:
  interval: "daily"  # Change from weekly to daily
  time: "06:00"      # Change time
```

### Modify Stale Timings
Edit `.github/workflows/stale.yml`:
```yaml
days-before-issue-stale: 60    # Increase from 30 to 60 days
days-before-pr-close: 14       # Increase from 7 to 14 days
```

### Add More Issue Templates
Create new files in `.github/ISSUE_TEMPLATE/` following the YAML format.

---

## 🔐 Permissions Required

These features require the following repository permissions (all enabled by default):
- **Actions:** Read (for workflows)
- **Contents:** Read (for CodeQL)
- **Issues:** Write (for stale bot)
- **Pull Requests:** Write (for stale bot)
- **Security Events:** Write (for CodeQL)

---

## 🎯 Next Steps

1. **Push these files** to your repository:
   ```bash
   git add .github/
   git commit -m "feat: add GitHub advanced features configuration"
   git push
   ```

2. **Wait for activation** (usually within 5-10 minutes):
   - Dependabot will create its first check
   - CodeQL will run on next push
   - Stale bot will start monitoring

3. **Monitor the Actions tab**:
   - Verify workflows are running successfully
   - Check for any permission errors

4. **Review Security tab**:
   - Enable CodeQL results display
   - Set up email notifications for security alerts

---

## 📝 Notes

- All features are **free** for public repositories
- Private repositories get limited CodeQL scans (but still functional)
- Dependabot works on both public and private repos
- Stale bot helps maintain project hygiene automatically
- Issue templates improve community contribution quality

For questions or issues with these configurations, check the [GitHub Documentation](https://docs.github.com/).
