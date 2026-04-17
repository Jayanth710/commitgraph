WITH ranked_pending AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY commitment_id, status
            ORDER BY created_at ASC, id ASC
        ) AS row_num
    FROM review_queue
    WHERE status = 'pending'
)
DELETE FROM review_queue
WHERE id IN (
    SELECT id
    FROM ranked_pending
    WHERE row_num > 1
);
