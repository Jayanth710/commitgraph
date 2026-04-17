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
