-- Run from the repository root against an in-memory SQLite connection.
ATTACH DATABASE 'outputs/geds-snapshot-2026-07-08/geds.sqlite' AS initial_nine;
ATTACH DATABASE 'outputs/runs/2026-07-08/a-batch/geds.sqlite' AS a_batch;
ATTACH DATABASE 'outputs/runs/2026-07-08/ised-crtc/geds.sqlite' AS ised;
ATTACH DATABASE 'outputs/runs/2026-07-08/crtc/geds.sqlite' AS crtc;
ATTACH DATABASE 'outputs/runs/2026-07-08/rest-batch/geds.sqlite' AS rest_batch;
ATTACH DATABASE 'outputs/control/control.sqlite' AS control;

WITH
selected_people AS (
    SELECT * FROM initial_nine.people_index
    UNION ALL
    SELECT * FROM a_batch.people_index
    UNION ALL
    SELECT * FROM ised.people_index
    UNION ALL
    SELECT * FROM crtc.people_index
    UNION ALL
    SELECT * FROM rest_batch.people_index
    WHERE department_dn <> 'OU=CRTC-CRTC,O=GC,C=CA'
),
selected_orgs AS (
    SELECT * FROM initial_nine.org_units
    UNION ALL
    SELECT * FROM a_batch.org_units
    UNION ALL
    SELECT * FROM ised.org_units
    UNION ALL
    SELECT * FROM crtc.org_units
    UNION ALL
    SELECT * FROM rest_batch.org_units
    WHERE department_dn <> 'OU=CRTC-CRTC,O=GC,C=CA'
),
selected_departments AS (
    SELECT dn FROM initial_nine.departments
    UNION
    SELECT dn FROM a_batch.departments
    UNION
    SELECT dn FROM ised.departments
    UNION
    SELECT dn FROM crtc.departments
    UNION
    SELECT dn FROM rest_batch.departments
    WHERE dn <> 'OU=CRTC-CRTC,O=GC,C=CA'
),
org_people AS (
    SELECT org_dn, COUNT(*) AS people
    FROM selected_people
    GROUP BY org_dn
)
SELECT
    (SELECT COUNT(*) FROM control.department_catalog) AS catalog_departments,
    (SELECT COUNT(*) FROM selected_departments) AS represented_departments,
    (SELECT COUNT(*) FROM selected_people) AS people,
    (SELECT COUNT(*) FROM selected_orgs) AS org_units,
    (
        SELECT COUNT(*)
        FROM selected_people
        WHERE title IS NULL OR TRIM(title) = ''
    ) AS missing_titles,
    (SELECT MAX(people) FROM org_people) AS maximum_people_per_org,
    (SELECT COUNT(*) FROM org_people WHERE people = 25) AS orgs_at_25_people,
    (
        SELECT COUNT(*)
        FROM selected_people AS people
        LEFT JOIN selected_orgs AS orgs ON orgs.dn = people.org_dn
        WHERE orgs.dn IS NULL
    ) AS orphan_people_org,
    (
        SELECT COUNT(*)
        FROM selected_orgs AS child
        LEFT JOIN selected_orgs AS parent ON parent.dn = child.parent_dn
        WHERE child.parent_dn IS NOT NULL AND parent.dn IS NULL
    ) AS orphan_org_parent;
