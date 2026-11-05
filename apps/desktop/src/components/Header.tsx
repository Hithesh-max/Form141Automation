import React from 'react';
import { Shield, Radio, Server, Database, Cpu, Layers, FileSpreadsheet } from 'lucide-react';
import type { SystemHealth } from '../types';
import type { AuthUser } from '../services/api';

interface HeaderProps {
  wsConnected: boolean;
  health: SystemHealth | null;
  onOpenImport: () => void;
  currentUser?: AuthUser | null;
  onLogout?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ wsConnected, health, onOpenImport, currentUser, onLogout }) => {
  const isApiOnline = health?.components.api === 'ONLINE';
  const isDbOnline = health?.components.database === 'ONLINE';
  const isRedisOnline = health?.components.redis === 'ONLINE';
  const isWorkerOnline = health?.components.worker === 'ONLINE';

  return (
    <header className="bg-slate-900 text-white border-b border-slate-800 px-6 py-3.5 shadow-md flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <div className="bg-blue-600 p-2 rounded-lg text-white shadow">
          <Shield className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            FORM 141 AUTOMATION PLATFORM
          </h1>
          <p className="text-xs text-slate-400">Automated TDS Filing & Employee-Assisted Payment Gateway</p>
        </div>
      </div>

      {/* Health Badges */}
      <div className="flex items-center gap-5 text-xs">
        <div className="flex items-center gap-3 bg-slate-800/80 px-3.5 py-1.5 rounded-full border border-slate-700">
          <div className="flex items-center gap-1.5" title={`WebSocket: ${wsConnected ? 'Connected' : 'Disconnected'}`}>
            <Radio className={`w-3.5 h-3.5 ${wsConnected ? 'text-emerald-400 animate-pulse' : 'text-rose-500'}`} />
            <span className="text-slate-300 font-medium">WS</span>
          </div>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1.5" title={`API: ${isApiOnline ? 'Online' : 'Offline'}`}>
            <Server className={`w-3.5 h-3.5 ${isApiOnline ? 'text-emerald-400' : 'text-rose-500'}`} />
            <span className="text-slate-300 font-medium">API</span>
          </div>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1.5" title={`Database: ${isDbOnline ? 'Online' : 'Offline'}`}>
            <Database className={`w-3.5 h-3.5 ${isDbOnline ? 'text-emerald-400' : 'text-rose-500'}`} />
            <span className="text-slate-300 font-medium">DB</span>
          </div>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1.5" title={`Redis: ${isRedisOnline ? 'Online' : 'Offline'}`}>
            <Layers className={`w-3.5 h-3.5 ${isRedisOnline ? 'text-emerald-400' : 'text-amber-400'}`} />
            <span className="text-slate-300 font-medium">REDIS</span>
          </div>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1.5" title={`Worker: ${isWorkerOnline ? 'Online' : 'Offline'}`}>
            <Cpu className={`w-3.5 h-3.5 ${isWorkerOnline ? 'text-emerald-400' : 'text-amber-400'}`} />
            <span className="text-slate-300 font-medium">WORKER</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {currentUser && (
            <div className="flex items-center gap-2 bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700">
              <span className="text-slate-300 font-semibold">{currentUser.username}</span>
              <span className="bg-slate-700 text-slate-300 text-[10px] px-1.5 py-0.5 rounded font-mono uppercase">{currentUser.role}</span>
              {onLogout && (
                <button
                  onClick={onLogout}
                  className="ml-1 text-slate-400 hover:text-rose-400 text-xs transition cursor-pointer"
                  title="Log out of session"
                >
                  Log out
                </button>
              )}
            </div>
          )}
          <button
            onClick={onOpenImport}
            title="Import Filings (CSV/Excel/Form 141 Multi-Customer)"
            className="bg-blue-600 hover:bg-blue-500 text-white px-3.5 py-1.5 rounded-lg font-medium shadow flex items-center gap-1.5 transition cursor-pointer text-xs"
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>Import Filings</span>
          </button>
        </div>
      </div>
    </header>
  );
};
