import { useEffect, useState, useCallback, useRef } from 'react';
import type {
  DashboardSummary,
  JobItem,
  SystemHealth,
  WebSocketEvent,
  Form141LogicalFilingItem,
  Form141ActiveLock,
  Form141KpiSummary
} from './types';
import { Header } from './components/Header';
import { MetricsOverview } from './components/MetricsOverview';
import { ActiveJobCard } from './components/ActiveJobCard';
import { PaymentActionSection } from './components/PaymentActionSection';
import { PreviewActionSection } from './components/PreviewActionSection';
import { QueueControls } from './components/QueueControls';
import { JobTable } from './components/JobTable';
import { Form141FilingsTable } from './components/Form141FilingsTable';
import { JobDetailModal } from './components/JobDetailModal';
import { ImportWizardModal } from './components/ImportWizardModal';
import { LiveTimeline } from './components/LiveTimeline';
import { FilingDetailsDrawer } from './components/FilingDetailsDrawer';
import { RemoteBrowserViewerModal } from './components/RemoteBrowserViewerModal';
import { ChevronDown, ChevronUp, Server, Activity, Lock } from 'lucide-react';

import { LoginModal } from './components/LoginModal';
import {
  apiFetch,
  API_BASE,
  WS_URL,
  getStoredUser,
  clearAuthToken,
  setUnauthorizedHandler
} from './services/api';
import type { AuthUser } from './services/api';

