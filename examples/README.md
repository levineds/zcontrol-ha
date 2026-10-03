# Home Assistant examples

Replace every example entity ID with the actual ID from **Developer Tools →
States**. Only include sensors your device reports. To use an automation, create
an empty automation, open **Edit in YAML**, and paste one complete automation
file. To use multiple copies, give each copy a different `id`.

- [508 fault alert](508_fault_alert.yaml): watches the 508's readiness, DC pump,
  float, and battery fault sensors. It does not notify on ordinary heartbeat,
  signal-strength, or alarm-count updates. Readiness can overlap another fault,
  so one event may produce more than one notification; remove the readiness
  trigger if you prefer only the individual faults.
- [APak input alert](apak_input_alert.yaml): watches both wired alarm inputs.
  Confirm what each input is connected to before describing it as high water.
- [Offline alert](offline_alert.yaml): optional notification after 30 minutes
  offline. It detects cloud-reported `off`, not an integration that is
  `unavailable` because Home Assistant cannot reach the cloud.
- [508 dashboard](508_dashboard.yaml): paste into a dashboard's manual card
  editor. Buttons are intentionally omitted to avoid accidental commands.

The examples use Home Assistant persistent notifications. They do not send
mobile push notifications. A stable `notification_id` replaces a previous
notification for the same sensor instead of accumulating copies. Notifications
remain visible until dismissed; they do not automatically clear when the fault
ends. None of the examples silences or resets a controller.

A state trigger with `to: "on"` also alerts when a sensor recovers from
`unknown`/`unavailable` into an active fault. It does not repeat while the sensor
stays `on`, and it does not scan an already-active fault when automations are
reloaded. Check existing faults after setup. A `for:` delay resets when Home
Assistant restarts or automations reload; it is not a durable outage timer.
See [Home Assistant's trigger documentation](https://www.home-assistant.io/docs/automation/trigger/).

The fault categories are broad: use the cloud detail view to determine the
specific cause and urgency. For a broader catch-all, a `numeric_state` trigger
on your device's Alarm Count with `above: 0` detects entry into a nonzero count;
it will not alert again for an increase from one active alarm to two. Do not
assume every counted alarm is a critical water emergency.
