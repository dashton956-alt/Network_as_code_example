package network.compliance

import future.keywords.if
import future.keywords.in

# ─────────────────────────────────────────────
# PCI-DSS Compliance Checks
# ─────────────────────────────────────────────

deny[msg] if {
    input.intent.policy.compliance == "PCI-DSS"
    not input.intent.policy.encryption == "required"
    msg := "PCI-DSS intents require encryption=required"
}

deny[msg] if {
    input.intent.policy.compliance == "PCI-DSS"
    proto := input.intent.isolation.deny_protocols[_]
    not prohibited_protocol_blocked(proto)
    msg := sprintf("PCI-DSS requires protocol '%v' to be explicitly denied", [proto])
}

# PCI prohibited protocols must appear in the deny list
prohibited_protocol_blocked(proto) if {
    pci_prohibited := {"telnet", "http", "ftp", "snmpv1", "snmpv2"}
    pci_prohibited[proto]
    proto in input.intent.isolation.deny_protocols
}

# PCI intents must not share a VRF with non-PCI intents
deny[msg] if {
    input.intent.policy.compliance == "PCI-DSS"
    existing := input.existing_intents[_]
    existing.status == "deployed"
    existing.policy.compliance != "PCI-DSS"
    existing_vrf := existing.resolved.vrf_name
    proposed_vrf := input.resolution_plan.vrf_name
    existing_vrf == proposed_vrf
    msg := sprintf(
        "PCI-DSS intent cannot share VRF '%v' with non-PCI intent '%v'",
        [proposed_vrf, existing.id]
    )
}


# ─────────────────────────────────────────────
# General Encryption Requirements
# ─────────────────────────────────────────────

deny[msg] if {
    input.intent.destination.external == true
    input.intent.policy.encryption == "none"
    msg := "External-facing intents require at minimum encryption=preferred"
}


# ─────────────────────────────────────────────
# Feature Entitlement
# ─────────────────────────────────────────────
# Check that requested features are in the customer's contract

deny[msg] if {
    input.intent.type == "connectivity"
    input.resolution_plan.requires_mpls == true
    not "mpls" in input.customer_policy.allowed_features
    msg := "Customer contract does not include MPLS. Cannot resolve connectivity via MPLS path."
}

deny[msg] if {
    input.intent.type == "service"
    input.intent.service_type == "sdwan"
    not "sdwan" in input.customer_policy.allowed_features
    msg := "Customer contract does not include SD-WAN service tier."
}


# ─────────────────────────────────────────────
# Compliance Profile Authorization
# ─────────────────────────────────────────────

deny[msg] if {
    requested_profile := input.intent.policy.compliance
    requested_profile != "none"
    not requested_profile in input.customer_policy.compliance_profiles
    msg := sprintf(
        "Compliance profile '%v' not authorized for this customer. Authorized profiles: %v",
        [requested_profile, input.customer_policy.compliance_profiles]
    )
}
