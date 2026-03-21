export type CommitmentStatus =
  | "detected"
  | "confirmed"
  | "in_progress"
  | "completed"
  | "overdue"
  | "abandoned"
  | "delegated";

export type CommitmentDirection = "outbound" | "inbound";

export type Commitment = {
  id: string;
  summary: string;
  raw_text?: string;
  direction: CommitmentDirection;
  status: CommitmentStatus;
  commitment_type?: string | null;
  confidence_score: number;
  due_date?: string | null;
  due_date_confidence?: number | null;
  created_at?: string;
  updated_at?: string;
  completed_at?: string | null;
  detected_at?: string;
  calendar_event_id?: string | null;
  owner_name?: string | null;
  owner_email?: string | null;
  owner_is_self?: boolean;
  target_name?: string | null;
  target_email?: string | null;
};

export type EvidenceItem = {
  id: string;
  evidence_type: string;
  extracted_snippet?: string | null;
  linked_at?: string;
  subject?: string | null;
  sender_email?: string | null;
  sender_name?: string | null;
  item_type?: string | null;
  sent_at?: string | null;
  received_at?: string | null;
  event_start?: string | null;
  event_end?: string | null;
  body_text?: string | null;
  recipients?: Array<{ email: string; name?: string | null; type?: string }>;
};

export type CommitmentListResponse = {
  commitments: Commitment[];
  total: number;
  limit: number;
  offset: number;
};

export type CommitmentDetailResponse = {
  commitment: Commitment;
  evidence: EvidenceItem[];
};

export type ReviewItem = {
  id: string;
  reason: string;
  suggested_action?: string | null;
  review_status?: string;
  review_created_at?: string;
  commitment_id: string;
  summary: string;
  raw_text: string;
  direction: CommitmentDirection;
  confidence_score: number;
  due_date?: string | null;
  commitment_type?: string | null;
  owner_email?: string | null;
  target_email?: string | null;
  source_subject?: string | null;
  source_sender?: string | null;
  source_body?: string | null;
};

export type ReviewQueueResponse = {
  review_items: ReviewItem[];
  total: number;
};