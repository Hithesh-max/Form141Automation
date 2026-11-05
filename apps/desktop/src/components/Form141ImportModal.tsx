import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Upload, X, CheckCircle2, AlertTriangle, XCircle, 
  FileSpreadsheet, Users, Loader2, Lock, Play, RefreshCw, Eye, Ban, Info
} from 'lucide-react';
import type { Form141FieldMeta, Form141CustomerPreview, Form141ActiveLock } from '../types';
import { Form141PreviewModal } from './Form141PreviewModal';
import { apiFetch } from '../services/api';

export function Form141ImportModal({ isOpen, onClose, onImportComplete }: {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: () => void;
}) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<any>(null);
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<any>(null);
  
  // Matrix workspace state
  const [activeLock, setActiveLock] = useState<Form141ActiveLock | null>(null);
  const [startingIndex, setStartingIndex] = useState<number | null>(null);
  const [cellSearch, setCellSearch] = useState('');
  const [selectedCustomerIndex, setSelectedCustomerIndex] = useState<number | null>(null);
  const [previewCustomer, setPreviewCustomer] = useState<Form141CustomerPreview | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  // Fetch strict concurrency lock status
  const fetchActiveLock = useCallback(async () => {
    try {
      const res = await apiFetch('/api/jobs/active-lock');
      if (res.ok) {
        const data: Form141ActiveLock = await res.json();
        setActiveLock(data);
      }
    } catch (err) {
      console.debug('Failed to fetch active lock status:', err);
    }
  }, []);

  useEffect(() => {
    if (isOpen && step === 2) {
      fetchActiveLock();
      const interval = setInterval(fetchActiveLock, 3000);
      return () => clearInterval(interval);
    }
  }, [isOpen, step, fetchActiveLock]);

  const handleFileUpload = async (selectedFile: File) => {
    if (!selectedFile.name.endsWith('.xlsx')) {
      setError('Please select a valid .xlsx file.');
      return;
    }
    setFile(selectedFile);
    setError(null);
    setIsLoading(true);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await apiFetch('/api/import/form141/preview', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        throw new Error('Failed to parse file. Please check the format.');
      }
      const data = await response.json();
      setPreviewData(data);
      
      // Auto-select READY and WARNING
      const initialSelected = new Set<number>();
      data.customers.forEach((c: any) => {
        if (c.status === 'READY' || c.status === 'WARNING') {
          initialSelected.add(c.customerIndex);
        }
      });
      setSelectedIndices(initialSelected);
      setStep(2);
    } catch (err: any) {
      setError(err.message || 'An error occurred during file parsing.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      handleFileUpload(droppedFile);
    }
  };

  const handleConfirmImport = async () => {
    if (!file || selectedIndices.size === 0) return;
    setIsLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('selectedIndices', JSON.stringify(Array.from(selectedIndices)));

    try {
      const response = await apiFetch('/api/import/form141/confirm', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        throw new Error('Import failed. Please try again.');
      }
      const result = await response.json();
      setImportResult(result);
      setStep(3);
    } catch (err: any) {
      setError(err.message || 'An error occurred during import.');
    } finally {
      setIsLoading(false);
    }
  };

  // Start a single filing directly from matrix column
  const handleStartFiling = async (customer: Form141CustomerPreview) => {
    if (!customer) return;
    setStartingIndex(customer.customerIndex);
    setError(null);

    try {
      if (!customer.jobId) {
        if (!file) throw new Error('Source file missing. Please re-upload.');
        const formData = new FormData();
        formData.append('file', file);
        formData.append('selectedIndices', JSON.stringify([customer.customerIndex]));

        const confirmRes = await apiFetch('/api/import/form141/confirm', {
          method: 'POST',
          body: formData,
        });
        if (!confirmRes.ok) {
          const errJson = await confirmRes.json().catch(() => ({}));
          throw new Error(errJson.detail || 'Failed to save customer filing before start.');
        }

        const confirmData = await confirmRes.json();
        if (confirmData.job_ids && confirmData.job_ids.length > 0) {
          customer.jobId = confirmData.job_ids[0];
        } else {
          const jobsRes = await apiFetch('/api/jobs/?limit=5');
          if (jobsRes.ok) {
            const jobsData = await jobsRes.json();
            const found = jobsData.items?.find((j: any) => 
              j.customer_name === customer.customerLabel || 
              (customer.values?.deductorPan && j.pan_masked?.includes(customer.values.deductorPan.substring(0, 2)))
            );
            if (found) {
              customer.jobId = found.id;
            }
          }
        }
      }

      if (customer.jobId) {
        const startRes = await apiFetch(`/api/jobs/${customer.jobId}/start`, {
          method: 'POST',
        });
        if (startRes.status === 409) {
          const conflictData = await startRes.json();
          throw new Error(conflictData.detail?.message || 'Another filing is currently active.');
        }
        if (!startRes.ok) {
          const errData = await startRes.json().catch(() => ({}));
          throw new Error(errData.detail || 'Failed to start filing automation.');
        }
      }

      await fetchActiveLock();
      onImportComplete();
    } catch (err: any) {
      setError(err.message || 'Failed to start filing.');
    } finally {
      setStartingIndex(null);
    }
  };

  const toggleCustomerSelected = (index: number) => {
    const next = new Set(selectedIndices);
    if (next.has(index)) {
      next.delete(index);
    } else {
      next.add(index);
    }
    setSelectedIndices(next);
  };

  const handleSelectAllReady = () => {
    if (!previewData) return;
    const next = new Set<number>();
    previewData.customers.forEach((c: Form141CustomerPreview) => {
      if (c.status === 'READY' || c.status === 'WARNING' || c.status === 'VALIDATION_REQUIRED') {
        next.add(c.customerIndex);
      }
    });
    setSelectedIndices(next);
  };

  const handleDeselectAll = () => {
    setSelectedIndices(new Set());
  };

  const getFetchTypeBadge = (type: string) => {
    switch (type) {
      case 'Manual': return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'Select': return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'Fetch': return 'bg-slate-100 text-slate-700 border-slate-200';
      case 'Calculate': return 'bg-teal-50 text-teal-700 border-teal-200';
      case 'Validate': return 'bg-indigo-50 text-indigo-700 border-indigo-200';
      case 'Conditional Input': return 'bg-amber-50 text-amber-800 border-amber-200';
      default: return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'READY':
        return <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800"><CheckCircle2 className="w-3 h-3 mr-1" /> READY</span>;
      case 'VALIDATION_REQUIRED':
      case 'WARNING':
        return <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800"><AlertTriangle className="w-3 h-3 mr-1" /> WARNING</span>;
      case 'INVALID':
      case 'ERROR':
        return <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800"><XCircle className="w-3 h-3 mr-1" /> INVALID</span>;
      case 'PROCESSING':
        return <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> ACTIVE</span>;
      case 'PREVIEW_PENDING':
        return <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-100 text-purple-800"><Eye className="w-3 h-3 mr-1" /> PREVIEW</span>;
      case 'PAYMENT_PENDING':
        return <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800"><AlertTriangle className="w-3 h-3 mr-1" /> PAYMENT</span>;
      case 'SESSION_LOST':
        return <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 border border-slate-300"><Ban className="w-3 h-3 mr-1" /> SESSION LOST</span>;
      case 'CANCELLED':
        return <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-300"><Ban className="w-3 h-3 mr-1" /> CANCELLED</span>;
      case 'COMPLETED':
        return <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-green-100 text-green-800"><CheckCircle2 className="w-3 h-3 mr-1" /> DONE</span>;
      default:
        return <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">{status}</span>;
    }
  };

  const maskValue = (fieldKey: string, fieldLabel: string, value: any) => {
    if (value === null || value === undefined || value === '') return '';
    const str = String(value).trim();
    if (fieldKey.toLowerCase().includes('password') || fieldLabel.toLowerCase().includes('password')) {
      return '••••••••';
    }
    if (fieldKey.toLowerCase().endsWith('pan') || fieldLabel.toLowerCase().includes('pan')) {
      if (str.length === 10) {
        return `${str.substring(0, 2)}*****${str.substring(8)}`;
      }
      return str.length > 4 ? `${str.substring(0, 2)}****` : '****';
    }
    return str;
  };

  const renderStep1 = () => (
    <div className="p-12 flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-xl bg-gray-50 m-6 transition-colors hover:bg-gray-100 hover:border-gray-400"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
    >
      <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mb-4">
        <Upload className="w-8 h-8" />
      </div>
      <h3 className="text-xl font-bold text-gray-900 mb-2">Upload Form 141 Multi-Customer Excel</h3>
      <p className="text-gray-500 mb-6 text-center max-w-lg text-sm">
        Upload your grouped Form 141 template with columns <code>TYPE</code>, <code>Form 141 Field</code>, <code>Fetch Type</code>, followed by dynamic customer filing columns.
      </p>
      <input
        type="file"
        ref={fileInputRef}
        onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
        accept=".xlsx"
        className="hidden"
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={isLoading}
        className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center shadow-sm"
      >
        {isLoading ? <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Analyzing Template...</> : 'Select Excel File (.xlsx)'}
      </button>
      {error && (
        <div className="mt-4 text-red-600 text-sm flex items-center bg-red-50 p-3 rounded-lg border border-red-200">
          <AlertTriangle className="w-4 h-4 mr-2 shrink-0" /> {error}
        </div>
      )}
    </div>
  );

  const renderStep2 = () => {
    if (!previewData) return null;

    const fields: Form141FieldMeta[] = previewData.fields || [];
    const customers: Form141CustomerPreview[] = previewData.customers || [];

    const filteredFields = fields.filter(f => 
      f.fieldLabel.toLowerCase().includes(cellSearch.toLowerCase()) ||
      f.type.toLowerCase().includes(cellSearch.toLowerCase()) ||
      f.fetchType.toLowerCase().includes(cellSearch.toLowerCase())
    );

    return (
      <div className="flex flex-col h-full overflow-hidden">
        {/* Top Summary Bar */}
        <div className="bg-gray-50 border-b p-3 px-6 shrink-0 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <FileSpreadsheet className="w-5 h-5 text-green-600" />
            <span className="font-semibold text-gray-800">{previewData.filename}</span>
            <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded font-mono">
              {fields.length} Fields × {customers.length} Filings
            </span>
          </div>
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-1.5 text-xs bg-white px-2.5 py-1 rounded-full shadow-sm border border-gray-200">
              <Users className="w-3.5 h-3.5 text-blue-500" />
              <span className="font-bold">{previewData.totalCustomers}</span>
              <span className="text-gray-500">Filings</span>
            </div>
            <div className="flex items-center space-x-1.5 text-xs bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200 text-emerald-800">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span className="font-bold">{previewData.readyCount}</span> Ready
            </div>
            <div className="flex items-center space-x-1.5 text-xs bg-amber-50 px-2.5 py-1 rounded-full border border-amber-200 text-amber-800">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
              <span className="font-bold">{previewData.warningCount}</span> Warnings
            </div>
            {previewData.errorCount > 0 && (
              <div className="flex items-center space-x-1.5 text-xs bg-rose-50 px-2.5 py-1 rounded-full border border-rose-200 text-rose-800">
                <XCircle className="w-3.5 h-3.5 text-rose-600" />
                <span className="font-bold">{previewData.errorCount}</span> Invalid
              </div>
            )}
          </div>
        </div>

        {/* Active Concurrency Lock Banner */}
        {activeLock?.has_active_job && (
          <div className="bg-amber-50 border-b border-amber-200 px-6 py-2.5 flex items-center justify-between text-amber-900 text-xs shrink-0">
            <div className="flex items-center space-x-2">
              <Lock className="w-4 h-4 text-amber-600 shrink-0" />
              <span className="font-bold uppercase tracking-wider text-[11px] bg-amber-200/80 px-1.5 py-0.5 rounded text-amber-900">
                Concurrency Lock Active
              </span>
              <span>
                Filing <strong>{activeLock.active_job?.job_reference}</strong> ({activeLock.active_job?.customer_name}) is currently in status <strong>{activeLock.active_job?.status}</strong>.
                Form 141 enforces <strong>MAX_ACTIVE_FORM141_JOBS = 1</strong>. Other filings cannot start until this filing completes or is cancelled.
              </span>
            </div>
            <div className="flex items-center space-x-2 shrink-0 ml-4">
              <button
                onClick={fetchActiveLock}
                className="text-amber-800 hover:text-amber-900 p-1 hover:bg-amber-100 rounded transition-colors"
                title="Refresh Lock Status"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* Filter Toolbar */}
        <div className="bg-white border-b px-6 py-2 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-4">
            <input
              type="text"
              placeholder="Search section, field name, or fetch type..."
              value={cellSearch}
              onChange={(e) => setCellSearch(e.target.value)}
              className="text-xs px-3 py-1.5 border border-gray-300 rounded-md w-72 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {cellSearch && (
              <span className="text-xs text-gray-500">
                Showing {filteredFields.length} of {fields.length} rows
              </span>
            )}
          </div>
          <div className="text-xs text-gray-500 flex items-center space-x-3">
            <span>Scroll horizontally to view all customer filing columns</span>
          </div>
        </div>

        {/* Matrix Grid: Left 3 columns sticky, dynamic customer columns scrollable */}
        <div className="flex-1 overflow-auto bg-gray-100">
          <table className="border-collapse table-fixed w-full text-xs text-left">
            <thead className="bg-gray-50 border-b border-gray-200 sticky top-0 z-30 shadow-sm">
              <tr>
                {/* Column 1: TYPE (Sticky Left 0) */}
                <th className="sticky left-0 z-40 bg-gray-100 border-r border-gray-200 w-48 px-3 py-3 font-bold text-gray-700 uppercase tracking-wider text-[11px]">
                  TYPE (Section)
                </th>

                {/* Column 2: Form 141 Field (Sticky Left 192px) */}
                <th className="sticky left-48 z-40 bg-gray-100 border-r border-gray-200 w-64 px-3 py-3 font-bold text-gray-700 uppercase tracking-wider text-[11px]">
                  Form 141 Field
                </th>

                {/* Column 3: Fetch Type (Sticky Left 448px) */}
                <th className="sticky left-[448px] z-40 bg-gray-100 border-r border-gray-300 w-32 px-3 py-3 font-bold text-gray-700 uppercase tracking-wider text-[11px] shadow-[2px_0_4px_rgba(0,0,0,0.04)]">
                  Fetch Type
                </th>

                {/* Dynamic Customer / Filing Columns */}
                {customers.map((cust) => {
                  const isSelected = selectedIndices.has(cust.customerIndex);
                  const isLocked = activeLock?.has_active_job;
                  const isInvalid = cust.status === 'INVALID' || cust.status === 'ERROR';
                  const canStart = !isLocked && !isInvalid;

                  return (
                    <th 
                      key={cust.customerIndex} 
                      onClick={() => setSelectedCustomerIndex(cust.customerIndex)}
                      className={`border-r border-gray-200 w-64 px-3 py-2.5 align-top transition-colors cursor-pointer ${
                        selectedCustomerIndex === cust.customerIndex ? 'bg-blue-50/70' : 'bg-gray-50'
                      }`}
                    >
                      <div className="flex flex-col space-y-1.5">
                        <div className="flex items-center justify-between">
                          <label className="flex items-center space-x-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleCustomerSelected(cust.customerIndex)}
                              disabled={isInvalid}
                              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
                            />
                            <span className="font-bold text-gray-900 truncate max-w-[140px]" title={cust.customerLabel}>
                              {cust.customerLabel}
                            </span>
                          </label>
                          {getStatusBadge(cust.status)}
                        </div>

                        {/* Customer Actions: More Info & Start Filing */}
                        <div className="flex items-center justify-between pt-1 gap-1">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setPreviewCustomer(cust);
                            }}
                            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition cursor-pointer"
                            title="View read-only Form 141 preview for this customer"
                          >
                            <Info className="w-3 h-3" />
                            <span>More Info</span>
                          </button>
                          <button
                            onClick={() => handleStartFiling(cust)}
                            disabled={!canStart || startingIndex === cust.customerIndex}
                            title={
                              isLocked 
                                ? `Locked: Another filing (${activeLock?.active_job?.job_reference}) is currently active`
                                : isInvalid 
                                ? 'Cannot start: Customer filing contains validation errors'
                                : 'Start automated filing for this customer'
                            }
                            className={`px-2.5 py-1 rounded text-[11px] font-semibold flex items-center space-x-1 transition-all shadow-xs ${
                              canStart
                                ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer active:scale-95'
                                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            }`}
                          >
                            {startingIndex === cust.customerIndex ? (
                              <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Starting...</>
                            ) : (
                              <><Play className="w-3 h-3 mr-1 fill-current" /> Start Filing</>
                            )}
                          </button>
                        </div>

                        {/* Error / Warning summary in header if any */}
                        {cust.errors && cust.errors.length > 0 && (
                          <div className="text-[10px] text-rose-700 bg-rose-50 p-1 rounded border border-rose-100 flex items-center">
                            <XCircle className="w-3 h-3 mr-1 shrink-0 text-rose-500" />
                            <span className="truncate" title={cust.errors[0]?.message}>
                              {cust.errors[0]?.message}
                            </span>
                          </div>
                        )}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredFields.map((fieldMeta, fIdx) => {
                const isEven = fIdx % 2 === 0;
                const rowBg = isEven ? 'bg-white' : 'bg-gray-50/50';

                return (
                  <tr key={`${fieldMeta.sectionKey}-${fieldMeta.fieldKey}-${fIdx}`} className={`hover:bg-blue-50/40 transition-colors ${rowBg}`}>
                    {/* Sticky Left Col 1: TYPE */}
                    <td className={`sticky left-0 z-20 border-r border-gray-200 px-3 py-2 font-medium text-gray-700 text-[11px] truncate w-48 ${rowBg}`}>
                      {fieldMeta.type}
                    </td>

                    {/* Sticky Left Col 2: Form 141 Field */}
                    <td className={`sticky left-48 z-20 border-r border-gray-200 px-3 py-2 font-semibold text-gray-900 text-xs truncate w-64 ${rowBg}`} title={fieldMeta.fieldLabel}>
                      {fieldMeta.fieldLabel}
                    </td>

                    {/* Sticky Left Col 3: Fetch Type */}
                    <td className={`sticky left-[448px] z-20 border-r border-gray-300 px-3 py-2 w-32 shadow-[2px_0_4px_rgba(0,0,0,0.04)] ${rowBg}`}>
                      <span className={`inline-block text-[10px] px-2 py-0.5 rounded font-medium border ${getFetchTypeBadge(fieldMeta.fetchType)}`}>
                        {fieldMeta.fetchType || 'Manual'}
                      </span>
                    </td>

                    {/* Customer Value Cells */}
                    {customers.map((cust) => {
                      const secData = cust.sections?.[fieldMeta.sectionKey] || {};
                      const fieldData = secData[fieldMeta.fieldKey];
                      const rawVal = fieldData?.value !== undefined ? fieldData.value : (cust.values?.[fieldMeta.fieldKey] ?? '');
                      const dispVal = maskValue(fieldMeta.fieldKey, fieldMeta.fieldLabel, rawVal);

                      const fieldError = cust.errors?.find(e => e.field === fieldMeta.fieldKey || e.field === fieldMeta.fieldLabel);
                      const fieldWarning = cust.warnings?.find(w => w.field === fieldMeta.fieldKey || w.field === fieldMeta.fieldLabel);

                      return (
                        <td 
                          key={`${cust.customerIndex}-${fieldMeta.fieldKey}`} 
                          className={`border-r border-gray-200 px-3 py-2 w-64 text-xs align-middle transition-colors ${
                            fieldError ? 'bg-rose-50 text-rose-900 font-semibold' :
                            fieldWarning ? 'bg-amber-50 text-amber-900' :
                            'text-gray-800'
                          }`}
                          title={fieldError ? fieldError.message : fieldWarning ? fieldWarning.message : String(rawVal)}
                        >
                          <div className="flex items-center justify-between">
                            <span className="truncate max-w-[200px]">
                              {dispVal || <span className="text-gray-300 italic">Empty</span>}
                            </span>
                            {fieldError && <XCircle className="w-3.5 h-3.5 text-rose-500 shrink-0 ml-1" />}
                            {fieldWarning && !fieldError && <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 ml-1" />}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Bottom Action Footer */}
        <div className="bg-white border-t p-3 px-6 shrink-0 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <button onClick={handleSelectAllReady} className="text-xs text-blue-600 hover:text-blue-800 font-medium px-2 py-1 rounded hover:bg-blue-50 transition-colors">
              Select All Ready/Warnings
            </button>
            <div className="w-px h-4 bg-gray-300"></div>
            <button onClick={handleDeselectAll} className="text-xs text-gray-600 hover:text-gray-800 font-medium px-2 py-1 rounded hover:bg-gray-100 transition-colors">
              Deselect All
            </button>
            <span className="text-xs text-gray-500 ml-2 bg-gray-100 px-2.5 py-1 rounded-full">
              <strong className="text-gray-900">{selectedIndices.size}</strong> filings selected
            </span>
          </div>

          <div className="flex items-center space-x-4">
            {error && (
              <span className="text-xs text-red-600 flex items-center bg-red-50 px-2 py-1 rounded border border-red-200">
                <AlertTriangle className="w-3.5 h-3.5 mr-1 text-red-500 shrink-0" /> {error}
              </span>
            )}
            <button 
              onClick={handleConfirmImport} 
              disabled={selectedIndices.size === 0 || isLoading}
              className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg font-semibold text-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center shadow-sm"
            >
              {isLoading ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Importing Records...</>
              ) : (
                `Import ${selectedIndices.size} Filings to Dashboard`
              )}
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderStep3 = () => (
    <div className="p-12 flex flex-col items-center justify-center text-center">
      <div className="w-20 h-20 bg-green-100 text-green-600 rounded-full flex items-center justify-center mb-6">
        <CheckCircle2 className="w-10 h-10" />
      </div>
      <h3 className="text-2xl font-bold text-gray-900 mb-2">Form 141 Import Successful!</h3>
      <p className="text-gray-600 mb-6 max-w-md text-sm">
        Successfully imported <span className="font-semibold text-gray-900">{importResult?.jobs_created || 0}</span> Form 141 filings.
        Under the strict single-filing concurrency policy (MAX_ACTIVE_FORM141_JOBS = 1), you can now start each filing individually from the dashboard.
      </p>
      <button
        onClick={() => {
          onImportComplete();
          onClose();
        }}
        className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-2.5 rounded-lg font-semibold transition-colors text-sm shadow-sm"
      >
        Go to Dashboard
      </button>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-2 sm:p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-[96vw] h-[92vh] overflow-hidden flex flex-col relative border border-gray-200">
        
        {/* Header */}
        <div className="bg-white border-b px-6 py-3.5 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-gray-900">Form 141 Multi-Customer Matrix Workspace</h2>
              <p className="text-xs text-gray-500">
                {step === 1 ? 'Step 1 of 3: Upload Excel Template' : step === 2 ? 'Step 2 of 3: Matrix Grid Review & Individual Filing Execution' : 'Step 3 of 3: Import Complete'}
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 hover:bg-gray-100 p-1.5 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
      </div>

      {/* Dynamic Form 141 More Info Preview Modal */}
      <Form141PreviewModal
        isOpen={Boolean(previewCustomer)}
        customer={previewCustomer}
        onClose={() => setPreviewCustomer(null)}
      />
    </div>
  );
}

