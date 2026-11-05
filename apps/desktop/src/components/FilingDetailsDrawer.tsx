import React, { useEffect, useState } from 'react';
import {
  X,
  FileSpreadsheet,
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  ExternalLink,
  ShieldAlert,
  Play,
  Lock,
  ChevronRight,
  Building,
  CreditCard,
  History
} from 'lucide-react';
import type { Form141FilingDetail, Form141ActiveLock } from '../types';
import { apiFetch } from '../services/api';

interface FilingDetailsDrawerProps {
  filingIdentifier: string | number | null;
  isOpen: boolean;
  onClose: () => void;
  activeLock: Form141ActiveLock | null;
  onStartFiling: (id: string | number) => void;
  onOpenSession?: (jobId: number) => void;
  onViewJob?: (jobId: number) => void;
}

export const FilingDetailsDrawer: React.FC<FilingDetailsDrawerProps> = ({
  filingIdentifier,
  isOpen,
  onClose,
  activeLock,
  onStartFiling,
  onOpenSession,
  onViewJob
}) => {
  const [detail, setDetail] = useState<Form141FilingDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !filingIdentifier) {
      setDetail(null);
      return;
    }

    let isCancelled = false;
    setLoading(true);
    setError(null);

    apiFetch(`/api/form141/filings/${filingIdentifier}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load filing details`);
        return res.json();
      })
      .then((data) => {
        if (!isCancelled) {
          setDetail(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [isOpen, filingIdentifier]);

  if (!isOpen) return null;

  const hasActiveJob = Boolean(activeLock?.has_active_job);
  const statusUpper = (detail?.status || 'READY').toUpperCase();
  const isInvalid = statusUpper === 'INVALID';
  const isRetryable = ['FAILED', 'CANCELLED', 'SESSION_LOST'].includes(statusUpper);
  const canStart = !hasActiveJob && !isInvalid && (statusUpper === 'READY' || isRetryable);

  const getStatusBadge = (st: string) => {
    switch (st.toUpperCase()) {
      case 'READY':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> READY
          </span>
        );
      case 'QUEUED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300">
            <Clock className="w-3 h-3 text-blue-600" /> QUEUED
          </span>
        );
      case 'PROCESSING':
      case 'IN_PROGRESS':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300 animate-pulse">
            <Clock className="w-3 h-3 text-blue-600 animate-spin" /> IN PROGRESS
          </span>
        );
      case 'PREVIEW_PENDING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            <AlertTriangle className="w-3 h-3 text-amber-600" /> PREVIEW PENDING
          </span>
        );
      case 'PAYMENT_PENDING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 border border-purple-300">
            <ShieldAlert className="w-3 h-3 text-purple-600" /> PAYMENT PENDING
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> COMPLETED
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            <XCircle className="w-3 h-3 text-rose-600" /> FAILED
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-200 text-slate-700 border border-slate-300">
            <XCircle className="w-3 h-3 text-slate-500" /> CANCELLED
          </span>
        );
      case 'SESSION_LOST':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange-100 text-orange-800 border border-orange-300">
            <AlertTriangle className="w-3 h-3 text-orange-600" /> SESSION LOST
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
            {st}
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-xs flex justify-end">
      <div className="w-full max-w-xl bg-white shadow-2xl h-full flex flex-col border-l border-slate-200">
        {/* Drawer Header */}
        <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600 text-white rounded-lg shadow-sm">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <span>{detail?.customer_label || 'Filing Details'}</span>
                {detail?.logical_filing_id && (
                  <span className="font-mono text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded font-semibold border border-blue-200">
                    {detail.logical_filing_id}
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Source: {detail?.source_file || 'Form 141 Workbook'} &bull; Column #{detail?.column_index || 1}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded-lg transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {loading && (
            <div className="py-16 text-center text-slate-400 text-xs">
              <Clock className="w-8 h-8 animate-spin mx-auto mb-2 text-blue-500" />
              Loading filing information...
            </div>
          )}

          {error && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
              <XCircle className="w-5 h-5 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {detail && !loading && (
            <>
              {/* Top Status Card */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 flex items-center justify-between">
                <div>
                  <div className="text-[11px] uppercase font-bold text-slate-400 mb-1">Current Status</div>
                  <div>{getStatusBadge(detail.status)}</div>
                </div>
                <div className="text-right">
                  <div className="text-[11px] uppercase font-bold text-slate-400 mb-1">Execution Attempts</div>
                  <div className="text-sm font-bold text-slate-800 font-mono">
                    {detail.total_attempts} {detail.total_attempts === 1 ? 'Attempt' : 'Attempts'}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                {canStart && (
                  <button
                    onClick={() => {
                      onStartFiling(detail.logical_filing_id);
                      onClose();
                    }}
                    className="flex-1 inline-flex items-center justify-center gap-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-bold text-xs shadow-sm transition cursor-pointer"
                  >
                    <Play className="w-4 h-4 fill-current" />
                    <span>{isRetryable ? 'Retry Filing Automation' : 'Start Filing Automation'}</span>
                  </button>
                )}

                {hasActiveJob && (
                  <div className="flex-1 py-2 px-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-xs flex items-center gap-2">
                    <Lock className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>Another filing is currently active. Concurrency locked (1 max).</span>
                  </div>
                )}

                {detail.latest_job && detail.latest_job.session_available && onOpenSession && (
                  <button
                    onClick={() => onOpenSession(detail.latest_job!.id)}
                    className="inline-flex items-center gap-1.5 py-2.5 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-bold text-xs shadow-sm transition cursor-pointer"
                  >
                    <ExternalLink className="w-4 h-4" />
                    <span>Open Live Browser</span>
                  </button>
                )}
              </div>

              {/* Filing Details Section */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <Building className="w-4 h-4 text-blue-600" />
                  Filing Information
                </h3>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">Deductor PAN</span>
                    <span className="font-mono font-bold text-slate-800 text-sm">
                      {detail.deductor_pan || 'N/A'}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">Deductee PAN</span>
                    <span className="font-mono font-bold text-slate-800 text-sm">
                      {detail.deductee_pan || 'N/A'}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">Transaction Amount</span>
                    <span className="font-bold text-slate-800 text-sm">
                      {detail.amount ? `₹${Number(detail.amount).toLocaleString('en-IN')}` : '₹0'}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">TDS Amount</span>
                    <span className="font-bold text-slate-800 text-sm">
                      {detail.tds_amount !== null && detail.tds_amount !== undefined
                        ? `₹${Number(detail.tds_amount).toLocaleString('en-IN')}`
                        : <span className="text-slate-400 font-normal">Pending</span>}
                    </span>
                  </div>
                </div>
              </div>

              {/* Latest Execution Details */}
              {detail.latest_job && (
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                    <CreditCard className="w-4 h-4 text-indigo-600" />
                    Latest Execution
                  </h3>
                  <div className="p-3.5 rounded-xl border border-indigo-200 bg-indigo-50/30 space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900 font-mono">
                        {detail.latest_job.job_reference}
                      </span>
                      {getStatusBadge(detail.latest_job.status)}
                    </div>
                    <div className="text-slate-600 flex items-center justify-between text-[11px]">
                      <span>Current Step: <strong className="text-slate-800">{detail.latest_job.current_step}</strong></span>
                      {detail.latest_job.worker_id && (
                        <span>Worker: <strong className="font-mono">{detail.latest_job.worker_id}</strong></span>
                      )}
                    </div>
                    {detail.latest_job.error_message && (
                      <div className="mt-2 p-2 bg-rose-50 border border-rose-200 text-rose-800 rounded text-[11px]">
                        <strong>Error:</strong> {detail.latest_job.error_message}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Attempt Timeline */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <History className="w-4 h-4 text-slate-600" />
                  Execution Attempt History ({detail.attempts.length})
                </h3>

                {detail.attempts.length === 0 ? (
                  <div className="p-4 text-center text-slate-400 text-xs bg-slate-50 rounded-lg border border-dashed border-slate-200">
                    No execution jobs started yet. Click &ldquo;Start Filing Automation&rdquo; to create Attempt #1.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {detail.attempts.map((att) => (
                      <div
                        key={att.id}
                        className="p-3 rounded-lg border border-slate-200 bg-white hover:bg-slate-50/80 transition flex items-center justify-between text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-800 font-mono">{att.job_reference}</span>
                            <span className="text-[10px] px-1.5 py-0.2 bg-slate-100 text-slate-600 rounded font-semibold">
                              Attempt #{att.attempt_number}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-500">
                            Step: {att.current_step} &bull; Started: {att.started_at ? new Date(att.started_at).toLocaleTimeString() : (att.created_at ? new Date(att.created_at).toLocaleTimeString() : 'N/A')}
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {getStatusBadge(att.status)}
                          {att.session_available && onOpenSession && (
                            <button
                              onClick={() => onOpenSession(att.id)}
                              className="p-1 text-blue-600 hover:bg-blue-100 rounded cursor-pointer"
                              title="Attach live browser"
                            >
                              <ExternalLink className="w-3.5 h-3.5" />
                            </button>
                          )}
                          {onViewJob && (
                            <button
                              onClick={() => {
                                onViewJob(att.id);
                                onClose();
                              }}
                              className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded cursor-pointer"
                              title="View full job modal"
                            >
                              <ChevronRight className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
