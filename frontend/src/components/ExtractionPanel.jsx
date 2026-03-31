import React from 'react'

const DOC_CONFIG = {
  application_form: {
    label: 'Application Form',
    icon: '📋',
    headerBg: 'bg-blue-600',
    border: 'border-blue-200',
    keyBg: 'bg-blue-50 text-blue-700',
  },
  government_id: {
    label: 'Government ID',
    icon: '🪪',
    headerBg: 'bg-emerald-600',
    border: 'border-emerald-200',
    keyBg: 'bg-emerald-50 text-emerald-700',
  },
  policy_illustration: {
    label: 'Policy Illustration',
    icon: '📄',
    headerBg: 'bg-purple-600',
    border: 'border-purple-200',
    keyBg: 'bg-purple-50 text-purple-700',
  },
}

function formatKey(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function ExtractionCard({ docType, data }) {
  const cfg = DOC_CONFIG[docType]
  if (!data) return null

  return (
    <div className={`rounded-xl border ${cfg.border} overflow-hidden shadow-sm`}>
      <div className={`${cfg.headerBg} text-white px-4 py-3 flex items-center gap-2`}>
        <span>{cfg.icon}</span>
        <span className="font-semibold text-sm">{cfg.label}</span>
      </div>
      <div className="divide-y divide-gray-100">
        {Object.entries(data).map(([k, v]) => (
          <div key={k} className="flex px-4 py-2.5 gap-3">
            <span className={`text-xs font-medium rounded px-1.5 py-0.5 whitespace-nowrap self-start mt-0.5 ${cfg.keyBg}`}>
              {formatKey(k)}
            </span>
            {v !== null && v !== undefined ? (
              <span className="text-sm text-gray-800 break-words">{String(v)}</span>
            ) : (
              <span className="text-sm text-gray-400 italic">Not found</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ExtractionPanel({ extractions }) {
  const docTypes = Object.keys(DOC_CONFIG)
  const hasAny = docTypes.some((dt) => extractions[dt])

  if (!hasAny) return null

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
      <h2 className="text-lg font-bold text-gray-800 mb-5">Extracted Data</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {docTypes.map((dt) => (
          <ExtractionCard key={dt} docType={dt} data={extractions[dt]} />
        ))}
      </div>
    </div>
  )
}
