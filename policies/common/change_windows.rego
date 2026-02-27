package network.common

import future.keywords.if
import future.keywords.in

# ─────────────────────────────────────────────
# Change Window Enforcement
# ─────────────────────────────────────────────
# Deny changes outside approved change windows unless emergency flag is set.
# Change window times are defined in the customer's policy.yaml and passed
# in as input.customer_policy.change_management

deny[msg] if {
    not input.change.emergency
    not in_change_window
    msg := sprintf(
        "Change requested outside of approved window. Next window: %v. Set emergency=true to override (requires approver sign-off).",
        [next_window_str]
    )
}

in_change_window if {
    window := input.customer_policy.change_management.change_windows[_]
    window.day == input.change.day_of_week
    time_in_range(input.change.time_utc, window.start, window.end)
}

# Simplified time range check (HH:MM strings)
time_in_range(t, start, end) if {
    t >= start
    t <= end
}

next_window_str := "Check customer policy for next scheduled window"


# ─────────────────────────────────────────────
# Device Maintenance Window
# ─────────────────────────────────────────────
deny[msg] if {
    device := input.resolution_plan.affected_devices[_]
    device.in_maintenance == true
    msg := sprintf(
        "Device '%v' is in active maintenance window. Maintenance ends: %v",
        [device.name, device.maintenance_end]
    )
}


# ─────────────────────────────────────────────
# Change Freeze Periods
# ─────────────────────────────────────────────
# Global freeze periods (e.g. Christmas, financial year end)
# Configured as an array of {start, end} date strings in input.global_policy

deny[msg] if {
    not input.change.emergency
    freeze := input.global_policy.freeze_periods[_]
    input.change.date >= freeze.start
    input.change.date <= freeze.end
    msg := sprintf(
        "Global change freeze in effect from %v to %v. Reason: %v",
        [freeze.start, freeze.end, freeze.reason]
    )
}
