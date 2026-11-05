import React from 'react';
import type { JobItem } from '../types';
import { Search, Eye, RotateCw, Ban, ChevronLeft, ChevronRight, ExternalLink, Check, Play, Lock, Trash2 } from 'lucide-react';

interface JobTableProps {
  jobs: JobItem[];
  total: number;
  page: number;
  limit: number;
  search: string;
  statusFilter?: string;
  hasActiveJob?: boolean;
  onSearchChange: (val: string) => void;
  onStatusFilterChange?: (status: string) => void;
  onPageChange: (page: number) => void;
  onViewJob: (jobId: number) => void;
  onStartJob?: (jobId: number) => Promise<void>;
  onRetryJob: (jobId: number) => Promise<void>;
  onCancelJob: (jobId: number) => Promise<void>;
  onOpenSession?: (jobId: number) => Promise<void>;
  onConfirmPayment?: (jobId: number) => Promise<void>;
  onDeleteJob?: (jobId: number) => Promise<void> | void;
}

export const JobTable: React.FC<JobTableProps> = ({
  jobs,
  total,
  page,
  limit,
  search,
  statusFilter: _statusFilter,
  hasActiveJob = false,
  onSearchChange,
  onStatusFilterChange: _onStatusFilterChange,
  onPageChange,
  onViewJob,
  onStartJob,
  onRetryJob,
  onCancelJob,
  onOpenSession,
  onConfirmPayment,
  onDeleteJob
}) => {
  const totalPages = Math.max(1, Math.ceil(total / limit));

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'READY':
        return <span className="bg-emerald-50 text-emerald-800 border border-emerald-300 px-2 py-0.5 rounded text-[11px] font-bold tracking-wide">READY</span>;
      case 'VALIDATION_REQUIRED':
        return <span className="bg-amber-50 text-amber-800 border border-amber-300 px-2 py-0.5 rounded text-[11px] font-bold">WARNING</span>;
      case 'QUEUED':
        return <span className="bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded text-[11px] font-bold">QUEUED</span>;
      case 'PROCESSING':
        return <span className="bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded text-[11px] font-bold animate-pulse">PROCESSING</span>;
      case 'PREVIEW_PENDING':
        return <span className="bg-purple-100 text-purple-900 border border-purple-300 px-2 py-0.5 rounded text-[11px] font-extrabold animate-pulse">PREVIEW PENDING</span>;
      case 'PAYMENT_PENDING':
        return <span className="bg-amber-100 text-amber-900 border border-amber-300 px-2 py-0.5 rounded text-[11px] font-extrabold animate-pulse">PAYMENT PENDING</span>;
      case 'COMPLETED':
        return <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded text-[11px] font-bold">COMPLETED</span>;
      case 'FAILED':
        return <span className="bg-rose-50 text-rose-700 border border-rose-200 px-2 py-0.5 rounded text-[11px] font-bold">FAILED</span>;
      case 'MANUAL_INTERVENTION':
        return <span className="bg-purple-50 text-purple-700 border border-purple-200 px-2 py-0.5 rounded text-[11px] font-bold">INTERVENTION</span>;
      case 'SESSION_LOST':
        return <span className="bg-slate-200 text-slate-700 border border-slate-300 px-2 py-0.5 rounded text-[11px] font-semibold">SESSION LOST</span>;
      case 'CANCELLED':
        return <span className="bg-slate-100 text-slate-600 border border-slate-300 px-2 py-0.5 rounded text-[11px] font-medium">CANCELLED</span>;
      default:
        return <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-[11px] font-medium">{status}</span>;
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col">
      {/* Table Toolbar */}
      <div className="p-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-1 max-w-sm">
          <div className="relative w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by customer, PAN, or job ID..."
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition"
            />
          </div>
        </div>

        <div className="text-xs text-slate-500 font-medium">
          Showing {jobs.length} of {total} records
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-600">
          <thead className="bg-slate-50 border-b border-slate-200 font-semibold text-slate-700 uppercase tracking-wider text-[11px]">
            <tr>
              <th className="py-3 px-4">Job ID</th>
              <th className="py-3 px-3">Logical Filing ID</th>
              <th className="py-3 px-4">Client / PAN</th>
              <th className="py-3 px-4">Amount / TDS</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Current Step</th>
              <th className="py-3 px-4 text-center">Attempts</th>
              <th className="py-3 px-4">Created</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-12 text-center text-slate-400">
                  No filing jobs match the current filters.
                </td>
              </tr>
            ) : (
              jobs.map((job, idx) => {
                const rowIndex = (page - 1) * limit + idx + 1;
                const canStartJob = ['READY', 'VALIDATION_REQUIRED', 'QUEUED', 'FAILED', 'CANCELLED'].includes(job.status);
                const isStartDisabled = hasActiveJob || !canStartJob;

                return (
                  <tr key={job.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center justify-center px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-blue-100 text-blue-800 border border-blue-200 shrink-0">
                          Job {rowIndex}
                        </span>
                        <span className="font-mono font-bold text-slate-900 text-xs truncate max-w-[140px]" title={job.job_reference}>
                          {job.job_reference}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      {job.logical_filing_id ? (
                        <span className="font-mono text-slate-800 bg-slate-100 px-2 py-0.5 rounded border border-slate-200 font-semibold text-[11px]">
                          {job.logical_filing_id}
                        </span>
                      ) : (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-800">{job.customer_name}</div>
                      <div className="text-[11px] font-mono text-slate-400 flex items-center gap-1.5 mt-0.5">
                        <span>{job.customer_code}</span>
                        <span>•</span>
                        <span className="text-slate-600 font-medium">{job.pan_masked}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-800">₹{job.amount.toLocaleString()}</div>
                      <div className="text-[11px] text-slate-500">
                        TDS:{' '}
                        {(() => {
                          if (job.tds_amount === null || job.tds_amount === undefined) {
                            return <span className="text-amber-600 font-semibold">Pending</span>;
                          }
                          const tdsStr = String(job.tds_amount);
                          if (tdsStr === 'Requires Review' || tdsStr === 'REQUIRES_REVIEW') {
                            return <span className="text-rose-600 font-semibold">Requires Review</span>;
                          }
                          const num = typeof job.tds_amount === 'number' ? job.tds_amount : parseFloat(tdsStr);
                          if (!isNaN(num)) {
                            return <span className="font-medium text-slate-700">₹{num.toLocaleString()}</span>;
                          }
                          return <span>{tdsStr}</span>;
                        })()}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {getStatusBadge(job.status)}
                      {job.error_message && (
                        <div className="text-[10px] text-rose-600 font-mono mt-1 max-w-xs truncate" title={job.error_message}>
                          {job.error_message}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-700">
                      {job.current_step}
                    </td>
                    <td className="py-3 px-4 text-center font-bold">
                      <span className={`px-2 py-0.5 rounded-full text-[11px] ${job.attempt_count > 1 ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700'}`}>
                        {job.attempt_count}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-[11px]">
                      {job.created_at ? new Date(job.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {canStartJob && onStartJob && (
                          <button
                            onClick={() => onStartJob(job.id)}
                            disabled={isStartDisabled}
                            title={
                              hasActiveJob
                                ? 'Another filing automation is actively running. Only one filing can run at a time.'
                                : `Start automation for Job ${rowIndex}`
                            }
                            className={`px-2.5 py-1 rounded-lg font-bold flex items-center gap-1.5 text-xs transition shadow-xs ${
                              isStartDisabled
                                ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
                                : 'bg-emerald-600 hover:bg-emerald-500 text-white cursor-pointer active:scale-95'
                            }`}
                          >
                            {hasActiveJob ? (
                              <Lock className="w-3.5 h-3.5" />
                            ) : (
                              <Play className="w-3.5 h-3.5 fill-current" />
                            )}
                            <span>Start</span>
                          </button>
                        )}

                        {job.status === 'PAYMENT_PENDING' && onOpenSession && (
                          <button
                            onClick={() => onOpenSession(job.id)}
                            title="Open/Focus Browser Session"
                            className="p-1.5 hover:bg-amber-100 rounded text-amber-800 hover:text-amber-950 transition cursor-pointer font-bold flex items-center gap-1 text-[11px]"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span className="hidden xl:inline">Open Session</span>
                          </button>
                        )}

                        {job.status === 'PAYMENT_PENDING' && onConfirmPayment && (
                          <button
                            onClick={() => onConfirmPayment(job.id)}
                            title="Confirm Payment Completed"
                            className="p-1.5 hover:bg-emerald-100 rounded text-emerald-700 hover:text-emerald-900 transition cursor-pointer font-bold flex items-center gap-1 text-[11px]"
                          >
                            <Check className="w-3.5 h-3.5" />
                            <span className="hidden xl:inline">Paid</span>
                          </button>
                        )}

                        <button
                          onClick={() => onViewJob(job.id)}
                          title={job.status === 'COMPLETED' ? 'View Details' : (job.status === 'FAILED' ? 'View Error' : 'View Job Details')}
                          className="p-1.5 hover:bg-slate-200 rounded text-slate-600 hover:text-slate-900 transition cursor-pointer"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>

                        {job.status === 'FAILED' && (
                          <button
                            onClick={() => onRetryJob(job.id)}
                            title="Retry Automation"
                            className="p-1.5 hover:bg-blue-100 rounded text-blue-600 hover:text-blue-800 transition cursor-pointer"
                          >
                            <RotateCw className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {!['COMPLETED', 'CANCELLED'].includes(job.status) && (
                          <button
                            onClick={() => onCancelJob(job.id)}
                            title="Cancel Job"
                            className="p-1.5 hover:bg-rose-100 rounded text-rose-500 hover:text-rose-700 transition cursor-pointer"
                          >
                            <Ban className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {/* Compact Delete History Icon Button */}
                        {onDeleteJob && (() => {
                          const isJobActive = ['QUEUED', 'PROCESSING', 'PREVIEW_PENDING', 'PAYMENT_PENDING', 'IN_PROGRESS'].includes((job.status || '').toUpperCase());
                          return (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                if (window.confirm(`Are you sure you want to delete history for Job #${job.id}?`)) {
                                  onDeleteJob(job.id);
                                }
                              }}
                              disabled={isJobActive}
                              title={isJobActive ? "Cannot delete active/running job" : "Delete history"}
                              aria-label={`Delete history for Job #${job.id}`}
                              className={`p-1.5 rounded transition text-slate-400 hover:text-rose-600 hover:bg-rose-50 ${isJobActive ? 'opacity-30 cursor-not-allowed hover:text-slate-400 hover:bg-transparent' : 'cursor-pointer'}`}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          );
                        })()}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="p-3 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
        <div>
          Page {page} of {totalPages}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="p-1 rounded border border-slate-200 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            className="p-1 rounded border border-slate-200 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
