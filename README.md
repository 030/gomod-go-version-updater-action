# gomod-go-version-updater-action

## Usage

Create a `~/.github/workflows/gomod-go-version-updater.yml` file:

```bash
---
name: gomod-go-version-updater-action
'on':
  schedule:
    - cron: '42 6 * * *'
permissions:
  actions: none
  checks: none
  contents: none
  deployments: none
  id-token: none
  issues: write
  discussions: none
  packages: none
  pages: none
  pull-requests: write
  repository-projects: none
  security-events: none
  statuses: none
jobs:
  gomod-go-version-updater-action:
    runs-on: ubuntu-22.04
    steps:
      - uses: 030/gomod-go-version-updater-action@v0.1.0
```

## Test

```bash
pip install pytest pytest-cov
pytest --cov=main test.py --verbose --capture=no --cov-report term-missing
```
