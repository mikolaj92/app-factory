# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/app-factory issue=42 -->

Repository: `mikolaj92/app-factory`  
Issue: #42 — PlatformPaths.invite defaultuje na ślepy /admin/users/invite

## Goal

`PlatformPaths.invite` w kicie nadal defaultuje na `/admin/users/invite` (stara osobna strona). Po UM v0.5.1 formularz siedzi na liście users; POST zostaje na `/admin/users/invite`.

## Files likely touched

- `PlatformPaths.invite`

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
