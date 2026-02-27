package network.capacity

import future.keywords.if

# ─────────────────────────────────────────────
# Bandwidth Capacity Checks
# ─────────────────────────────────────────────

deny[msg] if {
    requested_bw := input.intent.policy.bandwidth_mbps
    committed_bw := input.topology.site_committed_bandwidth_mbps
    available_bw := input.topology.site_max_bandwidth_mbps - committed_bw
    requested_bw > available_bw
    msg := sprintf(
        "Insufficient bandwidth at site. Requested: %vMbps, Available: %vMbps (Max: %vMbps, Committed: %vMbps)",
        [requested_bw, available_bw, input.topology.site_max_bandwidth_mbps, committed_bw]
    )
}

deny[msg] if {
    input.intent.policy.bandwidth_mbps > input.customer_policy.capacity_limits.max_bandwidth_mbps
    msg := sprintf(
        "Requested bandwidth %vMbps exceeds customer contract limit of %vMbps",
        [input.intent.policy.bandwidth_mbps, input.customer_policy.capacity_limits.max_bandwidth_mbps]
    )
}


# ─────────────────────────────────────────────
# VRF Capacity Checks
# ─────────────────────────────────────────────

deny[msg] if {
    input.resolution_plan.requires_new_vrf == true
    current_vrf_count := input.topology.tenant_vrf_count
    max_vrfs := input.customer_policy.capacity_limits.max_vrfs
    current_vrf_count >= max_vrfs
    msg := sprintf(
        "VRF limit reached. Customer has %v/%v VRFs. Cannot create new VRF for this intent.",
        [current_vrf_count, max_vrfs]
    )
}


# ─────────────────────────────────────────────
# Prefix/Route Table Capacity
# ─────────────────────────────────────────────

deny[msg] if {
    new_prefixes := count(input.intent.destination.prefixes)
    current_prefix_count := input.topology.vrf_prefix_count
    max_prefixes := input.customer_policy.capacity_limits.max_prefixes_per_vrf
    (current_prefix_count + new_prefixes) > max_prefixes
    msg := sprintf(
        "Adding %v prefixes would exceed VRF prefix limit of %v (currently at %v)",
        [new_prefixes, max_prefixes, current_prefix_count]
    )
}


# ─────────────────────────────────────────────
# SLA Feasibility (Physical Path Constraints)
# ─────────────────────────────────────────────

deny[msg] if {
    input.intent.policy.max_latency_ms != null
    input.topology.path_min_latency_ms > input.intent.policy.max_latency_ms
    msg := sprintf(
        "Requested SLA of %vms cannot be met. Minimum achievable latency on available path: %vms",
        [input.intent.policy.max_latency_ms, input.topology.path_min_latency_ms]
    )
}
