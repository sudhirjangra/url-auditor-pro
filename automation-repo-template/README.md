# URL Auditor — Automation Repo

Private repo for running URL audits automatically via GitHub Actions.

## Setup

1. Create a **new private GitHub repo** and push this folder's contents into it.
2. Add a repo secret named `AUDITOR_REPO_TOKEN`:
   - Go to repo **Settings → Secrets → Actions → New repository secret**
   - Name: `AUDITOR_REPO_TOKEN`
   - Value: a GitHub Personal Access Token (PAT) with `read:packages` + `contents:read` scope
     on the source repo (`url-auditor-pro`).
3. Edit `autorun.yml` line 25 — replace `YOUR_GITHUB_USERNAME/url-auditor-pro` with the actual
   repo path where releases are published.

## How to run

1. Push/update `input.xlsx` (and optionally `url_auditor_config.xml`) to `main`.
2. GitHub Actions triggers automatically, downloads the latest `URL Auditor Auto.exe`,
   runs the audit, and commits the output folder back to this repo.
3. Download the `output_YYYY-MM-DD_HH-MM-SS/` folder from the repo.

## Column configuration

Columns are read from `url_auditor_config.xml`:
```xml
<url_auditor_config>
  <url_column>Website URL</url_column>
  <status_column>Current Status</status_column>
  ...
</url_auditor_config>
```
Set these once in the GUI app and the XML is saved automatically. Then commit the updated XML here.

## Manual trigger

Go to **Actions → Run URL Audit → Run workflow** to trigger without pushing a file.
