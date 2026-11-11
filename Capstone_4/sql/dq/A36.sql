-- A36 | Hierarchy: entity_id is not numeric (mixed key types)
SELECT
    CAST(NULL AS VARCHAR) AS yr,
    t._row_num AS row_num,
    coalesce(NOT regexp_matches(t.entity_id, '^[0-9]+$'), FALSE) AS failed,
    coalesce(t.entity_id IS NOT NULL, FALSE) AS in_scope
FROM Hierarchy AS t
