WITH ranked_duplicates AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY
                commitment_id,
                normalized_item_id,
                evidence_type,
                COALESCE(extracted_snippet, '')
            ORDER BY linked_at ASC, id ASC
        ) AS row_num
    FROM evidence_links
)
DELETE FROM evidence_links
WHERE id IN (
    SELECT id
    FROM ranked_duplicates
    WHERE row_num > 1
);

DELETE FROM evidence_links e
USING evidence_links source
WHERE e.commitment_id = source.commitment_id
  AND e.normalized_item_id = source.normalized_item_id
  AND COALESCE(e.extracted_snippet, '') = COALESCE(source.extracted_snippet, '')
  AND source.evidence_type = 'origin'
  AND e.evidence_type IN ('update', 'follow_up');
