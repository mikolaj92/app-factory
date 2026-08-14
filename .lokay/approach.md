# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/app-factory issue=44 -->

Repository: `mikolaj92/app-factory`  
Issue: #44 — plist storybook zahardkodowany na mini-m4-1

## Goal

README: launchd unit `gui/$(id -u)/dev.app-factory.storybook`.
`example/dev.app-factory.storybook.plist` ma WorkingDirectory / cd / logi = `/Users/mini-m4-1/Developer/app-factory`. Na innym hoście unit nie wstaje.

## Files likely touched

- `example/dev.app-factory.storybook.plist`

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
