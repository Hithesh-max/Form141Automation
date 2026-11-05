import React, { useState, useEffect } from 'react';
import type { ActiveJob } from '../types';
import { Clock, Check, ShieldAlert, Monitor /*, CheckCircle2, AlertTriangle, XCircle, Loader2 */ } from 'lucide-react';

interface ActiveJobCardProps {
  activeJob: ActiveJob | null;
  onConfirmPayment: (jobId: number) => Promise<void>;
  onConfirmReview?: (jobId: number) => Promise<void>;
  onReportProblem: (jobId: number, type: string, reason: string) => Promise<void>;
  onOpenSession?: (jobId: number) => Promise<void>;
  onCancelJob?: (jobId: number) => Promise<void>;
}

export const ActiveJobCard: React.FC<ActiveJobCardProps> = ({
  activeJob,
  onConfirmPayment,
  onConfirmReview,
  onReportProblem,
  onOpenSession,
  onCancelJob
}) => {

  const [seconds, setSeconds] = useState(activeJob?.elapsed_seconds || 0);
  const [confirming, setConfirming] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [showProblemModal, setShowProblemModal] = useState(false);
  const [problemReason, setProblemReason] = useState('');
  const [problemType, setProblemType] = useState('PAYMENT_FAILED');

  useEffect(() => {
    setSeconds(activeJob?.elapsed_seconds || 0);
    if (!activeJob) return;

    const interval = setInterval(() => {
      setSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [activeJob?.id, activeJob?.elapsed_seconds]);

  const formatTimer = (totalSec: number) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  if (!activeJob) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col items-center justify-center min-h-[220px] text-center">
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-3">
          <Monitor className="w-6 h-6" />
        </div>
        <h3 className="font-semibold text-slate-700">No Active Automation Job</h3>
        <p className="text-xs text-slate-400 mt-1 max-w-sm">
          The automation worker is idle and ready. When jobs are queued and the queue is running, the next client will appear here.
        </p>
      </div>
    );
  }

  const isPaymentPending = activeJob.status === 'PAYMENT_PENDING';
  const isReviewRequired =
    isPaymentPending ||
    activeJob.status === 'PREVIEW_PENDING' ||
    activeJob.status === 'REVIEW_REQUIRED' ||
    activeJob.status === 'WAITING_FOR_HUMAN';


  /*
  // Temporarily disabled:
  // Five-stage filing progress tracker helpers.
  // Re-enable after browser-session and stage synchronization are fixed.

  // 5 Filing Workflow Stages
  const steps = [
    { key: 'BROWSER', label: 'Browser Initialized' },
    { key: 'LOGIN', label: 'Portal Authenticated' },
    { key: 'FORM', label: 'Form 141 Populated' },
    { key: 'VALIDATED', label: 'Form Validated' },
    { key: 'PAYMENT', label: 'Payment Gateway' }
  ];

  type StageState = 'completed' | 'active' | 'pending' | 'failed' | 'intervention' | 'cancelled';

  const getStepStatus = (index: number): StageState => {
    const status = (activeJob.status || '').toUpperCase();
    const step = (activeJob.current_step || '').toUpperCase();

    if (status === 'COMPLETED') {
      return 'completed';
    }

    if (status === 'PAYMENT_PENDING' || status === 'PREVIEW_PENDING') {
      if (index < 4) return 'completed';
      return 'active';
    }

    if (status === 'MANUAL_INTERVENTION') {
      if (step.includes('AUTH') || step.includes('LOGIN')) {
        if (index === 0) return 'completed';
        if (index === 1) return 'intervention';
        return 'pending';
      }
      if (index < 4) return 'completed';
      return 'intervention';
    }

    if (status === 'FAILED') {
      if (step.includes('BROWSER')) {
        if (index === 0) return 'failed';
        return 'pending';
      }
      if (step.includes('AUTH') || step.includes('LOGIN')) {
        if (index === 0) return 'completed';
        if (index === 1) return 'failed';
        return 'pending';
      }
      if (step.includes('FILLING') || step.includes('POPULAT') || step.includes('TAB1') || step.includes('TAB2') || step.includes('NAVIGATION')) {
        if (index < 2) return 'completed';
        if (index === 2) return 'failed';
        return 'pending';
      }
      if (step.includes('VALIDAT') || step.includes('SAVE') || step.includes('MODE') || step.includes('PREVIEW')) {
        if (index < 3) return 'completed';
        if (index === 3) return 'failed';
        return 'pending';
      }
      if (index < 4) return 'completed';
      return 'failed';
    }

    if (status === 'CANCELLED') {
      if (step.includes('BROWSER')) {
        if (index === 0) return 'cancelled';
        return 'pending';
      }
      if (step.includes('AUTH') || step.includes('LOGIN')) {
        if (index === 0) return 'completed';
        if (index === 1) return 'cancelled';
        return 'pending';
      }
      if (step.includes('FILLING') || step.includes('POPULAT') || step.includes('TAB1') || step.includes('TAB2')) {
        if (index < 2) return 'completed';
        if (index === 2) return 'cancelled';
        return 'pending';
      }
      if (step.includes('VALIDAT') || step.includes('SAVE')) {
        if (index < 3) return 'completed';
        if (index === 3) return 'cancelled';
        return 'pending';
      }
      if (index < 4) return 'completed';
      return 'cancelled';
    }

    // Status is PROCESSING
    if (status === 'PROCESSING') {
      if (step === 'BROWSER_INITIALIZED' || step === 'LOGIN_IN_PROGRESS') {
        if (index === 0) return 'completed';
        if (index === 1) return 'active';
        return 'pending';
      }
      if (step === 'PORTAL_AUTHENTICATED' || step.includes('NAVIGATION') || step.includes('FORM_FILLING') || step.includes('TAB1') || step.includes('TAB2')) {
        if (index < 2) return 'completed';
        if (index === 2) return 'active';
        return 'pending';
      }
      if (step === 'FORM_POPULATED' || step === 'FORM_VALIDATING' || step === 'FORM_SAVING') {
        if (index < 3) return 'completed';
        if (index === 3) return 'active';
        return 'pending';
      }
      if (step === 'FORM_VALIDATED') {
        if (index < 4) return 'completed';
        if (index === 4) return 'active';
        return 'pending';
      }
      // Initial startup: QUEUED / AUTOMATING / STARTING
      if (index === 0) return 'active';
      return 'pending';
    }

    // Default
    if (index === 0) return 'active';
    return 'pending';
  };

  const getStageDescription = () => {
    const status = (activeJob.status || '').toUpperCase();
    const step = (activeJob.current_step || '').toUpperCase();

    if (status === 'COMPLETED') {
      return 'Filing completed successfully.';
    }
    if (status === 'CANCELLED') {
      return 'Filing was cancelled by employee.';
    }
    if (status === 'MANUAL_INTERVENTION') {
      return 'Please complete portal authentication in the browser session.';
    }
    if (status === 'PAYMENT_PENDING' || status === 'PREVIEW_PENDING') {
      return 'Filing is ready for payment review — Payment requires manual confirmation.';
    }
    if (status === 'FAILED') {
      return `Filing failed: ${activeJob.current_step.replace(/_/g, ' ')}`;
    }

    // PROCESSING
    if (step === 'BROWSER_INITIALIZED') {
      return 'Browser initialized successfully. Authenticating with portal...';
    }
    if (step === 'LOGIN_IN_PROGRESS') {
      return 'Authenticating with Income Tax portal...';
    }
    if (step === 'PORTAL_AUTHENTICATED') {
      return 'Portal authenticated. Navigating to Form 141...';
    }
    if (step.includes('NAVIGATION') || step.includes('FORM_FILLING') || step.includes('TAB1') || step.includes('TAB2')) {
      return 'Populating Form 141';
    }
    if (step === 'FORM_POPULATED') {
      return 'Form 141 fields populated and verified.';
    }
    if (step === 'FORM_VALIDATING' || step === 'FORM_SAVING') {
      return 'Validating Form 141';
    }
    if (step === 'FORM_VALIDATED') {
      return 'Form 141 validated successfully. Proceeding to payment gateway...';
    }
    return 'Waiting for browser initialization';
  };
  */

  const handleConfirm = async () => {
    if (confirm("Confirm that payment was successfully completed on the visible portal browser?\n\nThis will mark the job COMPLETED and close the session.")) {
      setConfirming(true);
      try {
        await onConfirmPayment(activeJob.id);
      } finally {
        setConfirming(false);
      }
    }
  };

  const handleProblemSubmit = async () => {
    if (!problemReason) {
      alert("Please enter a brief description of the problem.");
      return;
    }
    await onReportProblem(activeJob.id, problemType, problemReason);
    setShowProblemModal(false);
    setProblemReason('');
  };

  return (
    <div className={`rounded-xl border shadow-sm p-5 transition-all ${
      isPaymentPending 
        ? 'bg-amber-50/40 border-amber-300 ring-2 ring-amber-400/50' 
        : 'bg-white border-slate-200'
    }`}>
      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-200/80">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Active Job</span>
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-semibold border border-slate-300">
              {activeJob.job_reference}
            </span>
          </div>
          <h2 className="text-xl font-bold text-slate-900 mt-1">
            {activeJob.customer_name} <span className="text-sm font-medium text-slate-500">({activeJob.customer_code})</span>
          </h2>
        </div>

        <div className="flex items-center gap-3">
          {onOpenSession && (
            <button
              onClick={() => onOpenSession(activeJob.id)}
              className="bg-slate-800 hover:bg-slate-700 text-white px-2.5 py-1.5 rounded-lg text-xs font-semibold shadow-xs transition flex items-center gap-1 cursor-pointer"
              title="Open visible browser session"
            >
              <Monitor className="w-3.5 h-3.5 text-blue-400" />
              <span>Browser Session</span>
            </button>
          )}
          <div className="flex items-center gap-1.5 bg-slate-100 px-3 py-1.5 rounded-lg text-slate-700 text-sm font-mono font-medium">
            <Clock className="w-4 h-4 text-slate-500" />
            <span>{formatTimer(seconds)}</span>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
            isPaymentPending ? 'bg-amber-500 text-white animate-pulse' : 'bg-blue-600 text-white'
          }`}>
            {activeJob.status.replace('_', ' ')}
          </span>
          {onCancelJob && (
            <button
              onClick={() => onCancelJob(activeJob.id)}
              className="bg-slate-100 hover:bg-rose-50 text-slate-600 hover:text-rose-700 border border-slate-300 hover:border-rose-300 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer"
              title="Cancel / Abort filing"
            >
              Cancel Filing
            </button>
          )}
        </div>
      </div>

      {/*
        Temporarily disabled:
        Five-stage filing progress tracker.
        Re-enable after browser-session and stage synchronization are fixed.
      */}
      {/*
      <div className="py-4">
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {steps.map((st, i) => {
            const stepState = getStepStatus(i);
            const isClickable = Boolean(onOpenSession) && (stepState === 'completed' || stepState === 'active' || stepState === 'intervention');

            return (
              <button
                key={st.key}
                type="button"
                onClick={() => isClickable && onOpenSession && onOpenSession(activeJob.id)}
                disabled={!isClickable}
                title={
                  isClickable 
                    ? `Click to bring browser session to foreground (${st.label} - ${stepState})` 
                    : `${st.label} (${stepState})`
                }
                className={`flex items-center gap-2 p-2 rounded-lg text-xs font-medium border text-left transition-all ${
                  stepState === 'completed'
                    ? 'bg-emerald-50 border-emerald-300 text-emerald-800 hover:bg-emerald-100 hover:border-emerald-400'
                    : stepState === 'active'
                    ? 'bg-blue-50 border-blue-400 text-blue-900 ring-1 ring-blue-400/50 shadow-xs hover:bg-blue-100'
                    : stepState === 'intervention'
                    ? 'bg-amber-50 border-amber-400 text-amber-900 ring-1 ring-amber-400/50 shadow-xs hover:bg-amber-100'
                    : stepState === 'failed'
                    ? 'bg-rose-50 border-rose-300 text-rose-800'
                    : stepState === 'cancelled'
                    ? 'bg-slate-100 border-slate-300 text-slate-500'
                    : 'bg-slate-50 border-slate-200 text-slate-400 opacity-70'
                } ${isClickable ? 'cursor-pointer' : 'cursor-default pointer-events-none'}`}
              >
                {stepState === 'completed' && (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                )}
                {stepState === 'active' && (
                  <Loader2 className="w-4 h-4 text-blue-600 animate-spin shrink-0" />
                )}
                {stepState === 'intervention' && (
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                )}
                {stepState === 'failed' && (
                  <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
                )}
                {stepState === 'cancelled' && (
                  <div className="w-4 h-4 rounded-full border border-slate-400 flex items-center justify-center text-[10px] text-slate-500 shrink-0 font-bold">
                    ✕
                  </div>
                )}
                {stepState === 'pending' && (
                  <div className="w-4 h-4 rounded-full border border-slate-300 flex items-center justify-center text-[10px] text-slate-400 shrink-0">
                    {i + 1}
                  </div>
                )}
                <span className="truncate">{st.label}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-3 flex flex-col items-center justify-center text-center">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs font-semibold text-slate-700">
            {activeJob.status === 'PROCESSING' && <Loader2 className="w-3.5 h-3.5 text-blue-600 animate-spin" />}
            {activeJob.status === 'MANUAL_INTERVENTION' && <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />}
            {activeJob.status === 'PAYMENT_PENDING' && <Clock className="w-3.5 h-3.5 text-amber-600" />}
            {activeJob.status === 'COMPLETED' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
            {activeJob.status === 'FAILED' && <XCircle className="w-3.5 h-3.5 text-rose-600" />}
            <span>{getStageDescription()}</span>
          </div>
          {Boolean(onOpenSession) && (
            <p className="text-[10px] text-slate-400 mt-1">
              Click any active or completed stage to bring the Chrome browser session to foreground
            </p>
          )}
        </div>
      </div>
      */}

      {/* Human-in-the-Loop Review and Payment Handoff Boundary */}
      {isReviewRequired && (
        <div className="bg-amber-100/70 border border-amber-300 rounded-xl p-4 mt-2">
          <div className="flex items-start gap-3">
            <div className="bg-amber-500 text-white p-2 rounded-lg shrink-0">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h4 className="text-sm font-bold text-amber-900">
                Review Required — Please review the completed Form 141 in the browser.
              </h4>
              <p className="text-xs text-amber-800 mt-1 leading-relaxed">
                Your Form 141 has been filled and validated. Please open the browser session and review the complete form before proceeding.
              </p>
              <div className="flex flex-wrap items-center gap-2.5 mt-4">
                {onOpenSession && (
                  <button
                    onClick={() => onOpenSession(activeJob.id)}
                    className="bg-slate-800 hover:bg-slate-900 text-white px-3.5 py-2 rounded-lg font-semibold text-xs flex items-center gap-1.5 shadow-xs transition cursor-pointer"
                  >
                    <Monitor className="w-3.5 h-3.5 text-blue-400" />
                    <span>Open Browser Session</span>
                  </button>
                )}
                {onConfirmReview && (
                  <button
                    onClick={async () => {
                      setReviewing(true);
                      try {
                        await onConfirmReview(activeJob.id);
                      } finally {
                        setReviewing(false);
                      }
                    }}
                    disabled={reviewing}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-3.5 py-2 rounded-lg font-semibold text-xs flex items-center gap-1.5 shadow-xs transition cursor-pointer disabled:opacity-50"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>{reviewing ? 'Saving Review...' : 'I Have Reviewed the Form'}</span>
                  </button>
                )}
                <button
                  onClick={handleConfirm}
                  disabled={confirming}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-2 rounded-lg font-semibold text-xs flex items-center gap-1.5 shadow-xs transition cursor-pointer disabled:opacity-50"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>{confirming ? 'Confirming...' : 'Payment Completed'}</span>
                </button>
                <button
                  onClick={() => setShowProblemModal(true)}
                  className="bg-white hover:bg-rose-50 text-rose-700 border border-rose-300 px-3.5 py-2 rounded-lg font-medium text-xs shadow-xs transition cursor-pointer"
                >
                  Report Problem / Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}


      {/* Problem Report Modal */}
      {showProblemModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900">Report Payment Problem</h3>
            <p className="text-xs text-slate-500 mt-1">
              Select the issue encountered on the payment gateway:
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
                  <option value="MANUAL_INTERVENTION">Portal Challenge / CAPTCHA Presented</option>
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
                onClick={() => setShowProblemModal(false)}
                className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleProblemSubmit}
                className="px-4 py-2 text-xs font-bold bg-rose-600 text-white rounded-lg hover:bg-rose-700 shadow-sm"
              >
                Submit Problem
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
