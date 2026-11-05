import React, { useState, useEffect } from 'react';
import type { PreviewPendingJob } from '../types';
import { 
  FileCheck, 
  ExternalLink, 
  AlertTriangle, 
  Clock, 
  AlertCircle,
  ArrowRight
} from 'lucide-react';

interface PreviewActionSectionProps {
  pendingJobs: PreviewPendingJob[];
  onOpenSession: (jobId: number) => Promise<void>;
  onAuthorizePayment: (jobId: number) => Promise<void>;
  onReportProblem: (jobId: number, type: string, reason: string) => Promise<void>;
  onRetryJob?: (jobId: number) => Promise<void>;
}

export const PreviewActionSection: React.FC<PreviewActionSectionProps> = ({
  pendingJobs,
  onOpenSession,
  onAuthorizePayment,
  onReportProblem
}) => {
  const [authorizingId, setAuthorizingId] = useState<number | null>(null);
  const [openingId, setOpeningId] = useState<number | null>(null);

  // Problem modal state
  const [problemJobId, setProblemJobId] = useState<number | null>(null);
  const [problemType, setProblemType] = useState('DATA_MISMATCH');
  const [problemReason, setProblemReason] = useState('');

  // Timers for each job
  const [elapsedTimes, setElapsedTimes] = useState<Record<number, number>>({});

  useEffect(() => {
    const initial: Record<number, number> = {};
    pendingJobs.forEach((j) => {
      initial[j.id] = j.elapsed_seconds || 0;
    });
    setElapsedTimes(initial);

    const interval = setInterval(() => {
      setElapsedTimes((prev) => {
        const next = { ...prev };
        Object.keys(next).forEach((k) => {
          next[Number(k)] = (next[Number(k)] || 0) + 1;
        });
        return next;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [pendingJobs]);

  if (!pendingJobs || pendingJobs.length === 0) {
    return null;
  }

  const formatTimer = (totalSec: number) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleOpen = async (jobId: number) => {
    setOpeningId(jobId);
    try {
      await onOpenSession(jobId);
    } finally {
      setOpeningId(null);
    }
  };

  const handleAuthorize = async (jobId: number) => {
    setAuthorizingId(jobId);
    try {
      await onAuthorizePayment(jobId);
    } finally {
      setAuthorizingId(null);
    }
  };

  const submitProblem = async () => {
    if (!problemJobId) return;
    await onReportProblem(problemJobId, problemType, problemReason);
    setProblemJobId(null);
    setProblemReason('');
  };

  return (
    <div className="bg-amber-50 border border-amber-300 rounded-xl p-5 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-amber-500 text-white rounded-lg shadow-sm">
            <FileCheck className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-lg font-bold text-amber-950">FORM 141 REVIEW REQUIRED</h2>
              <span className="px-2 py-0.5 text-xs font-semibold bg-amber-200 text-amber-900 rounded-full">
                {pendingJobs.length} {pendingJobs.length === 1 ? 'Job' : 'Jobs'} Awaiting Approval
              </span>
            </div>
            <p className="text-xs text-amber-800 mt-0.5">
              Automation reached the official portal <strong>Preview and Make Payment</strong> page.
              Open the real session to review or edit. Clicking <em>Proceed to Payment</em> authorizes Pay Now.
            </p>
          </div>
        </div>
      </div>

      {/* Cards for each PREVIEW_PENDING job */}
      <div className="grid grid-cols-1 gap-4">
        {pendingJobs.map((job) => {
          const timer = elapsedTimes[job.id] || job.elapsed_seconds || 0;
          const isOpening = openingId === job.id;
          const isAuthorizing = authorizingId === job.id;

          return (
            <div
              key={job.id}
              className="bg-white border border-amber-200 rounded-lg p-4 shadow-xs hover:border-amber-400 transition-colors"
            >
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                {/* Job metadata */}
                <div className="space-y-1">
                  <div className="flex items-center space-x-3">
                    <span className="font-mono font-bold text-slate-900">{job.job_reference}</span>
                    <span className="text-xs text-slate-500">•</span>
                    <span className="text-xs font-medium text-slate-600">Filing: {job.filing_reference}</span>
                    <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-100 px-2 py-0.5 rounded">
                      <Clock className="w-3 h-3" />
                      In Review: {formatTimer(timer)}
                    </span>
                    {job.session_available ? (
                      <span className="text-xs bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-medium">
                        Portal Session Active
                      </span>
                    ) : (
                      <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                        Session Offline
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-slate-700">
                    <span className="font-semibold">{job.customer_name}</span>{' '}
                    <span className="text-xs text-slate-500">({job.customer_code})</span> —{' '}
                    <span className="font-mono text-xs text-slate-600">PAN: {job.pan_masked}</span>
                  </div>
                  <div className="text-xs text-slate-600 flex items-center space-x-4">
                    <span>Consideration: <strong>₹{job.amount?.toLocaleString() || '0'}</strong></span>
                    <span>Total TDS: <strong className="text-amber-900">₹{job.tds_amount?.toLocaleString() || '0'}</strong></span>
                  </div>
                </div>

                {/* 3 Explicit Action Buttons */}
                <div className="flex flex-wrap items-center gap-2">
                  {/* Button 1: OPEN SESSION */}
                  <button
                    onClick={() => handleOpen(job.id)}
                    disabled={isOpening}
                    className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-md bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition-colors disabled:opacity-50"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    {isOpening ? 'Focusing...' : 'OPEN SESSION'}
                  </button>

                  {/* Button 2: REVIEWED — PROCEED TO PAYMENT */}
                  <button
                    onClick={() => handleAuthorize(job.id)}
                    disabled={isAuthorizing || !job.session_available}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold rounded-md bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm transition-colors disabled:opacity-50"
                    title={!job.session_available ? 'Browser session unavailable' : 'Click Pay Now on real portal'}
                  >
                    <ArrowRight className="w-3.5 h-3.5" />
                    {isAuthorizing ? 'Authorizing...' : 'REVIEWED — PROCEED TO PAYMENT'}
                  </button>

                  {/* Button 3: REPORT PROBLEM */}
                  <button
                    onClick={() => setProblemJobId(job.id)}
                    className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-md bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 transition-colors"
                  >
                    <AlertTriangle className="w-3.5 h-3.5" />
                    REPORT PROBLEM
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Problem Report Modal */}
      {problemJobId && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center space-x-2 text-rose-600">
              <AlertCircle className="w-5 h-5" />
              <h3 className="font-bold text-slate-900">Report Form 141 Issue</h3>
            </div>
            <p className="text-xs text-slate-600">
              Flag an error on the portal preview page or request manual intervention.
            </p>
            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Issue Category</label>
                <select
                  value={problemType}
                  onChange={(e) => setProblemType(e.target.value)}
                  className="w-full border border-slate-300 rounded p-2 text-slate-900"
                >
                  <option value="DATA_MISMATCH">Data Mismatch on Preview Page</option>
                  <option value="TAX_CALCULATION_ERROR">Tax/TDS Amount Discrepancy</option>
                  <option value="PORTAL_REJECTED_FIELD">Portal Highlighted Field Error</option>
                  <option value="MANUAL_INTERVENTION">Requires Manual Employee Correction</option>
                  <option value="PORTAL_CRASH">Portal Session Expired / Crashed</option>
                </select>
              </div>
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Details</label>
                <textarea
                  rows={3}
                  value={problemReason}
                  onChange={(e) => setProblemReason(e.target.value)}
                  placeholder="Describe the discrepancy observed on the portal preview..."
                  className="w-full border border-slate-300 rounded p-2 text-slate-900"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setProblemJobId(null)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded"
              >
                Cancel
              </button>
              <button
                onClick={submitProblem}
                className="px-3 py-1.5 text-xs font-bold bg-rose-600 text-white rounded hover:bg-rose-700"
              >
                Submit Report
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
