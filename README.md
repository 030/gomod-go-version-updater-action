# gomod-go-version-updater-action

## Usage

https://github.com/030/gomod-go-version-updater-action/settings/actions

```
Allow GitHub Actions to create and approve pull requests
```

Create a `~/.github/workflows/gomod-go-version-updater.yml` file:

```bash
---
name: gomod-go-version-updater-action
'on':
  schedule:
    - cron: '42 6 * * *'
permissions:
  contents: write
  pull-requests: write
jobs:
  gomod-go-version-updater-action:
    runs-on: ubuntu-22.04
    steps:
      - uses: 030/gomod-go-version-updater-action@v0.1.0
```

## Test

```bash
pip install pytest pytest-cov requests
pytest --cov=main test.py --verbose --capture=no --cov-report term-missing
```
