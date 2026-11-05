import React, { useEffect, useState } from 'react';
import type { JobDetail } from '../types';
import { X, User, FileText, Activity, AlertCircle } from 'lucide-react';
import { apiFetch } from '../services/api';

interface JobDetailModalProps {
  jobId: number | null;
  onClose: () => void;
}

export const JobDetailModal: React.FC<JobDetailModalProps> = ({ jobId, onClose }) => {
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    setLoading(true);
    apiFetch(`/api/jobs/${jobId}`)
      .then((res) => res.json())
      .then((data) => setDetail(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [jobId]);

  if (!jobId) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-500 uppercase">Filing Job Details</span>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-800 font-bold border border-blue-200">
                {detail?.job_reference || `JOB-${jobId}`}
              </span>
            </div>
            <h2 className="text-lg font-bold text-slate-900 mt-0.5">
              {detail?.customer.name || 'Loading...'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading || !detail ? (
            <div className="py-16 text-center text-slate-400 text-sm">Loading job information...</div>
          ) : (
            <>
              {/* Info Grid */}
              <div className="grid grid-cols-2 gap-4">
                {/* Client Info */}
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                    <User className="w-4 h-4 text-blue-600" /> Client Information
                  </h3>
                  <div className="space-y-1.5 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Customer Code:</span>
                      <span className="font-mono font-semibold text-slate-800">{detail.customer.customer_code}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Taxpayer Name:</span>
                      <span className="font-medium text-slate-800">{detail.customer.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">PAN (Masked):</span>
                      <span className="font-mono font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded">{detail.customer.pan_masked}</span>
                    </div>
                  </div>
                </div>

                {/* Filing Info */}
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-indigo-600" /> Filing & Amounts
                  </h3>
                  <div className="space-y-1.5 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Filing Reference:</span>
                      <span className="font-mono font-medium text-slate-800">{detail.filing.filing_reference}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Total Consideration:</span>
                      <span className="font-bold text-slate-900">₹{detail.filing.amount.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">TDS Amount:</span>
                      {(() => {
                        const val = detail.filing.tds_amount;
                        if (val === null || val === undefined) {
                          return <span className="font-semibold text-amber-600">Pending</span>;
                        }
                        const s = String(val);
                        if (s === 'Requires Review' || s === 'REQUIRES_REVIEW') {
                          return <span className="font-semibold text-rose-600">Requires Review</span>;
                        }
                        const num = typeof val === 'number' ? val : parseFloat(s);
                        if (!isNaN(num)) {
                          return <span className="font-bold text-indigo-700">₹{num.toLocaleString()}</span>;
                        }
                        return <span className="font-medium text-slate-700">{s}</span>;
                      })()}
                    </div>
                  </div>
                </div>
              </div>

              {/* Status Banner */}
              <div className="p-4 rounded-xl border border-slate-200 flex items-center justify-between">
                <div>
                  <div className="text-xs text-slate-500">Current Status</div>
                  <div className="text-base font-bold text-slate-900 mt-0.5">{detail.status}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">Current Automation Step</div>
                  <div className="text-xs font-mono font-semibold text-blue-700 bg-blue-50 px-2 py-1 rounded mt-0.5">
                    {detail.current_step}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 text-right">Attempts</div>
                  <div className="text-base font-bold text-slate-900 text-right">{detail.attempt_count}</div>
                </div>
              </div>

              {/* Error Box if applicable */}
              {detail.error_message && (
                <div className="p-4 rounded-xl border border-rose-200 bg-rose-50 text-rose-800 text-xs">
                  <div className="font-bold flex items-center gap-1.5 mb-1">
                    <AlertCircle className="w-4 h-4" /> Failure Reason ({detail.error_code || 'ERROR'})
                  </div>
                  <div className="font-mono text-[11px] mt-1 bg-white/60 p-2 rounded border border-rose-200">
                    {detail.error_message}
                  </div>
                </div>
              )}

              {/* Audit Timeline */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                  <Activity className="w-4 h-4 text-slate-700" /> Automation Audit Timeline
                </h3>
                <div className="border border-slate-200 rounded-xl divide-y divide-slate-100 bg-white overflow-hidden text-xs">
                  {detail.timeline.length === 0 ? (
                    <div className="py-6 text-center text-slate-400">No events logged yet for this job.</div>
                  ) : (
                    detail.timeline.map((ev) => (
                      <div key={ev.id} className="p-3 flex items-start gap-3 hover:bg-slate-50/50">
                        <span className="font-mono text-[11px] text-slate-400 shrink-0 mt-0.5">
                          {ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : ''}
                        </span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold font-mono bg-slate-100 text-slate-700 shrink-0">
                          {ev.status}
                        </span>
                        <span className="text-slate-700 flex-1">{ev.message}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 text-white rounded-lg text-xs font-semibold hover:bg-slate-700 transition cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
