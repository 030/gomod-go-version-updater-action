# Configuration

Optional settings for the
[workflow from the Quickstart](../README.md#quickstart).

1. To ensure that an action is triggered for testing the Golang version update,
   add a `pull_request_review` trigger. This will cause a specific Workflow
   Action to run whenever someone submits a review for the pull request created
   by the **gomod-go-version-updater-action**:
   ```yml
   "on":
     # required by gomod-go-version-updater to trigger this action once pr has
     # been reviewed
     pull_request_review:
       types: [submitted]
   ```
1. Optional: if private go modules have to be downloaded:
   ```yml
   - uses: 030/gomod-go-version-updater-action@d212eb593e210eca20f3c42cbcbf3cdeb9dd3a54 # v0.3.8
     with:
       github-token-for-downloading-private-go-modules: ${{ secrets.GITHUB_TOKEN }}
   ```
1. Optional: set the log level to `DEBUG`, `WARNING`, `ERROR` or `CRITICAL`
   (default: INFO):
   ```yml
   - uses: 030/gomod-go-version-updater-action@d212eb593e210eca20f3c42cbcbf3cdeb9dd3a54 # v0.3.8
     with:
       gomod-go-version-updater-action-log-level: DEBUG
   ```
1. Optional: add an extra label to the PR that will be created:
   ```yml
   - uses: 030/gomod-go-version-updater-action@d212eb593e210eca20f3c42cbcbf3cdeb9dd3a54 # v0.3.8
     with:
       extra-pr-label: something
   ```