function App() {
  // Auth State
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(getStoredUser());
  const [isLoginOpen, setIsLoginOpen] = useState(!getStoredUser());

  // State
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(15);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const [events, setEvents] = useState<WebSocketEvent[]>([]);
  const [wsConnected, setWsConnected] = useState(false);

  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedFilingId, setSelectedFilingId] = useState<string | number | null>(null);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [isDiagnosticsOpen, setIsDiagnosticsOpen] = useState(false);
  const [form141Filings, setForm141Filings] = useState<Form141LogicalFilingItem[]>([]);
  const [form141ActiveLock, setForm141ActiveLock] = useState<Form141ActiveLock | null>(null);
  const [kpiSummary, setKpiSummary] = useState<Form141KpiSummary | null>(null);
  const [viewerModal, setViewerModal] = useState<{
    isOpen: boolean;
    jobId: number | null;
    jobReference: string;
    customerName: string;
    jobStatus: string;
    token: string;
    viewerUrl: string;
  }>({
    isOpen: false,
    jobId: null,
    jobReference: '',
    customerName: '',
    jobStatus: '',
    token: '',
    viewerUrl: ''
  });

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setCurrentUser(null);
      setIsLoginOpen(true);
    });
  }, []);

  const handleLogout = async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } catch {
      // ignore
    } finally {
      clearAuthToken();
      setCurrentUser(null);
      setIsLoginOpen(true);
    }
  };

  // 1. Authoritative Data Fetchers
  const fetchSummary = useCallback(async () => {
    try {
      const res = await apiFetch('/api/dashboard/summary');
      if (res.ok) {
        const data = await res.json();
        setSummary(data);
      }
    } catch (err) {
      console.debug('Failed to fetch summary:', err);
    }
  }, []);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await apiFetch('/api/system/health');
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch (err) {
      console.debug('Failed to fetch health:', err);
    }
  }, []);

  const fetchForm141Filings = useCallback(async () => {
    try {
      const res = await apiFetch('/api/form141/filings');
      if (res.ok) {
        const data = await res.json();
        setForm141Filings(data.filings || []);
      }
    } catch (err) {
      console.debug('Failed to fetch Form 141 filings:', err);
    }
  }, []);

  const fetchActiveLock = useCallback(async () => {
    try {
      const res = await apiFetch('/api/jobs/active-lock');
      if (res.ok) {
        const data = await res.json();
        setForm141ActiveLock(data);
      }
    } catch (err) {
      console.debug('Failed to fetch active lock:', err);
    }
  }, []);

  const fetchKpiSummary = useCallback(async () => {
    try {
      const res = await apiFetch('/api/form141/kpi-summary');
      if (res.ok) {
        const data = await res.json();
        setKpiSummary(data);
      }
    } catch (err) {
      console.debug('Failed to fetch Form 141 KPI summary:', err);
    }
  }, []);

  const fetchJobs = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString()
      });
      if (statusFilter && statusFilter !== 'ALL') {
        params.append('status', statusFilter);
      }
      if (search.trim()) {
        params.append('search', search.trim());
      }

      const res = await apiFetch(`/api/jobs/?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setJobs(data.items);
        setTotalJobs(data.total);
      }
    } catch (err) {
      console.debug('Failed to fetch jobs:', err);
    }
  }, [page, limit, statusFilter, search]);

  // Initial fetch and periodic poll fallback
  useEffect(() => {
    fetchSummary();
    fetchHealth();
    fetchJobs();
    fetchForm141Filings();
    fetchActiveLock();
    fetchKpiSummary();

    const interval = setInterval(() => {
      fetchSummary();
      fetchHealth();
      fetchForm141Filings();
      fetchActiveLock();
      fetchKpiSummary();
    }, 6000);
    return () => clearInterval(interval);
  }, [fetchSummary, fetchHealth, fetchJobs, fetchForm141Filings, fetchActiveLock, fetchKpiSummary]);

  const fetchJobsRef = useRef(fetchJobs);
  fetchJobsRef.current = fetchJobs;
  const fetchSummaryRef = useRef(fetchSummary);
  fetchSummaryRef.current = fetchSummary;
  const fetchHealthRef = useRef(fetchHealth);
  fetchHealthRef.current = fetchHealth;
  const fetchForm141FilingsRef = useRef(fetchForm141Filings);
  fetchForm141FilingsRef.current = fetchForm141Filings;
  const fetchActiveLockRef = useRef(fetchActiveLock);
  fetchActiveLockRef.current = fetchActiveLock;
  const fetchKpiSummaryRef = useRef(fetchKpiSummary);
  fetchKpiSummaryRef.current = fetchKpiSummary;


  // 2. WebSocket Real-time Connection (Single subscription on mount, no duplicate connections)
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: any = null;
    let isCancelled = false;

    const connectWebSocket = () => {
      if (isCancelled) return;
      try {
        ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
          if (isCancelled) {
            ws?.close();
            return;
          }
          setWsConnected(true);
          // Reconcile state
          fetchSummaryRef.current();
          fetchJobsRef.current();
          fetchHealthRef.current();
          fetchForm141FilingsRef.current();
          fetchActiveLockRef.current();
          fetchKpiSummaryRef.current();
        };

        ws.onmessage = (event) => {
          if (isCancelled) return;
          try {
            const data: WebSocketEvent = JSON.parse(event.data);
            setEvents((prev) => {
              // Deduplicate identical events received within 1.5s
              const isDup = prev.some(
                (e) =>
                  e.job_id === data.job_id &&
                  e.status === data.status &&
                  e.message === data.message &&
                  Math.abs(new Date(e.timestamp).getTime() - new Date(data.timestamp).getTime()) < 1500
              );
              if (isDup) return prev;
              return [data, ...prev].slice(0, 100);
            });

            // Trigger authoritative state reconciliation
            fetchSummaryRef.current();
            fetchJobsRef.current();
            fetchForm141FilingsRef.current();
            fetchActiveLockRef.current();
            fetchKpiSummaryRef.current();
          } catch (e) {
            console.error('Error parsing WS message:', e);
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          if (!isCancelled) {
            reconnectTimeout = setTimeout(connectWebSocket, 3000);
          }
        };

        ws.onerror = () => {
          ws?.close();
        };
      } catch (err) {
        setWsConnected(false);
        if (!isCancelled) {
          reconnectTimeout = setTimeout(connectWebSocket, 3000);
        }
      }
    };

    connectWebSocket();

    return () => {
      isCancelled = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) {
        ws.onclose = null; // Prevent reconnect on intentional unmount/cleanup
        ws.close();
      }
      wsRef.current = null;
    };
  }, []); // Run once on mount

  // 3. Queue Action Handlers
  const handleQueueStart = async () => {
    await apiFetch('/api/queue/start', { method: 'POST' });
    fetchSummary();
  };

  const handleQueuePause = async () => {
    await apiFetch('/api/queue/pause', { method: 'POST' });
    fetchSummary();
  };

  const handleQueueResume = async () => {
    await apiFetch('/api/queue/resume', { method: 'POST' });
    fetchSummary();
  };

  const handleQueueStop = async () => {
    await apiFetch('/api/queue/stop', { method: 'POST' });
    fetchSummary();
  };

  // 4. Job Action Handlers
  const handleOpenSession = async (jobId: number) => {
    try {
      const res = await apiFetch(`/api/jobs/${jobId}/open-session`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok || !data.success) {
        alert(data.detail || data.reason || 'Browser session unavailable');
        return;
      }
      if (data.viewer_url) {
        const fullUrl = data.viewer_url.startsWith('http') ? data.viewer_url : `${API_BASE}${data.viewer_url}`;
        const sessionToken = data.session_token || data.token || (data.viewer_url.includes('token=') ? data.viewer_url.split('token=')[1] : '');
        setViewerModal({
          isOpen: true,
          jobId: jobId,
          jobReference: data.job_reference || `JOB-${jobId}`,
          customerName: data.customer_name || '',
          jobStatus: data.status || '',
          token: sessionToken,
          viewerUrl: fullUrl
        });
        window.open(fullUrl, `form141_session_${jobId}`, 'noopener,noreferrer,width=1320,height=880');
      }
    } catch (e: any) {
      alert(`Error opening browser session: ${e.message}`);
    }
  };

  const handleConfirmReview = async (jobId: number) => {
    try {
      const res = await apiFetch(`/api/jobs/${jobId}/review/confirm`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        fetchSummary();
        fetchJobs();
      } else {
        alert(data.detail || 'Failed to record review confirmation');
      }
    } catch (e: any) {
      alert(`Error confirming review: ${e.message}`);
    }
  };


  const handleAuthorizePayment = async (jobId: number) => {
    try {
      const res = await apiFetch(`/api/jobs/${jobId}/preview/authorize`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        fetchSummary();
        fetchJobs();
      } else {
        alert(data.detail || 'Failed to authorize payment');
      }
    } catch (e: any) {
      alert(`Error authorizing payment: ${e.message}`);
    }
  };

  const handleConfirmPayment = async (jobId: number) => {
    const res = await apiFetch(`/api/jobs/${jobId}/payment/confirm`, { method: 'POST' });
    if (res.ok) {
      fetchSummary();
      fetchJobs();
    } else {
      const data = await res.json();
      alert(`Error confirming payment: ${data.detail || 'Request failed'}`);
    }
  };

  const handleReportProblem = async (jobId: number, problemType: string, details: string) => {
    const res = await apiFetch(`/api/jobs/${jobId}/payment/problem`, {
      method: 'POST',
      body: JSON.stringify({ problem_type: problemType, details })
    });
    if (res.ok) {
      fetchSummary();
      fetchJobs();
    } else {
      const data = await res.json();
      alert(`Error reporting problem: ${data.detail || 'Request failed'}`);
    }
  };

  const handleStartJob = async (jobId: number) => {
    try {
      const res = await apiFetch(`/api/jobs/${jobId}/start`, { method: 'POST' });
      const data = await res.json();
      if (res.status === 409) {
        alert(data.detail?.message || 'Another filing is currently active. Only one filing can run at a time.');
        return;
      }
      if (!res.ok) {
        alert(data.detail || 'Failed to start filing automation.');
        return;
      }
      fetchSummary();
      fetchJobs();
      fetchForm141Filings();
      fetchActiveLock();
    } catch (e: any) {
      alert(`Error starting job automation: ${e.message}`);
    }
  };

  const handleStartForm141Filing = async (filingIdentifier: string | number) => {
    try {
      const res = await apiFetch(`/api/form141/filings/${filingIdentifier}/start`, { method: 'POST' });
      const data = await res.json();
      if (res.status === 409) {
        alert(data.detail?.message || 'Another filing is currently active. Only one Form 141 filing can run at a time.');
        return;
      }
      if (!res.ok) {
        alert(data.detail || 'Failed to start Form 141 filing.');
        return;
      }
      fetchSummary();
      fetchJobs();
      fetchForm141Filings();
      fetchActiveLock();
    } catch (e: any) {
      alert(`Error starting Form 141 filing: ${e.message}`);
    }
  };

  const handleRetryJob = async (jobId: number) => {
    const res = await apiFetch(`/api/jobs/${jobId}/retry`, { method: 'POST' });
    if (res.ok) {
      fetchSummary();
      fetchJobs();
      fetchForm141Filings();
      fetchActiveLock();
    }
  };

  const handleCancelJob = async (jobId: number) => {
    if (confirm('Are you sure you want to cancel this filing job?')) {
      const res = await apiFetch(`/api/jobs/${jobId}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'Cancelled by user from dashboard' })
      });
      if (res.ok) {
        fetchSummary();
        fetchJobs();
        fetchForm141Filings();
        fetchActiveLock();
      }
    }
  };

  const handleDeleteForm141Filing = async (logicalFilingId: string) => {
    try {
      const res = await apiFetch(`/api/form141/filings/${logicalFilingId}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || `Failed to delete filing ${logicalFilingId}.`);
        return;
      }
      fetchSummary();
      fetchKpiSummary();
      fetchForm141Filings();
      fetchJobs();
      fetchActiveLock();
    } catch (e: any) {
      alert(`Error deleting filing: ${e.message}`);
    }
  };

  const handleDeleteJob = async (jobId: number) => {
    try {
      const res = await apiFetch(`/api/jobs/${jobId}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || `Failed to delete history for Job #${jobId}.`);
        return;
      }
      fetchSummary();
      fetchKpiSummary();
      fetchJobs();
      fetchForm141Filings();
      fetchActiveLock();
    } catch (e: any) {
      alert(`Error deleting job: ${e.message}`);
    }
  };


  const defaultMetrics = {
    total_clients: 0,
    total_jobs: 0,
    ready: 0,
    queued: 0,
    processing: 0,
    payment_pending: 0,
    completed: 0,
    failed: 0,
    manual_intervention: 0,
    cancelled: 0,
    completion_percentage: 0
  };

  const hasActiveJob = Boolean(
    (summary?.active_job && summary.active_job.status === 'PROCESSING') ||
    (summary?.preview_pending_jobs && summary.preview_pending_jobs.length > 0) ||
    (summary?.payment_pending_jobs && summary.payment_pending_jobs.length > 0)
  );

  return (
    <div className="min-h-screen bg-slate-100/70 text-slate-900 flex flex-col font-sans">
      {/* Top Header */}
      <Header
        wsConnected={wsConnected}
        health={health}
        onOpenImport={() => setIsImportOpen(true)}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      {/* Main Dashboard Workspace */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-6">
        {/* 1. Summary KPI Area */}
        <MetricsOverview
          metrics={summary?.metrics || defaultMetrics}
          kpiSummary={kpiSummary}
          activeFilter={statusFilter}
          onFilterStatus={(st) => {
            setStatusFilter(st);
            setPage(1);
          }}
        />

        {/* 2. Attention Required Area (Only rendered when employee action is required) */}
        {((summary?.preview_pending_jobs && summary.preview_pending_jobs.length > 0) ||
          (summary?.payment_pending_jobs && summary.payment_pending_jobs.length > 0)) && (
            <div className="space-y-4">
              {summary.preview_pending_jobs && summary.preview_pending_jobs.length > 0 && (
                <PreviewActionSection
                  pendingJobs={summary.preview_pending_jobs}
                  onOpenSession={handleOpenSession}
                  onAuthorizePayment={handleAuthorizePayment}
                  onReportProblem={handleReportProblem}
                  onRetryJob={handleRetryJob}
                />
              )}
              {summary.payment_pending_jobs && summary.payment_pending_jobs.length > 0 && (
                <PaymentActionSection
                  pendingJobs={summary.payment_pending_jobs}
                  onOpenSession={handleOpenSession}
                  onConfirmPayment={handleConfirmPayment}
                  onReportProblem={handleReportProblem}
                  onRetryJob={handleRetryJob}
                />
              )}
            </div>
          )}

        {/* 3. CURRENT FILING (Renamed from Section B) */}
        <div className="space-y-3 bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                {hasActiveJob ? (
                  <>
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-600"></span>
                  </>
                ) : (
                  <span className="inline-flex rounded-full h-3 w-3 bg-slate-300"></span>
                )}
              </span>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">
                CURRENT FILING
              </h2>
            </div>
            <span className="text-xs text-slate-500 font-medium flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-slate-400" />
              Strict Single-Filing Concurrency Lock (MAX_ACTIVE_FORM141_JOBS = 1)
            </span>
          </div>

          {summary?.active_job ? (
            <ActiveJobCard
              activeJob={summary.active_job}
              onConfirmPayment={handleConfirmPayment}
              onConfirmReview={handleConfirmReview}
              onReportProblem={handleReportProblem}
              onOpenSession={handleOpenSession}
              onCancelJob={handleCancelJob}
            />
          ) : (

            <div className="py-5 px-4 text-center text-slate-500 text-xs font-medium bg-slate-50 rounded-xl border border-dashed border-slate-200 flex flex-col items-center justify-center">
              <Activity className="w-6 h-6 text-slate-300 mb-1.5" />
              <span>No active filing job executing right now.</span>
              <span className="text-[11px] text-slate-400 mt-0.5">
                {/* Select any filing from &ldquo;Imported Filings&rdquo; below and click &ldquo;Start Filing&rdquo; to begin automation. */}
              </span>
            </div>
          )}
        </div>

        {/* 4. IMPORTED FILINGS (Renamed from Section A) */}
        <Form141FilingsTable
          filings={form141Filings}
          activeLock={form141ActiveLock}
          onStartFiling={handleStartForm141Filing}
          onOpenSession={handleOpenSession}
          onViewJob={(id) => setSelectedJobId(id)}
          onViewFilingDrawer={(logicalId) => setSelectedFilingId(logicalId)}
          onDeleteFiling={handleDeleteForm141Filing}
        />

        {/* 5. EXECUTION HISTORY & 6. ACTIVITY LOG */}
        <div className="space-y-3">
          <div className="flex items-center justify-between border-b border-slate-200 pb-2">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">
                EXECUTION HISTORY
              </h2>

            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
            <div className="lg:col-span-2">
              <JobTable
                jobs={jobs}
                total={totalJobs}
                page={page}
                limit={limit}
                search={search}
                statusFilter={statusFilter}
                hasActiveJob={hasActiveJob}
                onSearchChange={(val) => {
                  setSearch(val);
                  setPage(1);
                }}
                onPageChange={(p) => setPage(p)}
                onViewJob={(id) => setSelectedJobId(id)}
                onStartJob={handleStartJob}
                onRetryJob={handleRetryJob}
                onCancelJob={handleCancelJob}
                onOpenSession={handleOpenSession}
                onConfirmPayment={handleConfirmPayment}
                onDeleteJob={handleDeleteJob}
              />
            </div>

            <div className="lg:col-span-1">
              <LiveTimeline events={events} />
            </div>
          </div>
        </div>

        {/* 7. Collapsible System Diagnostics */}
        <div className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-xs">
          <button
            onClick={() => setIsDiagnosticsOpen((prev) => !prev)}
            className="w-full px-5 py-3 bg-slate-50/70 hover:bg-slate-100/70 transition flex items-center justify-between cursor-pointer text-left"
          >
            <div className="flex items-center gap-2.5">
              <Server className="w-4 h-4 text-slate-500" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                System Diagnostics & Concurrency Status
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-slate-500">
                Queue: <strong>{summary?.system.queue_state || 'RUNNING'}</strong> &bull; Worker: <strong>{summary?.system.worker_status || 'ONLINE'}</strong>
              </span>
              {isDiagnosticsOpen ? (
                <ChevronUp className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              )}
            </div>
          </button>

          {isDiagnosticsOpen && (
            <div className="p-5 border-t border-slate-200 space-y-4 text-xs">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">API Status</span>
                  <span className="font-bold text-slate-800">{health?.components.api || 'ONLINE'}</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Database</span>
                  <span className="font-bold text-slate-800">{health?.components.database || 'ONLINE'}</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Redis Concurrency Lock</span>
                  <span className="font-bold text-slate-800">{form141ActiveLock?.has_active_job ? '1 / 1 (LOCKED)' : '0 / 1 (AVAILABLE)'}</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Browser Automation</span>
                  <span className="font-bold text-slate-800">{summary?.system.browser_status || 'READY'}</span>
                </div>
              </div>

              {/* Queue Controls */}
              <div className="pt-2">
                <QueueControls
                  queueState={summary?.system.queue_state || 'RUNNING'}
                  completionPercentage={summary?.metrics.completion_percentage || 0}
                  totalJobs={summary?.metrics.total_jobs || 0}
                  completedJobs={summary?.metrics.completed || 0}
                  onStart={handleQueueStart}
                  onPause={handleQueuePause}
                  onResume={handleQueueResume}
                  onStop={handleQueueStop}
                />
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Filing Details Slide-over Drawer */}
      <FilingDetailsDrawer
        filingIdentifier={selectedFilingId}
        isOpen={Boolean(selectedFilingId)}
        onClose={() => setSelectedFilingId(null)}
        activeLock={form141ActiveLock}
        onStartFiling={handleStartForm141Filing}
        onOpenSession={handleOpenSession}
        onViewJob={(id) => {
          setSelectedFilingId(null);
          setSelectedJobId(id);
        }}
      />

      {/* Job Details Modal */}
      <JobDetailModal
        jobId={selectedJobId}
        onClose={() => setSelectedJobId(null)}
      />

      {/* Import Wizard Modal */}
      <ImportWizardModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        onImportComplete={() => {
          fetchSummary();
          fetchJobs();
          fetchForm141Filings();
          fetchActiveLock();
          fetchKpiSummary();
        }}
      />

      {/* Employee Login Modal */}
      <LoginModal
        isOpen={isLoginOpen}
        onSuccess={(user) => {
          setCurrentUser(user);
          setIsLoginOpen(false);
          fetchSummary();
          fetchJobs();
          fetchHealth();
          fetchForm141Filings();
          fetchActiveLock();
          fetchKpiSummary();
        }}
      />

      {/* Remote Browser Viewer Modal */}
      <RemoteBrowserViewerModal
        isOpen={viewerModal.isOpen}
        onClose={() => setViewerModal(prev => ({ ...prev, isOpen: false }))}
        jobId={viewerModal.jobId}
        jobReference={viewerModal.jobReference}
        customerName={viewerModal.customerName}
        jobStatus={viewerModal.jobStatus}
        token={viewerModal.token}
        viewerUrl={viewerModal.viewerUrl}
      />
    </div>
  );
}

export default App;
