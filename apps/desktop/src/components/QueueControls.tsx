import React from 'react';
import { Play, Pause, Square } from 'lucide-react';

interface QueueControlsProps {
  queueState: string;
  completionPercentage: number;
  totalJobs: number;
  completedJobs: number;
  onStart: () => Promise<void>;
  onPause: () => Promise<void>;
  onResume: () => Promise<void>;
  onStop: () => Promise<void>;
}

export const QueueControls: React.FC<QueueControlsProps> = ({
  queueState,
  completionPercentage,
  totalJobs,
  completedJobs,
  onStart,
  onPause,
  onResume,
  onStop
}) => {
  const isRunning = queueState === 'RUNNING';
  const isPaused = queueState === 'PAUSED';
  const isStopped = queueState === 'STOPPED';

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* State Badge & Progress */}
        <div className="flex-1 min-w-[240px]">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Queue Progress</span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                isRunning ? 'bg-emerald-100 text-emerald-800' :
                isPaused ? 'bg-amber-100 text-amber-800' : 'bg-rose-100 text-rose-800'
              }`}>
                {queueState}
              </span>
            </div>
            <span className="text-xs font-bold text-slate-700">
              {completedJobs} of {totalJobs} completed ({completionPercentage}%)
            </span>
          </div>

          <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden border border-slate-200">
            <div
              className={`h-full transition-all duration-500 ${
                isRunning ? 'bg-blue-600' : isPaused ? 'bg-amber-500' : 'bg-slate-400'
              }`}
              style={{ width: `${Math.min(100, Math.max(0, completionPercentage))}%` }}
            />
          </div>
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-2">
          {isPaused ? (
            <button
              onClick={onResume}
              className="bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-xs transition cursor-pointer"
            >
              <Play className="w-3.5 h-3.5" />
              Resume Queue
            </button>
          ) : isStopped ? (
            <button
              onClick={onStart}
              className="bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-xs transition cursor-pointer"
            >
              <Play className="w-3.5 h-3.5" />
              Start Queue
            </button>
          ) : (
            <button
              onClick={onPause}
              className="bg-amber-500 hover:bg-amber-600 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-xs transition cursor-pointer"
            >
              <Pause className="w-3.5 h-3.5" />
              Pause Queue
            </button>
          )}

          <button
            onClick={onStop}
            disabled={isStopped}
            className="bg-slate-100 hover:bg-rose-50 hover:text-rose-600 text-slate-600 border border-slate-200 px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50"
          >
            <Square className="w-3.5 h-3.5" />
            Stop Queue
          </button>
        </div>
      </div>
    </div>
  );
};
