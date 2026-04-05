# AIGC Interactive Demo

Interactive companion to the [AIGC SDK](https://github.com/nealsolves/aigc) — seven
hands-on labs for the M2 governance capabilities plus a v0.3.2 architecture guide
covering unified default mode and opt-in split enforcement.

**Live demo:** [https://nealsolves.github.io/aigc/](https://nealsolves.github.io/aigc/)

## Labs

| Lab | Topic |
| --- | ----- |
| 1 | Risk Scoring — `strict`, `risk_scored`, and `warn_only` modes |
| 2 | Signing & Verification — HMAC-SHA256 artifact signing; tamper detection |
| 3 | Audit Chain — hash-chained artifacts; chain continuity verification |
| 4 | Policy Composition — `intersect`, `union`, and `replace` strategies |
| 5 | Loaders & Versioning — pluggable `PolicyLoader`; policy date enforcement |
| 6 | Custom Gates — `EnforcementGate` plugins at all four pipeline insertion points |
| 7 | Compliance Dashboard — compliance export from a JSONL audit trail |

## Architecture

The demo has two deployed components:

- **React frontend** — built with Vite, deployed to GitHub Pages via `.github/workflows/deploy-demo-react.yml` on every push to `main` that touches `demo-app-react/`. The API URL is baked in at build time via the `VITE_API_URL` GitHub secret.
- **FastAPI backend** (`demo-app-api/`) — deployed on Render at `https://aigc-2oaf.onrender.com`. The React app calls this backend for all lab enforcement, signing, chaining, composition, and loader operations. No user API keys are required.

## Development

```bash
cd demo-app-react
npm install
npm run dev
```

## Build

```bash
npm run build
```

Output is in `dist/`. The app is configured with `base: '/aigc/'` for deployment
under `https://nealsolves.github.io/aigc/`.

## Deployment

Pushes to `main` that touch `demo-app-react/` trigger automatic deployment to
GitHub Pages via `.github/workflows/deploy-demo-react.yml`.
