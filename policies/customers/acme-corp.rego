package network.customers.acme_corp

import future.keywords.if
import future.keywords.in

# ─────────────────────────────────────────────
# Acme Corp Customer-Specific Policies
# These supplement (not replace) the common policies
# ─────────────────────────────────────────────

# All Acme changes require change ticket reference
deny[msg] if {
    not input.change.ticket_reference
    msg := "Acme Corp requires a change ticket reference (e.g. CHG0012345) for all network changes"
}

deny[msg] if {
    not startswith(input.change.ticket_reference, "CHG")
    msg := sprintf(
        "Invalid ticket reference '%v'. Must start with 'CHG' (ServiceNow change record)",
        [input.change.ticket_reference]
    )
}

# Acme finance group cannot route to public internet directly
deny[msg] if {
    input.intent.source.group == "finance-servers"
    input.intent.destination.external == true
    not input.intent.policy.compliance == "PCI-DSS"
    msg := "Finance servers can only reach external destinations via PCI-DSS compliant paths"
}

# Acme guest network is completely isolated - cannot be source or destination of any intent
deny[msg] if {
    input.intent.source.group == "guest-wifi"
    msg := "Guest network cannot be the source of managed connectivity intents"
}

deny[msg] if {
    "guest-wifi" in input.intent.isolation.deny_groups
    input.intent.source.group != "guest-wifi"
} else = false  # Not a deny - just checking it IS in the deny list (this rule is a whitelist check elsewhere)

# Production intents require senior engineer approval (checked via PR labels in GitHub Actions)
deny[msg] if {
    input.intent.policy.compliance == "PCI-DSS"
    not input.change.senior_engineer_approved
    msg := "PCI-DSS intents require approval from a senior network engineer (label: approved-senior-engineer)"
}

# Bandwidth on PCI VRF is capped below contract max for headroom
deny[msg] if {
    input.intent.policy.compliance == "PCI-DSS"
    input.intent.policy.bandwidth_mbps > 2000
    msg := "PCI VRF bandwidth capped at 2000Mbps per Acme security policy (regardless of contract limit)"
}
