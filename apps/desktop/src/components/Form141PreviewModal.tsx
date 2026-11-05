import React, { useMemo } from 'react';
import {
  X,
  FileSpreadsheet,
  XCircle,
  AlertTriangle,
  ShieldAlert
} from 'lucide-react';
import type { Form141CustomerPreview, Form141ExtractedField } from '../types';

interface Form141PreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  customer: Form141CustomerPreview | null;
}

export const Form141PreviewModal: React.FC<Form141PreviewModalProps> = ({
  isOpen,
  onClose,
  customer
}) => {

  // Group fields strictly by original Excel TYPE preserving exact order
  const { groupedFields, totalRendered } = useMemo(() => {
    if (!customer?.fields || customer.fields.length === 0) {
      return { groupedFields: [], totalRendered: 0 };
    }

    const groups: { type: string; fields: Form141ExtractedField[] }[] = [];
    const seenTypes = new Set<string>();

    for (const f of customer.fields) {
      if (!seenTypes.has(f.type)) {
        seenTypes.add(f.type);
        groups.push({ type: f.type, fields: [] });
      }
      const g = groups.find((grp) => grp.type === f.type);
      if (g) {
        g.fields.push(f);
      }
    }

    const count = groups.reduce((acc, g) => acc + g.fields.length, 0);
    return { groupedFields: groups, totalRendered: count };
  }, [customer]);

  if (!isOpen || !customer) return null;

  const custLabel = customer.customer_label || customer.customerLabel;
  const custIndex = customer.customer_index || customer.customerIndex;
  const custCol = customer.source_column || (customer.fields?.[0]?.source_column ?? 'D');

  const getFetchTypeBadge = (fetchType?: string) => {
    const ft = (fetchType || 'Manual').toLowerCase();
    if (ft.includes('fetch')) {
      return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-blue-100 text-blue-800 border border-blue-200">Autofetch</span>;
    }
    if (ft.includes('calc')) {
      return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-purple-100 text-purple-800 border border-purple-200">Calculated</span>;
    }
    if (ft.includes('select')) {
      return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">Select</span>;
    }
    if (ft.includes('conditional')) {
      return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-amber-100 text-amber-800 border border-amber-200">Conditional</span>;
    }
    if (ft.includes('validate')) {
      return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-cyan-100 text-cyan-800 border border-cyan-200">Validate</span>;
    }
    return <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-slate-100 text-slate-700 border border-slate-200">Manual</span>;
  };

  const renderFieldValue = (f: Form141ExtractedField) => {
    // 1. Password/Sensitive Protection
    if (f.is_sensitive) {
      return (
        <span className="font-mono text-xs tracking-widest bg-slate-100 px-2 py-0.5 rounded text-slate-700 border border-slate-200">
          ••••••••
        </span>
      );
    }

    // 2. Numeric 0 Rule: Must remain 0 and display as 0
    if (f.value === 0 || f.value === '0') {
      return <span className="font-mono font-bold text-slate-900">0</span>;
    }

    // 3. Real Value Exists
    if (f.value !== null && f.value !== undefined && f.value !== '') {
      return <span className="font-mono font-semibold text-slate-900 break-all">{String(f.value)}</span>;
    }

    // 4. Blank Field Rules based on Fetch Type
    const ftLower = (f.fetch_type || '').toLowerCase();
    if (ftLower.includes('fetch')) {
      return <span className="text-blue-600 font-medium italic text-xs">Pending portal autofetch</span>;
    }
    if (ftLower.includes('calc')) {
      return <span className="text-purple-600 font-medium italic text-xs">Pending calculation</span>;
    }
    if (ftLower.includes('select')) {
      return <span className="text-slate-500 font-medium italic text-xs">Not selected</span>;
    }
    if (ftLower.includes('conditional')) {
      return <span className="text-amber-700 font-medium italic text-xs">Not applicable unless condition is selected</span>;
    }
    return <span className="text-slate-400 font-normal italic text-xs">Not provided</span>;
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[92vh] flex flex-col border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-600 text-white rounded-xl shadow-sm">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900">{custLabel}</h2>
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
                  Column {custCol}
                </span>
                <span className="text-xs font-normal text-slate-500 font-mono">
                  (Index #{custIndex})
                </span>
                <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${customer.status === 'READY' ? 'bg-emerald-100 text-emerald-800' :
                    customer.status === 'WARNING' ? 'bg-amber-100 text-amber-800' :
                      'bg-rose-100 text-rose-800'
                  }`}>
                  {customer.status}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {/* Dynamic Form 141 structure preview &bull; Source of truth: Excel workbook */}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded-lg transition cursor-pointer"
              title="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>


        {/* Validation Errors & Warnings */}
        {Boolean((customer.errors && customer.errors.length > 0) || (customer.warnings && customer.warnings.length > 0)) && (
          <div className="p-4 border-b border-slate-200 bg-slate-50 space-y-2">
            {customer.errors && customer.errors.length > 0 && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl space-y-1">
                <div className="font-bold text-xs text-rose-800 flex items-center gap-1.5">
                  <XCircle className="w-4 h-4 text-rose-600" />
                  Validation Errors ({customer.errors.length})
                </div>
                <ul className="text-xs text-rose-700 list-disc list-inside space-y-0.5">
                  {customer.errors.map((e, idx) => (
                    <li key={idx}><strong className="font-mono">{e.field}:</strong> {e.message}</li>
                  ))}
                </ul>
              </div>
            )}
            {customer.warnings && customer.warnings.length > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-1">
                <div className="font-bold text-xs text-amber-800 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  Validation Warnings ({customer.warnings.length})
                </div>
                <ul className="text-xs text-amber-700 list-disc list-inside space-y-0.5">
                  {customer.warnings.map((w, idx) => (
                    <li key={idx}><strong className="font-mono">{w.field}:</strong> {w.message}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Body - Grouped strictly by Excel TYPE headings */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/50">
          {(!customer.fields || customer.fields.length === 0) ? (
            <div className="p-12 text-center text-slate-500 bg-white rounded-2xl border border-slate-200 shadow-sm space-y-2">
              <ShieldAlert className="w-8 h-8 text-slate-400 mx-auto" />
              <p className="font-semibold text-slate-700 text-sm">No extracted fields available for this customer.</p>
              <p className="text-xs text-slate-400">Please re-upload the workbook to re-extract all fields.</p>
            </div>
          ) : (
            groupedFields.map((group) => (
              <div key={group.type} className="space-y-2.5">
                {/* Section Heading from exact Excel TYPE */}
                <div className="flex items-center justify-between border-b border-slate-200 pb-1.5">
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-600"></span>
                    <span>{group.type}</span>
                  </h3>
                  <span className="text-[11px] font-semibold text-slate-500 bg-white px-2 py-0.5 rounded-full border border-slate-200">
                    {group.fields.length} {group.fields.length === 1 ? 'field' : 'fields'}
                  </span>
                </div>

                {/* Grid of Fields in exact Excel row order */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {group.fields.map((field) => (
                    <div
                      key={`${field.original_row_number}-${field.form141_field}`}
                      className="p-3 bg-white rounded-xl border border-slate-200 hover:border-slate-300 transition-shadow shadow-xs flex flex-col justify-between"
                    >
                      {/* Top: Field Label and Row # */}
                      <div>
                        <div className="flex items-start justify-between gap-1.5 mb-1.5">
                          <span
                            className="text-xs font-semibold text-slate-700 leading-tight"
                            title={field.form141_field}
                          >
                            {field.form141_field}
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono shrink-0">
                            Row #{field.original_row_number}
                          </span>
                        </div>

                        {/* Middle: Value */}
                        <div className="min-h-[28px] flex items-center bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-100">
                          {renderFieldValue(field)}
                        </div>
                      </div>

                      {/* Bottom: Fetch Type Badge & Column */}
                      <div className="flex items-center justify-between pt-2 mt-2 border-t border-slate-100">
                        {getFetchTypeBadge(field.fetch_type)}
                        <span className="text-[10px] text-slate-400 font-mono">
                          Col {field.source_column}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer: Read-Only with Close Preview only */}
        <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <div className="text-xs text-slate-500">
            Showing <strong className="text-slate-800">{totalRendered}</strong> fields across{' '}
            <strong className="text-slate-800">{groupedFields.length}</strong> Excel sections
          </div>
          <button
            onClick={onClose}
            className="px-5 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-semibold text-xs rounded-lg transition cursor-pointer"
          >
            Close Preview
          </button>
        </div>
      </div>
    </div>
  );
};

