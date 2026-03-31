
function formatCheckName(check) {
  return check
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function StatusBadge({ status }) {
  if (status === 'pass') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-green-100 text-green-700 text-xs font-semibold">
        ✅ Pass
      </span>
    )
  }
  if (status === 'fail') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-red-100 text-red-700 text-xs font-semibold">
        ❌ Fail
      </span>
    )
  }
  if (status === 'unverified') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-semibold">
        🔍 Unverified
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-semibold">
      ⚠️ Warning
    </span>
  )
}

function ValidationRow({ v }) {
  const isCriticalBad = v.severity === 'critical' && v.status !== 'pass'
  const isWarning = v.severity === 'warning' && v.status !== 'pass'

  const borderClass = isCriticalBad
    ? v.status === 'unverified'
      ? 'border-l-4 border-l-slate-400 bg-slate-50'
      : 'border-l-4 border-l-red-500 bg-red-50'
    : isWarning
    ? 'border-l-4 border-l-amber-400 bg-amber-50'
    : 'border-l-4 border-l-transparent'

  return (
    <tr className={`${borderClass} transition-colors`}>
      <td className="px-4 py-3 text-sm font-medium text-gray-700 whitespace-nowrap">
        {formatCheckName(v.check)}
      </td>
      <td className="px-4 py-3 text-xs text-gray-500 max-w-xs">
        {Object.entries(v.values).map(([label, val]) => (
          <div key={label}>
            <span className="font-medium text-gray-600">{label}:</span>{' '}
            {val !== null && val !== undefined ? (
              <span className="text-gray-800">{String(val)}</span>
            ) : (
              <span className="italic text-gray-400">N/A</span>
            )}
          </div>
        ))}
      </td>
      <td className="px-4 py-3 text-center">
        <StatusBadge status={v.status} />
      </td>
      <td className="px-4 py-3 text-xs text-gray-500">{v.message}</td>
    </tr>
  )
}

export default function ValidationPanel({ validations }) {
  if (!validations || validations.length === 0) return null

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
      <h2 className="text-lg font-bold text-gray-800 mb-5">Cross-Document Validation</h2>
      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-left">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th className="px-4 py-3">Check</th>
              <th className="px-4 py-3">Values Compared</th>
              <th className="px-4 py-3 text-center">Status</th>
              <th className="px-4 py-3">Message</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {validations.map((v) => (
              <ValidationRow key={v.check} v={v} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
