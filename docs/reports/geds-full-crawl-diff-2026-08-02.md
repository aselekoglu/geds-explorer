# GEDS full crawl diff report

Generated: 2026-08-03T13:47:11.601405+00:00

## Result

Partial canonical snapshot was written locally. Neon activation was not completed because the Neon project rejected staging at its 512 MB project-size limit; the existing active pointer was preserved.

```json
{
  "canonical": {
    "backup": "outputs/automation/master-before-partial-20260803T133430Z/geds-master.sqlite",
    "current": {
      "as_of_at": "2026-08-03T13:04:24.683359+00:00",
      "cycle_count": 0,
      "departments_count": 156,
      "fallback_org_count": 2,
      "missing_parent_count": 0,
      "org_units_count": 27491,
      "parent_snapshot_id": "edd5d0f4269da97163b33a5cf7dd8c850ad51331a913721e0ce7a07e1977fce5",
      "people_count": 201469,
      "quality_status": "partial_overlay",
      "quality_warnings_json": "[\"crawl_error:OU=107149-107149,OU=101588-101588,OU=100981-100981,OU=100832-100832,OU=103642-103642,OU=ESDC-EDSC,O=GC,C=CA\",\"crawl_error:OU=107151-107151,OU=101588-101588,OU=100981-100981,OU=100832-100832,OU=103642-103642,OU=ESDC-EDSC,O=GC,C=CA\"]",
      "snapshot_id": "cbcd6b63facc3b6eb7e344a81c899ea22531cfca5417eb52d8eb4bfdf7712d38"
    },
    "current_warning_json": [
      "crawl_error:OU=107149-107149,OU=101588-101588,OU=100981-100981,OU=100832-100832,OU=103642-103642,OU=ESDC-EDSC,O=GC,C=CA",
      "crawl_error:OU=107151-107151,OU=101588-101588,OU=100981-100981,OU=100832-100832,OU=103642-103642,OU=ESDC-EDSC,O=GC,C=CA"
    ],
    "event_counts": {
      "organization:org_missing_candidate:uncertain": 1531,
      "organization:org_opened:certain": 1070,
      "organization:org_renamed:certain": 56,
      "organization:org_reparented:certain": 6269,
      "person:joined:certain": 13776,
      "person:missing_candidate:uncertain": 12895,
      "person:name_changed:certain": 20,
      "person:role_changed:certain": 1240
    },
    "identity": {
      "absence_policy": "partial scopes create uncertain missing_candidate events; no confirmed departure",
      "primary": "source_url",
      "role_event": "role_changed",
      "role_event_payload": "before.title -> after.title",
      "secondary": "normalized_name"
    },
    "previous": {
      "as_of_at": "2026-07-09T07:05:04.674049+00:00",
      "departments_count": 156,
      "org_units_count": 26421,
      "people_count": 193163,
      "snapshot_id": "edd5d0f4269da97163b33a5cf7dd8c850ad51331a913721e0ce7a07e1977fce5"
    }
  },
  "crawl": {
    "crawl_errors": 3,
    "cycle_error_dns": [
      "OU=107149-107149,OU=101588-101588,OU=100981-100981,OU=100832-100832,OU=103642-103642,OU=ESDC-EDSC,O=GC,C=CA",
      "OU=107151-107151,OU=101588-101588,OU=100981-100981,OU=100832-100832,OU=103642-103642,OU=ESDC-EDSC,O=GC,C=CA"
    ],
    "finished_at": "2026-08-03T13:04:24.683359+00:00",
    "queue": {
      "done": 25958,
      "error": 2
    },
    "raw_counts": {
      "departments": 156,
      "organizations": 25960,
      "people": 194044
    },
    "run_id": "5ef92383-217d-4527-a232-fc55d13351bb",
    "size_bytes": 456985756,
    "size_mb": 435.82,
    "status": "finished"
  },
  "generated_at": "2026-08-03T13:47:11.601405+00:00",
  "neon": {
    "activated": false,
    "active_pointer_unchanged": true,
    "reason": "project size limit (512 MB) exceeded during stage import"
  },
  "projection": "outputs/automation/public-partial-cbcd6b63facc3b6eb7e344a81c899ea22531cfca5417eb52d8eb4bfdf7712d38-v2"
}
```
