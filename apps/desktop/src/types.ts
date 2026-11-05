export interface JobItem {
  id: number;
  job_reference: string;
  logical_filing_id?: string;
  customer_id: number;
  customer_code: string;
  customer_name: string;
  pan_masked: string;
  filing_id?: number;
  amount: number;
  tds_amount?: number | null;
  status: string;
  current_step: string;
  attempt_count: number;
  worker_id?: string;
  error_code?: string;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
}

export interface JobTimelineEvent {
  id: number;
  event_type: string;
  status: string;
  message: string;
  metadata?: any;
  created_at?: string;
}

export interface JobDetail {
  id: number;
  job_reference: string;
  customer: {
    id: number;
    customer_code: string;
    name: string;
    pan_masked: string;
  };
  filing: {
    id: number;
    filing_reference: string;
    amount: number;
    tds_amount?: number | null;
    status: string;
  };
  status: string;
  current_step: string;
  attempt_count: number;
  worker_id?: string;
  error_code?: string;
  error_message?: string;
  data_payload?: any;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
  timeline: JobTimelineEvent[];
}

export interface DashboardMetrics {
  total_clients: number;
  total_jobs: number;
  ready?: number;
  queued: number;
  processing: number;
  preview_pending?: number;
  payment_pending: number;
  completed: number;
  failed: number;
  manual_intervention: number;
  cancelled: number;
  completion_percentage: number;
}

export interface ActiveJob {
  id: number;
  job_reference: string;
  customer_id: number;
  customer_name: string;
  customer_code: string;
  status: string;
  current_step: string;
  elapsed_seconds: number;
  attempt_count: number;
}

export interface SystemStatus {
  queue_state: string;
  worker_status: string;
  worker_id?: string;
  browser_status: string;
}

export interface PreviewPendingJob {
  id: number;
  job_reference: string;
  customer_id: number;
  customer_name: string;
  customer_code: string;
  pan_masked: string;
  filing_id?: number;
  filing_reference: string;
  amount: number;
  tds_amount?: number | null;
  status: string;
  current_step: string;
  elapsed_seconds: number;
  attempt_count: number;
  session_available: boolean;
  preview_metadata?: any;
  preview_reached_at?: string;
  created_at?: string;
}

export interface PaymentPendingJob {
  id: number;
  job_reference: string;
  customer_id: number;
  customer_name: string;
  customer_code: string;
  pan_masked: string;
  filing_id?: number;
  filing_reference: string;
  amount: number;
  tds_amount?: number | null;
  status: string;
  current_step: string;
  elapsed_seconds: number;
  attempt_count: number;
  session_available: boolean;
  created_at?: string;
}

export interface DashboardSummary {
  metrics: DashboardMetrics;
  active_job: ActiveJob | null;
  preview_pending_jobs?: PreviewPendingJob[];
  payment_pending_jobs?: PaymentPendingJob[];
  system: SystemStatus;
}

export interface SystemHealth {
  status: string;
  timestamp: string;
  components: {
    api: string;
    database: string;
    redis: string;
    worker: string;
    browser: string;
  };
}

export interface WebSocketEvent {
  event: string;
  job_id: string;
  status: string;
  message: string;
  timestamp: string;
  payload?: any;
}

export interface ValidationIssue {
  row: number;
  field: string;
  code: string;
  message: string;
  severity: "error" | "warning";
}

export interface ImportPreviewResponse {
  filename: string;
  columns: string[];
  total_rows: number;
  valid_count: number;
  error_count: number;
  warning_count: number;
  duplicate_count: number;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  preview: any[];
  suggested_mapping: Record<string, string>;
  is_form141?: boolean;
  customers?: Form141CustomerPreview[];
}

export interface Form141FieldMeta {
  type: string;
  sectionKey: string;
  fieldLabel: string;
  fieldKey: string;
  fetchType: string;
}

export interface Form141FieldData {
  value: string;
  fetchType: string;
  fieldLabel: string;
}

export interface Form141ExtractedField {
  type: string;
  form141_field: string;
  fetch_type: string;
  customer_index: number;
  customer_label: string;
  source_column: string;
  original_row_number: number;
  value: any;
  display_value: string;
  is_sensitive?: boolean;
}

