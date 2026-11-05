import React, { useState, useRef } from 'react';
import type { ImportPreviewResponse, Form141CustomerPreview } from '../types';
import { UploadCloud, XCircle, FileSpreadsheet, X, ArrowRight, ShieldCheck, Info } from 'lucide-react';
import { Form141PreviewModal } from './Form141PreviewModal';
import { apiFetch } from '../services/api';

interface ImportWizardModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: () => void;
}

export const ImportWizardModal: React.FC<ImportWizardModalProps> = ({
  isOpen,
  onClose,
  onImportComplete
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [importing, setImporting] = useState(false);
  const [previewCustomer, setPreviewCustomer] = useState<Form141CustomerPreview | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setLoading(true);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await apiFetch('/api/import/preview', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        setPreviewData(data);
        setMapping(data.suggested_mapping || {});
      } else {
        alert(`Error previewing file: ${data.detail}`);
      }
    } catch (err) {
      alert(`Network error: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!file) return;
    setImporting(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('mapping', JSON.stringify(mapping));
    formData.append('import_valid_only', 'true');

    try {
      const res = await apiFetch('/api/import/confirm', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        alert(`Successfully imported ${data.jobs_created} filing jobs in Ready status!`);
        onImportComplete();
        onClose();
      } else {
        alert(`Import failed: ${data.detail}`);
      }
    } catch (err) {
      alert(`Network error: ${err}`);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-blue-100 text-blue-700">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Import Client Filing Data</h2>
              <p className="text-xs text-slate-500">Upload Excel (.xlsx) or CSV containing Form 141 filing records</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-200 transition cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {!previewData ? (
            /* Upload Box */
            <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center bg-slate-50/50 hover:bg-blue-50/30 transition flex flex-col items-center">
              <input
                type="file"
                ref={fileInputRef}
                accept=".xlsx,.csv,.xls"
                className="hidden"
                onChange={handleFileSelect}
              />
              <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mb-3">
                <UploadCloud className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-slate-800">
                {file ? file.name : 'Select an Excel or CSV file'}
              </h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm">
                The file will be safely parsed and checked for valid PAN format, non-negative amounts, and required fields before importing.
              </p>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                className="mt-4 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition cursor-pointer disabled:opacity-50"
              >
                {loading ? 'Analyzing File...' : 'Choose File'}
              </button>
            </div>
          ) : (
            /* Validation Results & Preview */
            <div className="space-y-4">
              {/* Summary Cards */}
              <div className="grid grid-cols-4 gap-2 text-center text-xs">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <div className="text-slate-500 font-medium">
                    {previewData.is_form141 ? 'Customers' : 'Rows Detected'}
                  </div>
                  <div className="text-xl font-black text-slate-800 mt-0.5">{previewData.total_rows}</div>
                </div>
                <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200">
                  <div className="text-emerald-700 font-medium">Valid</div>
                  <div className="text-xl font-black text-emerald-800 mt-0.5">{previewData.valid_count}</div>
                </div>
                <div className="p-3 bg-rose-50 rounded-xl border border-rose-200">
                  <div className="text-rose-700 font-medium">Errors</div>
                  <div className="text-xl font-black text-rose-800 mt-0.5">{previewData.error_count}</div>
                </div>
                <div className="p-3 bg-amber-50 rounded-xl border border-amber-200">
                  <div className="text-amber-700 font-medium">Warnings</div>
                  <div className="text-xl font-black text-amber-800 mt-0.5">{previewData.warning_count}</div>
                </div>
              </div>

              {/* Column Mapping Preview */}
              <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/50">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-blue-600" />
                  {previewData.is_form141 ? 'Form 141 Multi-Customer Structure' : 'Auto-Detected Column Mapping'}
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  {Object.entries(mapping).map(([field, col]) => (
                    <div key={field} className="p-2 rounded bg-white border border-slate-200">
                      <div className="text-[10px] uppercase font-bold text-slate-400">{field.replace(/_/g, ' ')}</div>
                      <div className="font-mono text-[11px] font-semibold text-slate-800 truncate">{col || '<Not Found>'}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Form 141 Customers Preview */}
              {previewData.is_form141 && previewData.customers && previewData.customers.length > 0 && (
                <div className="p-3.5 rounded-xl border border-blue-200 bg-blue-50/40">
                  <h4 className="text-xs font-bold text-blue-900 uppercase tracking-wider mb-2 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-blue-600" />
                      Detected Customer Filings ({previewData.customers.length})
                    </span>
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs max-h-48 overflow-y-auto">
                    {previewData.customers.map((c) => (
                      <div key={c.customerIndex} className="p-2 rounded-lg bg-white border border-slate-200 flex items-center justify-between">
                        <div>
                          <span className="font-bold text-slate-800">{c.customerLabel}</span>
                          <span className="text-[10px] text-slate-400 ml-1.5 font-mono">Index #{c.customerIndex}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${c.status === 'READY' ? 'bg-emerald-100 text-emerald-800' :
                              c.status === 'WARNING' ? 'bg-amber-100 text-amber-800' :
                                'bg-rose-100 text-rose-800'
                            }`}>
                            {c.status}
                          </span>
                          <button
                            type="button"
                            onClick={() => setPreviewCustomer(c)}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition cursor-pointer"
                            title="View read-only Form 141 preview for this customer"
                          >
                            <Info className="w-3 h-3" />
                            <span>More Info</span>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Errors List */}
              {previewData.errors.length > 0 && (
                <div className="border border-rose-200 rounded-xl overflow-hidden">
                  <div className="bg-rose-50 px-3 py-2 border-b border-rose-200 font-bold text-xs text-rose-800 flex items-center gap-1.5">
                    <XCircle className="w-4 h-4 text-rose-600" /> Validation Errors ({previewData.errors.length})
                  </div>
                  <div className="max-h-40 overflow-y-auto divide-y divide-rose-100 text-xs">
                    {previewData.errors.map((err, i) => (
                      <div key={i} className="px-3 py-2 flex items-center justify-between text-rose-700">
                        <span className="font-bold">Row {err.row}</span>
                        <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-rose-100">{err.field}</span>
                        <span className="truncate flex-1 ml-3">{err.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <button
            onClick={() => {
              setPreviewData(null);
              setFile(null);
            }}
            disabled={!previewData || importing}
            className="text-xs text-slate-500 hover:text-slate-800 font-medium cursor-pointer disabled:opacity-0"
          >
            Choose Different File
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-200 rounded-lg transition cursor-pointer"
            >
              Cancel
            </button>
            {previewData && (
              <button
                onClick={handleConfirmImport}
                disabled={importing || previewData.valid_count === 0}
                className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {importing ? 'Importing...' : `Import ${previewData.valid_count} Valid Records`}
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Read-Only Form 141 Customer Preview Modal */}
      <Form141PreviewModal
        isOpen={Boolean(previewCustomer)}
        customer={previewCustomer}
        onClose={() => setPreviewCustomer(null)}
      />
    </div>
  );
};
