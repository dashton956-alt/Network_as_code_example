#!/usr/bin/env python3
"""
scripts/validation/run_opa_checks.py

Fetches Nautobot context and runs OPA policy checks against changed intents.
Posts results back as structured JSON for the GitHub Actions step to consume.
"""

import argparse
import json
import sys
import os
import yaml
from pathlib import Path
from datetime import datetime, timezone

import httpx


def load_intent_file(filepath: str) -> dict:
    with open(filepath) as f:
        return yaml.safe_load(f)


def get_tenant_from_path(filepath: str) -> str:
    """Extract tenant name from file path: customers/<tenant>/intents/..."""
    parts = Path(filepath).parts
    try:
        idx = list(parts).index("customers")
        return parts[idx + 1]
    except (ValueError, IndexError):
        raise ValueError(f"Cannot determine tenant from path: {filepath}")


def fetch_nautobot_context(
    nautobot_url: str,
    nautobot_token: str,
    tenant: str,
    intent: dict
) -> dict:
    """
    Fetch all context OPA needs from Nautobot via GraphQL.
    Returns a bundle that gets passed as input to OPA.
    """
    headers = {
        "Authorization": f"Token {nautobot_token}",
        "Content-Type": "application/json",
    }

    # GraphQL query to pull everything OPA needs in one round trip
    query = """
    query GetOPAContext($tenant: [String]) {
        tenant(name: $tenant) {
            name
            customFields
        }
        devices(tenant: $tenant) {
            name
            platform { slug }
            site { name }
            customFields
        }
        prefixes(tenant: $tenant, status: "active") {
            prefix
            vrf { name }
        }
    }
    """

    resp = httpx.post(
        f"{nautobot_url}/api/graphql/",
        headers=headers,
        json={"query": query, "variables": {"tenant": [tenant]}},
        timeout=30,
    )
    resp.raise_for_status()
    graph_data = resp.json()

    # Fetch existing intents for conflict detection
    intents_resp = httpx.get(
        f"{nautobot_url}/api/plugins/intent-engine/intents/",
        headers=headers,
        params={"tenant": tenant, "status": "deployed"},
        timeout=30,
    )
    intents_resp.raise_for_status()
    existing_intents = intents_resp.json().get("results", [])

    # Fetch customer policy from the policy.yaml in the repo
    # (In production this would also be synced into Nautobot custom fields)
    customer_policy_path = f"customers/{tenant}/policy.yaml"
    customer_policy = {}
    if os.path.exists(customer_policy_path):
        with open(customer_policy_path) as f:
            customer_policy_data = yaml.safe_load(f)
            customer_policy = customer_policy_data.get("customer", {})

    # Build the topology context (simplified for example)
    topology = {
        "site_committed_bandwidth_mbps": 450,  # Would come from Nautobot telemetry
        "site_max_bandwidth_mbps": 1000,
        "path_min_latency_ms": 8,
        "tenant_vrf_count": 3,
        "vrf_prefix_count": 45,
    }

    now = datetime.now(timezone.utc)

    return {
        "intent": intent.get("intent", {}),
        "customer_policy": customer_policy,
        "topology": topology,
        "existing_intents": existing_intents,
        "global_policy": {
            "freeze_periods": []  # Would be fetched from a global config
        },
        "change": {
            "day_of_week": now.strftime("%A").lower(),
            "time_utc": now.strftime("%H:%M"),
            "date": now.strftime("%Y-%m-%d"),
            "emergency": False,
            "ticket_reference": intent.get("intent", {}).get("change_ticket", ""),
            "senior_engineer_approved": False,  # Set by PR label check
        },
        "resolution_plan": {}  # Populated in resolution phase
    }


def run_opa_check(opa_url: str, package_path: str, input_data: dict) -> dict:
    """
    POST input data to OPA and get deny reasons back.
    package_path: e.g. "network/compliance" maps to /v1/data/network/compliance
    """
    resp = httpx.post(
        f"{opa_url}/v1/data/{package_path.replace('.', '/')}",
        json={"input": input_data},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()

    deny_reasons = result.get("result", {}).get("deny", [])
    return {
        "package": package_path,
        "passed": len(deny_reasons) == 0,
        "violations": deny_reasons
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-files", required=True)
    parser.add_argument("--nautobot-url", required=True)
    parser.add_argument("--nautobot-token", required=True)
    parser.add_argument("--opa-url", required=True)
    parser.add_argument("--output-file", default="opa-results.json")
    args = parser.parse_args()

    changed_files = [
        f for f in args.changed_files.strip().split()
        if "intents/" in f and os.path.exists(f)
    ]

    if not changed_files:
        print("No intent files changed")
        results = {"all_passed": True, "checks": []}
        with open(args.output_file, "w") as f:
            json.dump(results, f, indent=2)
        sys.exit(0)

    # OPA policy packages to check (common + customer-specific)
    common_packages = [
        "network.common",        # change_windows.rego
        "network.compliance",    # compliance.rego
        "network.capacity",      # capacity.rego
    ]

    all_checks = []
    any_failed = False

    for filepath in changed_files:
        print(f"\n{'─'*60}")
        print(f"Checking: {filepath}")

        intent = load_intent_file(filepath)
        tenant = get_tenant_from_path(filepath)
        intent_id = intent.get("intent", {}).get("id", filepath)

        # Skip draft intents
        if intent.get("intent", {}).get("status") == "draft":
            print(f"  ⏭️  Skipping draft intent: {intent_id}")
            continue

        # Fetch Nautobot context
        print(f"  📡 Fetching Nautobot context for tenant: {tenant}")
        try:
            opa_input = fetch_nautobot_context(
                args.nautobot_url, args.nautobot_token, tenant, intent
            )
        except Exception as e:
            print(f"  ❌ Failed to fetch Nautobot context: {e}")
            all_checks.append({
                "intent_id": intent_id,
                "passed": False,
                "violations": [f"Nautobot context fetch failed: {e}"]
            })
            any_failed = True
            continue

        # Run common policy packages
        packages_to_check = common_packages.copy()

        # Add customer-specific package if it exists
        customer_package = f"network.customers.{tenant.replace('-', '_')}"
        packages_to_check.append(customer_package)

        intent_violations = []
        for package in packages_to_check:
            print(f"  🔍 OPA check: {package}")
            try:
                result = run_opa_check(args.opa_url, package, opa_input)
                if result["passed"]:
                    print(f"     ✅ Pass")
                else:
                    for v in result["violations"]:
                        print(f"     ❌ {v}")
                    intent_violations.extend(result["violations"])
            except httpx.HTTPError as e:
                msg = f"OPA request failed for {package}: {e}"
                print(f"     ⚠️  {msg}")
                intent_violations.append(msg)

        check_result = {
            "intent_id": intent_id,
            "filepath": filepath,
            "tenant": tenant,
            "passed": len(intent_violations) == 0,
            "violations": intent_violations
        }

        all_checks.append(check_result)

        if not check_result["passed"]:
            any_failed = True

    results = {
        "all_passed": not any_failed,
        "checks": all_checks,
        "total": len(all_checks),
        "passed": sum(1 for c in all_checks if c["passed"]),
        "failed": sum(1 for c in all_checks if not c["passed"])
    }

    with open(args.output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'═'*60}")
    print(f"Results: {results['passed']}/{results['total']} passed")

    if any_failed:
        print("\n❌ OPA policy checks FAILED")
        sys.exit(1)
    else:
        print("\n✅ OPA policy checks PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
