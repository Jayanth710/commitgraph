DELETE FROM evidence_links e
USING evidence_links source
WHERE e.commitment_id = source.commitment_id
  AND e.normalized_item_id = source.normalized_item_id
  AND source.evidence_type = 'origin'
  AND e.evidence_type IN ('update', 'follow_up');
