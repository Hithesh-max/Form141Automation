import React, { useState } from 'react';
import type { WebSocketEvent } from '../types';
import { Activity, CheckCircle2, AlertCircle, Clock, Zap } from 'lucide-react';

interface LiveTimelineProps {
  events: WebSocketEvent[];
}

export const LiveTimeline: React.FC<LiveTimelineProps> = ({ events }) => {
  const [jobFilter, setJobFilter] = useState('');

  const filteredEvents = jobFilter.trim()
    ? events.filter((e) => (e.job_id || '').toLowerCase().includes(jobFilter.toLowerCase().trim()))
    : events;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col h-full">
      <div className="p-3.5 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-500" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
            ACTIVITY LOG
          </h3>
        </div>
        <div className="flex items-center gap-1.5">
          <input
            type="text"
            placeholder="Filter job..."
            value={jobFilter}
            onChange={(e) => setJobFilter(e.target.value)}
            className="px-2 py-0.5 text-[11px] bg-slate-50 border border-slate-200 rounded text-slate-700 w-24 focus:w-32 transition-all focus:outline-none focus:border-blue-400"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2 max-h-[420px] font-mono text-xs">
        {filteredEvents.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-xs font-sans">
            {jobFilter.trim() ? `No events found matching "${jobFilter}".` : 'No live activity yet. Start the queue or import filings to begin automation.'}
          </div>
        ) : (
          filteredEvents.map((ev, i) => {
            const isDone = ev.status === 'COMPLETED';
            const isFailed = ev.status === 'FAILED' || ev.status === 'ERROR';
            const isPending = ev.status === 'PAYMENT_PENDING';

            return (
              <div
                key={`${ev.job_id}-${ev.timestamp}-${i}`}
                className="p-2.5 rounded-lg border border-slate-100 bg-slate-50/70 hover:bg-slate-50 transition flex flex-col gap-1"
              >
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>{new Date(ev.timestamp).toLocaleTimeString()}</span>
                  <span className="font-bold text-slate-700">{ev.job_id}</span>
                </div>
                <div className="flex items-start gap-2 mt-0.5">
                  {isDone ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  ) : isFailed ? (
                    <AlertCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                  ) : isPending ? (
                    <Clock className="w-4 h-4 text-amber-500 shrink-0 mt-0.5 animate-pulse" />
                  ) : (
                    <Activity className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1 leading-snug">
                    <span className="font-bold text-slate-800">[{ev.status}]</span>{' '}
                    <span className="text-slate-600">{ev.message}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
