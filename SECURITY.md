# Security policy

Crossroad v0.1 is a working beta and a public reference, not a product. We still want to hear about security problems.

## Report a vulnerability privately

Use GitHub's **Report a vulnerability** button (private security advisories) on this repository: open the repository's **Security** tab, then **Report a vulnerability**.

**Do not open a public issue for a security bug.** Public issues are visible to everyone before a fix exists.

## What helps

- What you saw, and which file or document it concerns.
- How to reproduce it, using the example values in this repository.
- Whether you believe it affects only this reference code or also the design.

## Scope notes

- `reference/` is offline-tested reference code, not the production install. Town Hall and the PC doorbells are not part of this repository.
- Known weak points we already list: [docs/KNOWN_LIMITS.md](docs/KNOWN_LIMITS.md) and the boundaries in [docs/TRUST_RULES.md](docs/TRUST_RULES.md).
- Do not send real secrets, keys or private data in a report. Placeholders are enough.
