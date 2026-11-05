import React from 'react';
import { Play, CheckCircle2, AlertTriangle, XCircle, Clock, ExternalLink, ShieldAlert, FileSpreadsheet, Lock, RotateCw, Eye, Trash2 } from 'lucide-react';
import type { Form141LogicalFilingItem, Form141ActiveLock } from '../types';

interface Form141FilingsTableProps {
  filings: Form141LogicalFilingItem[];
  activeLock: Form141ActiveLock | null;
  onStartFiling: (filingId: string | number) => void;
  onOpenSession?: (jobId: number) => void;
  onViewJob?: (jobId: number) => void;
  onViewFilingDrawer?: (logicalId: string) => void;
  onDeleteFiling?: (logicalId: string) => void;
}

export const Form141FilingsTable: React.FC<Form141FilingsTableProps> = ({
  filings,
  activeLock,
  onStartFiling,
  onOpenSession,
  onViewJob,
  onViewFilingDrawer,
  onDeleteFiling
}) => {
  const getStatusBadge = (status: string) => {
    switch ((status || 'READY').toUpperCase()) {
      case 'READY':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            READY
          </span>
        );
      case 'QUEUED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300">
            <Clock className="w-3 h-3 text-blue-600" />
            QUEUED
          </span>
        );
      case 'PROCESSING':
      case 'IN_PROGRESS':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300 animate-pulse">
            <Clock className="w-3 h-3 text-blue-600 animate-spin" />
            IN PROGRESS
          </span>
        );
      case 'SAVE_AS_DRAFT_PENDING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 border border-indigo-300">
            <Clock className="w-3 h-3 text-indigo-600" />
            SAVING DRAFT
          </span>
        );
      case 'DRAFT_SAVED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-100 text-cyan-800 border border-cyan-300">
            <CheckCircle2 className="w-3 h-3 text-cyan-600" />
            DRAFT SAVED
          </span>
        );
      case 'PREVIEW_PENDING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            PREVIEW PENDING
          </span>
        );
      case 'PAYMENT_PENDING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 border border-purple-300">
            <ShieldAlert className="w-3 h-3 text-purple-600" />
            PAYMENT PENDING
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            COMPLETED
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            <XCircle className="w-3 h-3 text-rose-600" />
            FAILED
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-200 text-slate-700 border border-slate-300">
            <XCircle className="w-3 h-3 text-slate-500" />
            CANCELLED
          </span>
        );
      case 'SESSION_LOST':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange-100 text-orange-800 border border-orange-300">
            <AlertTriangle className="w-3 h-3 text-orange-600" />
            SESSION LOST
          </span>
        );
      case 'VALIDATION_REQUIRED':
      case 'WARNING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            VALIDATION REQUIRED
          </span>
        );
      case 'INVALID':
      case 'ERROR':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            <XCircle className="w-3 h-3 text-rose-600" />
            INVALID
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  const hasActiveJob = Boolean(activeLock?.has_active_job);
  const activeJobRef = activeLock?.active_job?.job_reference;
  const activeJobCust = activeLock?.active_job?.customer_name;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header Banner */}
      <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/70 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 p-2 rounded-lg text-white shadow-sm">
            <FileSpreadsheet className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
              IMPORTED FILINGS
              <span className="bg-blue-100 text-blue-800 text-xs px-2.5 py-0.5 rounded-full font-semibold border border-blue-200">
                {filings.length} {filings.length === 1 ? 'Customer' : 'Customers'}
              </span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
            </p>
          </div>
        </div>

        {/* Strict Single-Filing Concurrency Lock Badge */}
        {hasActiveJob ? (
          <div className="flex items-center gap-2 bg-amber-50 border border-amber-300 text-amber-900 px-3.5 py-1.5 rounded-lg text-xs font-medium shadow-sm">
            <Lock className="w-4 h-4 text-amber-600 shrink-0" />
            <div>
              <span className="font-bold">Active Filing in Progress:</span>{' '}
              <span className="text-amber-800">{activeJobCust} ({activeJobRef})</span>
              <div className="text-[11px] text-amber-700">
                Strict single-filing concurrency (MAX_ACTIVE_FORM141_JOBS = 1) is active.
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-300 text-emerald-900 px-3 py-1.5 rounded-lg text-xs font-medium shadow-sm">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>Single-Filing Lock Ready &bull; Select a filing to start</span>
          </div>
        )}
      </div>

      {/* Table Body */}
      {filings.length === 0 ? (
        <div className="py-12 px-6 text-center text-slate-500">
          <FileSpreadsheet className="w-12 h-12 mx-auto text-slate-300 mb-3" />
          <p className="text-sm font-medium text-slate-700">No Form 141 filings imported yet</p>
          <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
            Click &ldquo;Import Filings&rdquo; in the header above to upload a Form 141 multi-customer Excel workbook.
            Imported customer columns will appear here permanently.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-100/70 text-slate-600 font-bold uppercase tracking-wider text-[11px]">
                <th className="py-3 px-4">Customer / Filing</th>
                <th className="py-3 px-3">Logical ID</th>
                <th className="py-3 px-3">PANs (Deductor &rarr; Deductee)</th>
                <th className="py-3 px-3 text-right">Amount</th>
                <th className="py-3 px-3 text-right">TDS</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3">Latest Job</th>
                <th className="py-3 px-3">Current Step</th>
                <th className="py-3 px-3 text-center">Attempts</th>
                <th className="py-3 px-3">Browser Session</th>
                <th className="py-3 px-4 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 text-slate-700">
              {filings.map((filing) => {
                const statusUpper = (filing.status || 'READY').toUpperCase();
                const isCompleted = statusUpper === 'COMPLETED';
                const isInvalid = statusUpper === 'INVALID';
                const isRetryable = ['FAILED', 'CANCELLED', 'SESSION_LOST'].includes(statusUpper);
                const isCurrentlyRunning = ['QUEUED', 'PROCESSING', 'IN_PROGRESS', 'SAVE_AS_DRAFT_PENDING', 'DRAFT_SAVED'].includes(statusUpper);
                const isPreviewWaiting = statusUpper === 'PREVIEW_PENDING';
                const isPaymentWaiting = statusUpper === 'PAYMENT_PENDING';
                const canStart = !hasActiveJob && !isInvalid && (statusUpper === 'READY' || isRetryable);
                const attemptsCount = filing.attempt_count ?? (filing.job_id ? 1 : 0);
                const effectiveJobId = filing.latest_job_id ?? filing.job_id;
                const effectiveJobRef = filing.latest_job_reference ?? filing.job_reference;

                return (
                  <tr
                    key={filing.id}
                    className={`hover:bg-slate-50/80 transition-colors ${isCurrentlyRunning ? 'bg-blue-50/40' : ''
                      }`}
                  >
                    {/* Customer Label */}
                    <td className="py-3 px-4">
                      <button
                        onClick={() => onViewFilingDrawer && onViewFilingDrawer(filing.logical_filing_id)}
                        className="text-left font-bold text-slate-900 text-sm hover:text-blue-600 transition cursor-pointer"
                        title="Click to view filing details & attempt history"
                      >
                        {filing.customer_label}
                      </button>
                      <div className="text-[11px] text-slate-500">Column {filing.column_index}</div>
                    </td>

                    {/* Logical Filing ID */}
                    <td className="py-3 px-3">
                      <button
                        onClick={() => onViewFilingDrawer && onViewFilingDrawer(filing.logical_filing_id)}
                        className="font-mono text-slate-800 bg-slate-100 hover:bg-blue-50 hover:text-blue-700 px-2 py-0.5 rounded border border-slate-200 font-semibold cursor-pointer transition text-xs"
                        title="Click to view filing details & attempt history"
                      >
                        {filing.logical_filing_id}
                      </button>
                    </td>

                    {/* PANs */}
                    <td className="py-3 px-3 font-mono text-[11px] text-slate-600">
                      <div><span className="text-slate-400">Dr:</span> {filing.masked_pan || filing.deductor_pan || 'N/A'}</div>
                      <div><span className="text-slate-400">De:</span> {filing.deductee_pan || 'N/A'}</div>
                    </td>

                    {/* Amount */}
                    <td className="py-3 px-3 text-right font-medium text-slate-800">
                      {filing.amount ? `₹${Number(filing.amount).toLocaleString('en-IN')}` : '₹0'}
                    </td>

                    {/* TDS Amount */}
                    <td className="py-3 px-3 text-right font-medium text-slate-800">
                      {filing.tds_amount !== null && filing.tds_amount !== undefined
                        ? `₹${Number(filing.tds_amount).toLocaleString('en-IN')}`
                        : <span className="text-slate-400">Pending</span>}
                    </td>

                    {/* Status Badge */}
                    <td className="py-3 px-3">
                      {getStatusBadge(filing.status)}
                    </td>

                    {/* Latest Job */}
                    <td className="py-3 px-3">
                      {effectiveJobId ? (
                        <button
                          onClick={() => onViewJob && effectiveJobId && onViewJob(effectiveJobId)}
                          className="font-mono text-blue-600 hover:text-blue-800 underline flex items-center gap-1 cursor-pointer"
                          title="View Job Details in Job History"
                        >
                          {effectiveJobRef || `JOB-#${effectiveJobId}`}
                        </button>
                      ) : (
                        <span className="text-slate-400 italic">No job yet</span>
                      )}
                    </td>

                    {/* Current Step */}
                    <td className="py-3 px-3">
                      <span className="text-slate-600 font-medium text-[11px] max-w-[140px] truncate block" title={filing.current_step}>
                        {filing.current_step || 'NOT STARTED'}
                      </span>
                    </td>

                    {/* Attempts Count */}
                    <td className="py-3 px-3 text-center font-mono font-semibold text-slate-700">
                      {attemptsCount}
                    </td>

                    {/* Browser Session */}
                    <td className="py-3 px-3">
                      {filing.session_available && effectiveJobId ? (
                        <button
                          onClick={() => onOpenSession && effectiveJobId && onOpenSession(effectiveJobId)}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 font-semibold transition cursor-pointer"
                          title="Attach to live browser session"
                        >
                          <ExternalLink className="w-3 h-3" />
                          <span>Session Active</span>
                        </button>
                      ) : (
                        <span className="text-slate-400 text-[11px]">None</span>
                      )}
                    </td>

                    {/* Action Column */}
                    <td className="py-3 px-4 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        {isCompleted ? (
                          <button
                            onClick={() => {
                              if (onViewFilingDrawer) onViewFilingDrawer(filing.logical_filing_id);
                              else if (effectiveJobId && onViewJob) onViewJob(effectiveJobId);
                            }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium border border-slate-300 transition cursor-pointer text-xs"
                            title="View filing details and attempt history"
                          >
                            <Eye className="w-3.5 h-3.5 text-slate-500" />
                            <span>View Details</span>
                          </button>
                        ) : isCurrentlyRunning ? (
                          <div className="flex items-center justify-center gap-1.5">
                            <span className="inline-flex items-center gap-1 text-blue-700 font-semibold text-xs animate-pulse">
                              <Clock className="w-3.5 h-3.5 animate-spin" />
                              Running
                            </span>
                            {filing.session_available && effectiveJobId && (
                              <button
                                onClick={() => onOpenSession && onOpenSession(effectiveJobId)}
                                className="p-1 text-blue-600 hover:bg-blue-100 rounded"
                                title="Open browser session"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        ) : isPreviewWaiting ? (
                          <button
                            onClick={() => effectiveJobId && onOpenSession && onOpenSession(effectiveJobId)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-bold shadow-sm transition cursor-pointer text-xs"
                            title="Review Form 141 draft preview"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span>Review Preview</span>
                          </button>
                        ) : isPaymentWaiting ? (
                          <button
                            onClick={() => effectiveJobId && onOpenSession && onOpenSession(effectiveJobId)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-bold shadow-sm transition cursor-pointer text-xs"
                            title="Proceed to Payment gateway"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span>Make Payment</span>
                          </button>
                        ) : isRetryable ? (
                          <div className="relative group inline-block">
                            <button
                              onClick={() => onStartFiling(filing.logical_filing_id)}
                              disabled={hasActiveJob}
                              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-bold text-xs shadow-sm transition ${hasActiveJob
                                ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                                : 'bg-amber-600 hover:bg-amber-500 text-white cursor-pointer active:scale-95'
                                }`}
                              title={`Retry filing for ${filing.customer_label}`}
                            >
                              <RotateCw className="w-3.5 h-3.5" />
                              <span>Retry Filing</span>
                            </button>
                            {hasActiveJob && (
                              <div className="absolute right-0 bottom-full mb-2 hidden group-hover:block z-20 w-60 p-2 bg-slate-900 text-white text-[11px] rounded shadow-lg text-left">
                                Cannot retry: Another filing is currently active ({activeJobCust || activeJobRef}). Only one Form 141 filing can run at a time.
                              </div>
                            )}
                          </div>
                        ) : canStart ? (
                          <button
                            onClick={() => onStartFiling(filing.logical_filing_id)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-bold shadow-sm transition transform active:scale-95 cursor-pointer text-xs"
                            title={`Start Form 141 filing for ${filing.customer_label}`}
                          >
                            <Play className="w-3.5 h-3.5 fill-current" />
                            <span>Start Filing</span>
                          </button>
                        ) : (
                          <div className="relative group inline-block">
                            <button
                              disabled
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-200 text-slate-400 rounded-lg font-bold text-xs cursor-not-allowed"
                            >
                              <Lock className="w-3.5 h-3.5" />
                              <span>Start Filing</span>
                            </button>
                            {hasActiveJob && (
                              <div className="absolute right-0 bottom-full mb-2 hidden group-hover:block z-20 w-60 p-2 bg-slate-900 text-white text-[11px] rounded shadow-lg text-left">
                                Another filing is currently active ({activeJobCust || activeJobRef}). Only one Form 141 filing can run at a time.
                              </div>
                            )}
                            {isInvalid && (
                              <div className="absolute right-0 bottom-full mb-2 hidden group-hover:block z-20 w-60 p-2 bg-rose-900 text-white text-[11px] rounded shadow-lg text-left">
                                This filing has validation errors that must be corrected before starting.
                              </div>
                            )}
                          </div>
                        )}

                        {/* Compact Delete Filing Icon Button */}
                        {onDeleteFiling && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (window.confirm(`Are you sure you want to delete filing ${filing.logical_filing_id}?`)) {
                                onDeleteFiling(filing.logical_filing_id);
                              }
                            }}
                            disabled={isCurrentlyRunning}
                            title={isCurrentlyRunning ? "Cannot delete active/running filing" : "Delete filing"}
                            aria-label={`Delete filing ${filing.logical_filing_id}`}
                            className={`p-1.5 rounded-lg transition text-slate-400 hover:text-rose-600 hover:bg-rose-50 ${isCurrentlyRunning ? 'opacity-30 cursor-not-allowed hover:text-slate-400 hover:bg-transparent' : 'cursor-pointer'}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
