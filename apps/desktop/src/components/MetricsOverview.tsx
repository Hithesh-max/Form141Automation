import React from 'react';
import type { DashboardMetrics, Form141KpiSummary } from '../types';
import { Users, Loader2, AlertTriangle, CheckCircle2, XCircle, Ban } from 'lucide-react';

interface MetricsOverviewProps {
  metrics: DashboardMetrics;
  kpiSummary?: Form141KpiSummary | null;
  onFilterStatus: (status: string) => void;
  activeFilter: string;
}

export const MetricsOverview: React.FC<MetricsOverviewProps> = ({
  metrics,
  kpiSummary,
  onFilterStatus,
  activeFilter
}) => {
  const totalCount = kpiSummary ? kpiSummary.total_filings : (metrics.total_jobs ?? 0);
  const readyCount = kpiSummary ? kpiSummary.ready : (metrics.ready ?? 0);
  const inProgressCount = kpiSummary ? kpiSummary.in_progress : ((metrics.queued ?? 0) + (metrics.processing ?? 0));
  const actionCount = kpiSummary ? kpiSummary.action_required : ((metrics.payment_pending ?? 0) + (metrics.manual_intervention ?? 0));
  const completedCount = kpiSummary ? kpiSummary.completed : (metrics.completed ?? 0);
  const failedCount = kpiSummary ? kpiSummary.failed : (metrics.failed ?? 0);
  const cancelledCount = kpiSummary ? kpiSummary.cancelled : (metrics.cancelled ?? 0);

  const cards = [
    {
      id: 'ALL',
      label: 'Total Filings',
      count: totalCount,
      icon: Users,
      color: 'border-slate-200 text-slate-700 bg-white hover:border-slate-300',
    },
    {
      id: 'READY',
      label: 'Ready to Start',
      count: readyCount,
      icon: CheckCircle2,
      color: 'border-emerald-200 text-emerald-800 bg-emerald-50/50 hover:bg-emerald-50',
    },
    {
      id: 'PROCESSING',
      label: 'In Progress',
      count: inProgressCount,
      icon: Loader2,
      color: 'border-blue-200 text-blue-700 bg-blue-50/50 hover:bg-blue-50',
    },
    {
      id: 'ACTION_REQUIRED',
      label: 'Action Required',
      count: actionCount,
      icon: AlertTriangle,
      color: 'border-amber-200 text-amber-800 bg-amber-50/60 hover:bg-amber-50',
    },
    {
      id: 'COMPLETED',
      label: 'Completed',
      count: completedCount,
      icon: CheckCircle2,
      color: 'border-emerald-200 text-emerald-700 bg-emerald-50/30 hover:bg-emerald-50',
    },
    {
      id: 'FAILED',
      label: 'Failed',
      count: failedCount,
      icon: XCircle,
      color: 'border-rose-200 text-rose-700 bg-rose-50/40 hover:bg-rose-50',
    },
    {
      id: 'CANCELLED',
      label: 'Cancelled',
      count: cancelledCount,
      icon: Ban,
      color: 'border-slate-200 text-slate-600 bg-slate-50/60 hover:bg-slate-100',
    }
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
      {cards.map((c) => {
        const Icon = c.icon;
        const isSelected = activeFilter === c.id;
        return (
          <button
            key={c.id}
            onClick={() => onFilterStatus(c.id)}
            className={`p-3 rounded-xl border text-left transition shadow-xs hover:shadow-md cursor-pointer ${c.color} ${
              isSelected ? 'ring-2 ring-blue-600 ring-offset-1' : ''
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{c.label}</span>
              <Icon className="w-4 h-4 opacity-75" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black">{c.count}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
};
