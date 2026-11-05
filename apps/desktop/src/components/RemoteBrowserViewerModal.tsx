import React, { useEffect, useRef, useState } from 'react';
import RFB from '@novnc/novnc/lib/rfb.js';
import { X, RefreshCw, ShieldAlert, Monitor } from 'lucide-react';

interface RemoteBrowserViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  jobId: number | null;
  jobReference?: string;
  customerName?: string;
  jobStatus?: string;
  token?: string;
  viewerUrl?: string;
}

export const RemoteBrowserViewerModal: React.FC<RemoteBrowserViewerModalProps> = ({
  isOpen,
  onClose,
  jobId,
  jobReference = '',
  customerName = '',
  jobStatus = '',
  token = '',
  viewerUrl = ''
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const rfbRef = useRef<RFB | null>(null);
  const [statusTitle, setStatusTitle] = useState('Connecting to Remote Session...');
  const [statusMsg, setStatusMsg] = useState('Establishing secure WebSocket stream to VPS display...');
  const [showOverlay, setShowOverlay] = useState(true);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!isOpen || !jobId || !containerRef.current) {
      return;
    }

    setShowOverlay(true);
    setStatusTitle('Connecting to Remote Session...');
    setStatusMsg('Establishing secure WebSocket stream to VPS display...');
    setConnected(false);

    // Determine WebSocket URL relative to origin or API endpoint
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsEndpoint = token
      ? `${protocol}//${host}/api/jobs/${jobId}/vnc-stream?token=${encodeURIComponent(token)}`
      : `${protocol}//${host}/api/jobs/${jobId}/vnc-stream`;

    let rfbInstance: RFB | null = null;
    try {
      rfbInstance = new RFB(containerRef.current, wsEndpoint, {
        wsProtocols: ['binary'],
        credentials: { password: '' }
      });

      rfbInstance.scaleViewport = true;
      rfbInstance.clipViewport = false;
      rfbInstance.resizeSession = false;

      rfbInstance.addEventListener('connect', () => {
        setConnected(true);
        setShowOverlay(false);
        if (rfbInstance?.focus) {
          rfbInstance.focus();
        }
      });

      rfbInstance.addEventListener('disconnect', (e: any) => {
        setConnected(false);
        const clean = e.detail?.clean;
        setStatusTitle('Session Disconnected');
        setStatusMsg(
          clean
            ? 'The remote browser session concluded.'
            : 'The display stream disconnected. The session may have ended or timed out.'
        );
        setShowOverlay(true);
      });

      rfbInstance.addEventListener('securityfailure', () => {
        setConnected(false);
        setStatusTitle('Authentication Error');
        setStatusMsg('VNC security handshake failed. Please obtain a fresh session token.');
        setShowOverlay(true);
      });

      rfbRef.current = rfbInstance;
    } catch (err: any) {
      setStatusTitle('Initialization Error');
      setStatusMsg(err.message || 'Failed to initialize RFB client');
      setShowOverlay(true);
    }

    return () => {
      if (rfbRef.current) {
        try {
          rfbRef.current.disconnect();
        } catch {
          // ignore disconnect errors on unmount
        }
        rfbRef.current = null;
      }
    };
  }, [isOpen, jobId, token]);

  if (!isOpen || !jobId) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex flex-col justify-center items-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl w-full max-w-6xl flex flex-col h-[85vh] overflow-hidden">
        {/* Modal Header */}
        <div className="bg-slate-900 px-6 py-3 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Monitor className="w-5 h-5 text-sky-400" />
            <span className="font-mono text-xs px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-slate-200 font-semibold">
              {jobReference || `JOB-${jobId}`}
            </span>
            {customerName && (
              <span className="text-sm font-medium text-slate-300">{customerName}</span>
            )}
            {jobStatus && (
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                {jobStatus}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`}></span>
              {connected ? 'Live Stream Active' : 'Connecting...'}
            </span>

            {viewerUrl && (
              <a
                href={viewerUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-sky-400 hover:text-sky-300 underline font-medium px-2 py-1"
              >
                Open in Window ↗
              </a>
            )}

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition-colors"
              title="Close Remote Viewer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Security Alert Banner */}
        <div className="bg-amber-950/40 border-b border-amber-900/40 px-6 py-1.5 text-xs text-amber-200/90 flex items-center gap-2 font-mono">
          <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
          <span>CONFIDENTIAL SESSION: Remote browser for Form 141 filing and payment authorization.</span>
        </div>

        {/* Screen Container */}
        <div className="relative flex-1 bg-slate-950 flex items-center justify-center overflow-hidden">
          <div ref={containerRef} className="w-full h-full flex items-center justify-center" />

          {/* Status Overlay */}
          {showOverlay && (
            <div className="absolute inset-0 bg-slate-950/90 backdrop-blur-xs flex flex-col items-center justify-center p-6 text-center z-10">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 max-w-md shadow-2xl flex flex-col items-center">
                <RefreshCw className={`w-8 h-8 text-sky-400 mb-4 ${!connected && showOverlay ? 'animate-spin' : ''}`} />
                <h3 className="text-base font-semibold text-slate-100">{statusTitle}</h3>
                <p className="text-xs text-slate-400 mt-2 leading-relaxed">{statusMsg}</p>
                <button
                  onClick={onClose}
                  className="mt-6 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition-colors"
                >
                  Close Viewer
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
