import React, { useState, useEffect } from 'react';
import type { PaymentPendingJob } from '../types';
import { 
  AlertTriangle, 
  ExternalLink, 
  CheckCircle2, 
  ShieldAlert, 
  Check, 
  Clock, 
  CreditCard,
  RotateCw,
  AlertCircle
} from 'lucide-react';

interface PaymentActionSectionProps {
  pendingJobs: PaymentPendingJob[];
  onOpenSession: (jobId: number) => Promise<void>;
  onConfirmPayment: (jobId: number) => Promise<void>;
  onReportProblem: (jobId: number, type: string, reason: string) => Promise<void>;
  onRetryJob: (jobId: number) => Promise<void>;
}

export const PaymentActionSection: React.FC<PaymentActionSectionProps> = ({
  pendingJobs,
  onOpenSession,
  onConfirmPayment,
  onReportProblem,
  onRetryJob
}) => {
  const [activeReviewJob, setActiveReviewJob] = useState<PaymentPendingJob | null>(null);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [openingId, setOpeningId] = useState<number | null>(null);

  // Problem modal state
  const [problemJobId, setProblemJobId] = useState<number | null>(null);
  const [problemType, setProblemType] = useState('PAYMENT_FAILED');
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

  const formatTdsDisplay = (tdsVal: any) => {
    if (tdsVal === null || tdsVal === undefined || tdsVal === '') {
      return { text: 'Pending', className: 'text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-200' };
    }
    if (tdsVal === 'Requires Review' || tdsVal === 'REQUIRES_REVIEW') {
      return { text: 'Requires Review', className: 'text-rose-600 bg-rose-50 px-2 py-0.5 rounded border border-rose-200' };
    }
    const num = typeof tdsVal === 'number' ? tdsVal : parseFloat(String(tdsVal).replace(/[₹,]/g, ''));
    if (!isNaN(num)) {
      return { text: `₹${num.toLocaleString()}`, className: 'text-amber-900 font-extrabold' };
    }
    return { text: String(tdsVal), className: 'text-slate-700' };
  };

  const handleOpen = async (jobId: number) => {
    setOpeningId(jobId);
    try {
      await onOpenSession(jobId);
    } finally {
      setOpeningId(null);
    }
  };

  const handleReviewAndPay = async (job: PaymentPendingJob) => {
    setActiveReviewJob(job);
    // Bring window to front so employee sees it immediately
    await handleOpen(job.id);
  };

  const handleConfirm = async (jobId: number) => {
    if (confirm("Confirm that payment was successfully completed on the visible portal browser?\n\nThis will mark the job COMPLETED and cleanly close its browser session.")) {
      setConfirmingId(jobId);
      try {
        await onConfirmPayment(jobId);
        if (activeReviewJob?.id === jobId) {
          setActiveReviewJob(null);
        }
      } finally {
        setConfirmingId(null);
      }
    }
  };

  const handleProblemSubmit = async () => {
    if (!problemJobId) return;
    if (!problemReason.trim()) {
      alert("Please provide problem details.");
      return;
    }
    await onReportProblem(problemJobId, problemType, problemReason);
    setProblemJobId(null);
    setProblemReason('');
    if (activeReviewJob?.id === problemJobId) {
      setActiveReviewJob(null);
    }
  };

  const milestones = [
    { label: 'Browser Initialized', done: true },
    { label: 'Portal Authenticated', done: true },
    { label: 'Form 141 Populated', done: true },
    { label: 'Form Validated', done: true },
    { label: 'Payment Gateway', done: false, active: true }
  ];

  return (
    <section className="bg-amber-500/10 border-2 border-amber-400/80 rounded-2xl p-5 shadow-sm space-y-4">
      {/* Top Banner Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-amber-300/60">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-amber-500 text-white rounded-xl shadow-xs">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-extrabold uppercase tracking-wide text-amber-950">
                Payment Action Required
              </h2>
              <span className="bg-amber-500 text-white font-extrabold text-xs px-2.5 py-0.5 rounded-full shadow-2xs">
                {pendingJobs.length} {pendingJobs.length === 1 ? 'FILING' : 'FILINGS'} WAITING
              </span>
            </div>
            <p className="text-xs text-amber-900/80 mt-0.5">
              Automation completed up to payment gateway. Isolated browser sessions are preserved. Human review and payment required.
            </p>
          </div>
        </div>
      </div>

      {/* Grid of Payment Pending Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {pendingJobs.map((job) => {
          const timerSec = elapsedTimes[job.id] ?? job.elapsed_seconds ?? 0;
          return (
            <div
              key={job.id}
              className="bg-white rounded-xl border border-amber-300 shadow-xs p-5 flex flex-col justify-between space-y-4 hover:shadow-md transition"
            >
              {/* Card Header */}
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 bg-amber-100 text-amber-900 rounded font-bold border border-amber-200">
                      Form 141 • {job.filing_reference || `FIL-${job.id}`}
                    </span>
                    <h3 className="text-lg font-bold text-slate-900 mt-1">
                      {job.customer_name}
                    </h3>
                    <div className="flex items-center gap-2 text-xs text-slate-500 font-mono mt-0.5">
                      <span>{job.customer_code}</span>
                      <span>•</span>
                      <span className="text-slate-700 font-semibold">{job.pan_masked}</span>
                      <span>•</span>
                      <span className="text-slate-400">{job.job_reference}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 bg-slate-100 px-2.5 py-1 rounded-lg text-slate-700 font-mono text-xs font-semibold">
                    <Clock className="w-3.5 h-3.5 text-amber-600" />
                    <span>{formatTimer(timerSec)}</span>
                  </div>
                </div>

                {/* Amount & TDS summary */}
                <div className="grid grid-cols-2 gap-2 bg-slate-50 border border-slate-200 rounded-lg p-3 mt-3 text-xs">
                  <div>
                    <span className="text-slate-500 font-medium block">Total Consideration</span>
                    <span className="text-sm font-bold text-slate-900">
                      ₹{job.amount ? job.amount.toLocaleString() : '0'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 font-medium block">TDS Amount Due</span>
                    {(() => {
                      const tdsDisplay = formatTdsDisplay(job.tds_amount);
                      return (
                        <span className={`text-sm ${tdsDisplay.className}`}>
                          {tdsDisplay.text}
                        </span>
                      );
                    })()}
                  </div>
                </div>

                {/* Milestone Progression */}
                <div className="mt-3 space-y-1">
                  <div className="grid grid-cols-5 gap-1 text-[10px] font-medium text-slate-600">
                    {milestones.map((m, idx) => (
                      <div
                        key={idx}
                        className={`p-1.5 rounded flex items-center gap-1 truncate border ${
                          m.done
                            ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                            : 'bg-amber-100 border-amber-300 text-amber-900 font-bold'
                        }`}
                        title={m.label}
                      >
                        {m.done ? (
                          <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />
                        ) : (
                          <div className="w-2 h-2 rounded-full bg-amber-500 animate-ping shrink-0" />
                        )}
                        <span className="truncate">{m.label}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Session availability alert */}
                {!job.session_available && (
                  <div className="mt-3 flex items-center gap-2 bg-rose-50 border border-rose-200 rounded-lg p-2 text-xs text-rose-700">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>Browser session unavailable (worker restarted or window closed).</span>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleOpen(job.id)}
                    disabled={openingId === job.id || !job.session_available}
                    title="Bring the exact Chromium tab/window to front on screen"
                    className="bg-slate-800 hover:bg-slate-900 text-white px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-2xs transition cursor-pointer disabled:opacity-40"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    {openingId === job.id ? 'Focusing...' : 'Open Session'}
                  </button>

                  <button
                    onClick={() => handleReviewAndPay(job)}
                    disabled={!job.session_available}
                    title="Review complete Form 141 and continue to manual payment"
                    className="bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-2xs transition cursor-pointer disabled:opacity-40"
                  >
                    <CreditCard className="w-3.5 h-3.5" />
                    Review & Pay
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleConfirm(job.id)}
                    disabled={confirmingId === job.id}
                    title="Confirm payment completion after paying on portal"
                    className="bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 shadow-2xs transition cursor-pointer disabled:opacity-50"
                  >
                    <Check className="w-3.5 h-3.5" />
                    {confirmingId === job.id ? 'Confirming...' : 'Payment Completed'}
                  </button>

                  <button
                    onClick={() => {
                      setProblemJobId(job.id);
                      setProblemReason('');
                    }}
                    title="Report portal or payment issue"
                    className="text-slate-500 hover:text-rose-600 border border-slate-200 hover:border-rose-300 px-2.5 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer"
                  >
                    Report Issue
                  </button>

                  {!job.session_available && (
                    <button
                      onClick={() => onRetryJob(job.id)}
                      title="Retry Automation from start"
                      className="bg-blue-600 hover:bg-blue-700 text-white px-2.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1 shadow-2xs transition cursor-pointer"
                    >
                      <RotateCw className="w-3.5 h-3.5" />
                      Retry
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Review & Pay Modal */}
      {activeReviewJob && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-200 space-y-5 animate-in fade-in">
            <div className="flex items-start justify-between border-b pb-3">
              <div>
                <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 bg-amber-100 text-amber-900 rounded font-bold border border-amber-300">
                  Human-Assisted Payment Flow
                </span>
                <h3 className="text-xl font-bold text-slate-900 mt-1">
                  Review & Pay — {activeReviewJob.customer_name}
                </h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  Job Reference: {activeReviewJob.job_reference} • Filing: {activeReviewJob.filing_reference}
                </p>
              </div>
              <button
                onClick={() => setActiveReviewJob(null)}
                className="text-slate-400 hover:text-slate-700 text-lg font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Verification Checklist */}
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3 text-xs">
              <h4 className="font-bold text-slate-800 uppercase tracking-wider text-[11px]">
                Form 141 Verification Summary
              </h4>
              <div className="grid grid-cols-2 gap-3 text-slate-700">
                <div>
                  <span className="text-slate-400 block">Deductor / Buyer:</span>
                  <span className="font-semibold text-slate-900">{activeReviewJob.customer_name}</span>
                </div>
                <div>
                  <span className="text-slate-400 block">PAN (Masked):</span>
                  <span className="font-mono font-bold text-slate-900">{activeReviewJob.pan_masked}</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Sale Consideration:</span>
                  <span className="font-semibold text-slate-900">₹{activeReviewJob.amount.toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-slate-400 block">TDS Amount Payable:</span>
                  {(() => {
                    const tdsDisplay = formatTdsDisplay(activeReviewJob.tds_amount);
                    return (
                      <span className={`font-mono text-sm ${tdsDisplay.className}`}>
                        {tdsDisplay.text}
                      </span>
                    );
                  })()}
                </div>
              </div>
            </div>

            {/* Step-by-Step Instructions */}
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-950 space-y-2">
              <div className="flex items-center gap-2 font-bold text-amber-900">
                <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
                <span>MANDATORY EMPLOYEE ACTIONS</span>
              </div>
              <ol className="list-decimal list-inside space-y-1 text-amber-900/90 pl-1 leading-relaxed">
                <li>Click <strong>Bring Browser to Front</strong> below to inspect the actual Income Tax portal page.</li>
                <li>Review all Form 141 details against the client purchase agreement.</li>
                <li>Proceed manually through the Income Tax payment gateway (NetBanking, Debit Card, or UPI).</li>
                <li>Complete payment verification on the bank/portal page.</li>
                <li>Return here and click <strong>Payment Completed</strong> to finalize this filing.</li>
              </ol>
            </div>

            {/* Modal Actions */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t">
              <button
                onClick={() => handleOpen(activeReviewJob.id)}
                disabled={openingId === activeReviewJob.id}
                className="bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 shadow-xs cursor-pointer"
              >
                <ExternalLink className="w-4 h-4" />
                {openingId === activeReviewJob.id ? 'Activating Window...' : 'Bring Browser to Front'}
              </button>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveReviewJob(null)}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
                >
                  Close
                </button>
                <button
                  onClick={() => handleConfirm(activeReviewJob.id)}
                  disabled={confirmingId === activeReviewJob.id}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 shadow-xs cursor-pointer disabled:opacity-50"
                >
                  <Check className="w-4 h-4" />
                  {confirmingId === activeReviewJob.id ? 'Confirming...' : 'Payment Completed'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Problem Report Modal */}
      {problemJobId && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900">Report Payment Problem</h3>
            <p className="text-xs text-slate-500 mt-1">
              Select the issue encountered on the Income Tax payment gateway:
            </p>

            <div className="mt-4 space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-700">Issue Type</label>
                <select
                  value={problemType}
                  onChange={(e) => setProblemType(e.target.value)}
                  className="w-full mt-1 border border-slate-300 rounded-lg p-2 text-xs"
                >
                  <option value="PAYMENT_FAILED">Payment Failed at Gateway</option>
                  <option value="MANUAL_INTERVENTION">Portal Challenge / CAPTCHA Required</option>
                  <option value="CANCELLED">Client Requested Cancellation</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Details / Error Message</label>
                <textarea
                  value={problemReason}
                  onChange={(e) => setProblemReason(e.target.value)}
                  placeholder="e.g. Bank OTP timed out, portal session expired, etc."
                  rows={3}
                  className="w-full mt-1 border border-slate-300 rounded-lg p-2 text-xs"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => setProblemJobId(null)}
                className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleProblemSubmit}
                className="px-4 py-2 text-xs font-bold bg-rose-600 text-white rounded-lg hover:bg-rose-700 shadow-xs cursor-pointer"
              >
                Submit Problem
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
