# Network-as-Code Repository

## Overview

This repository is the **single source of truth** for all network intent across managed customers.
No change reaches the network without first going through a pull request in this repo.

## How It Works

```
Engineer writes YAML intent
       │
       ▼
  Git Pull Request
       │
       ▼
  CI Pipeline (automated)
  ├── Schema validation (pykwalify)
  ├── OPA policy checks
  ├── Batfish simulation
  └── Config rendering preview
       │
       ▼
  Human Review + Approval
       │
       ▼
  PR Merged → N8N Deployment Workflow triggered
       │
       ▼
  Nornir pushes config to devices
       │
       ▼
  Telemetry verification
       │
       ▼
  Nautobot Intent status → deployed ✓
```

## Repository Structure

```
network-as-code/
├── schema/                  # YAML validation schemas
├── policies/                # OPA Rego policy files
│   ├── common/              # Shared policies (all customers)
│   └── customers/           # Per-customer policy overrides
├── templates/               # Jinja2 config templates per vendor/OS
├── global/                  # Shared infrastructure intent
├── customers/               # Per-customer intent definitions
│   └── <customer-name>/
│       ├── customer.yaml    # Customer metadata
│       ├── policy.yaml      # Customer policy overrides
│       ├── sites/           # Site definitions
│       ├── intents/         # Intent YAML files
│       └── rendered/        # Auto-generated configs (do not edit)
├── scripts/                 # CI pipeline scripts
└── .github/workflows/       # GitHub Actions pipelines
```

## Adding a New Intent

1. Create a new YAML file under `customers/<name>/intents/<type>/`
2. Follow the naming convention: `<description>-<sequence>.yaml` e.g. `fin-pci-connectivity-001.yaml`
3. Open a Pull Request — CI will validate automatically
4. Assign a reviewer from the network team
5. On approval and merge, deployment triggers automatically

## Adding a New Customer

1. Copy the `customers/_template/` directory
2. Fill in `customer.yaml` and `policy.yaml`
3. Add site definitions under `sites/`
4. Open a PR titled `[NEW CUSTOMER] <customer-name>`

## Rollback

Every deployed intent has a `rendered/<device>/deployed.yaml` snapshot.
To rollback: revert the merge commit and open a PR — the pipeline handles the rest.
