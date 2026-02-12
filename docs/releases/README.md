# Release Documentation

This directory contains release notes and templates for the Cognitive Memory System.

## 📁 Structure

```
releases/
├── README.md (this file)
└── release-notes-template.md (template for new releases)
```

## 📝 Template Usage

1. Copy `release-notes-template.md` to `[version].md` (e.g., `1.2.0.md`)
2. Fill in all sections according to the release
3. Delete unused sections
4. Update the main `CHANGELOG.md` with summary

## 📋 Release Notes Sections

| Section | Purpose |
|----------|-----------|
| **Executive Summary** | Brief 2-3 sentence overview |
| **New Features** | User-facing features added |
| **Bug Fixes** | Bug fixes and patches |
| **Changes** | Breaking changes, deprecations |
| **Migration Notes** | Database/config migrations |
| **Testing** | Test coverage and results |
| **Documentation Updates** | Updated docs for this release |
| **Pre-Release Checklist** | Quality gates and sign-offs |
| **Release Metrics** | Success criteria vs actuals |
| **Notes** | Additional context |

## 🔄 Release Process

### Before Release
1. Complete feature implementation
2. Run full test suite
3. Create release notes from template
4. Update CHANGELOG.md
5. Tag release in git

### After Release
1. Deploy to production
2. Monitor for issues (1 week)
3. Create hotfix if needed
4. Document lessons learned

## 📊 Release Types

| Type | Description | Example |
|-------|-------------|----------|
| **Major** | Breaking changes, new features | 1.0.0 → 2.0.0 |
| **Minor** | New features, backward compatible | 1.0.0 → 1.1.0 |
| **Patch** | Bug fixes only | 1.1.0 → 1.1.1 |
| **Beta** | Feature testing | 1.2.0-beta |

## 🔗 Related Documentation

- [Main CHANGELOG](../CHANGELOG.md)
- [Operations Manual](../operations/operations-manual.md)
- [Production Checklist](../operations/production-checklist.md)
- [Migration Guide](../migration-guide.md)
