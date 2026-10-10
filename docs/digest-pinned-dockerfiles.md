# Digest pinned Dockerfiles

A `Dockerfile` that pins the image by tag *and* digest is updated in full:

```diff
-FROM golang:1.26.6-alpine@sha256:3889b425...2d83 AS builder
+FROM golang:1.27.0-alpine@sha256:4c9fe601...6dbc AS builder
```

The digest of the new tag is looked up anonymously on Docker Hub. Docker
resolves a `tag@digest` reference by digest and ignores the tag, so leaving the
old digest in place would keep building with the previous Go version while the
`go.mod` file already requires the new one.

A rate limited or dropped request is retried with an exponential backoff, and a
`Retry-After` header is honoured, because the anonymous pull limit is shared
with every other job running on the same GitHub runner IP. A `404` is not
retried: that tag is simply not there.

If the lookup still fails - the registry stays unreachable, or the `golang`
image for the new version has not been published yet, which happens because
<https://go.dev/dl> lists a release before the official image is built - nothing
is written at all and the workflow run fails. No pull request is created, so a
`Dockerfile` that can no longer be bumped, for instance because its base image
variant was dropped in the new Go release, is visible instead of silently
landing in a pull request. The next scheduled run tries again.