export interface Form141CustomerPreview {
  customerIndex: number;
  customerLabel: string;
  customer_index?: number;
  customer_label?: string;
  source_column?: string;
  status: "READY" | "WARNING" | "ERROR" | "VALIDATION_REQUIRED" | "INVALID" | "QUEUED" | "PROCESSING" | "PREVIEW_PENDING" | "PAYMENT_PENDING" | "COMPLETED" | "CANCELLED" | "FAILED";
  errors: Form141ValidationIssue[];
  warnings: Form141ValidationIssue[];
  sections: Record<string, Record<string, Form141FieldData>>;
  values?: Record<string, any>;
  fields?: Form141ExtractedField[];
  jobId?: number;
  jobReference?: string;
}

export interface Form141ValidationIssue {
  customerIndex: number;
  section: string;
  field: string;
  code: string;
  message: string;
  severity: "error" | "warning";
}

export interface Form141ActiveLock {
  has_active_job: boolean;
  can_start: boolean;
  active_job?: {
    id: number;
    job_reference: string;
    customer_id: number;
    customer_name: string;
    customer_code: string;
    filing_id?: number;
    filing_reference?: string;
    status: string;
    current_step: string;
    session_available: boolean;
    updated_at?: string;
  } | null;
  reason?: string | null;
}

export interface Form141PreviewResponse {
  filename: string;
  worksheet?: string;
  totalCustomers: number;
  readyCount: number;
  warningCount: number;
  errorCount: number;
  columns: string[];
  fields: Form141FieldMeta[];
  customers: Form141CustomerPreview[];
  type_headings?: string[];
  type_field_counts?: Record<string, number>;
  diagnostics?: {
    worksheet?: string;
    total_customers?: number;
    customer_columns?: string[];
    customer_labels?: string[];
    type_headings?: string[];
    type_field_counts?: Record<string, number>;
    total_extracted_fields?: number;
  };
}


export interface Form141ConfirmResponse {
  message: string;
  jobs_created: number;
  totalCustomers: number;
  selectedCount: number;
}

export interface Form141LogicalFilingItem {
  id: number;
  import_id?: number;
  logical_filing_id: string;
  customer_label: string;
  column_index: number;
  deductor_pan?: string;
  deductee_pan?: string;
  masked_pan?: string;
  amount: number;
  tds_amount?: number | null;
  status: string;
  current_step: string;
  attempt_count?: number;
  validation_errors?: Form141ValidationIssue[];
  validation_warnings?: Form141ValidationIssue[];
  job_id?: number | null;
  job_reference?: string | null;
  latest_job_id?: number | null;
  latest_job_reference?: string | null;
  latest_job?: {
    id: number;
    job_id: string;
    status: string;
    current_step: string;
    attempts: number;
  } | null;
  session_available?: boolean;
  can_start?: boolean;
  source_file?: string;
  customer_code?: string;
  form141_id?: string;
  last_activity?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Form141ExecutionAttempt {
  id: number;
  job_reference: string;
  status: string;
  current_step: string;
  attempt_number: number;
  worker_id?: string;
  error_code?: string;
  error_message?: string;
  session_available: boolean;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Form141FilingDetail {
  id: number;
  import_id?: number;
  source_file: string;
  logical_filing_id: string;
  customer_label: string;
  column_index: number;
  deductor_pan?: string;
  deductee_pan?: string;
  masked_pan?: string;
  amount: number;
  tds_amount?: number | null;
  status: string;
  current_step: string;
  total_attempts: number;
  attempts: Form141ExecutionAttempt[];
  latest_job?: Form141ExecutionAttempt | null;
  field_values?: Record<string, any>;
  field_metadata?: Record<string, any>;
  validation_errors?: Form141ValidationIssue[];
  validation_warnings?: Form141ValidationIssue[];
  created_at?: string;
  updated_at?: string;
}

export interface Form141KpiSummary {
  total_filings: number;
  ready: number;
  in_progress: number;
  action_required: number;
  completed: number;
  failed: number;
  cancelled: number;
}

