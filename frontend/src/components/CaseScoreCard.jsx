const DOC_LABELS = {
  application_form: 'Application Form',
  government_id: 'Government ID',
  policy_illustration: 'Policy Illustration',
}

const DOC_COLORS = {
  application_form: { bar: 'bg-blue-500', text: 'text-blue-700' },
  government_id: { bar: 'bg-emerald-500', text: 'text-emerald-700' },
  policy_illustration: { bar: 'bg-purple-500', text: 'text-purple-700' },
}

function statusColor(status) {
  if (status === 'Ready for Review') return { ring: '#22c55e', text: 'text-green-600', bg: 'bg-green-50' }
  if (status === 'Needs Attention') return { ring: '#f59e0b', text: 'text-amber-600', bg: 'bg-amber-50' }
  return { ring: '#ef4444', text: 'text-red-600', bg: 'bg-red-50' }
}

function CircularScore({ score, status }) {
  const colors = statusColor(status)
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference

  return (
    <div className="flex flex-col items-center">
      <svg width="140" height="140" className="-rotate-90">
        <circle cx="70" cy="70" r={radius} stroke="#e5e7eb" strokeWidth="12" fill="none" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          stroke={colors.ring}
          strokeWidth="12"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
      </svg>
      <div className="-mt-28 flex flex-col items-center mb-20">
        <span className="text-4xl font-bold text-gray-800">{score}</span>
        <span className="text-xs text-gray-400 mt-0.5">/ 100</span>
      </div>
      <span className={`text-sm font-semibold px-3 py-1 rounded-full ${colors.bg} ${colors.text}`}>
        {status}
      </span>
    </div>
  )
}

function CompletenessBar({ docType, data }) {
  const cfg = DOC_COLORS[docType]
  const score = data?.score ?? 0

  return (
    <div>
      <div className="flex justify-between text-xs font-medium mb-1">
        <span className="text-gray-600">{DOC_LABELS[docType]}</span>
        <span className={cfg.text}>{score}%</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${cfg.bar} rounded-full transition-all duration-700`}
          style={{ width: `${score}%` }}
        />
      </div>
      {data?.missing?.length > 0 && (
        <p className="text-xs text-gray-400 mt-1">
          Missing: {data.missing.join(', ')}
        </p>
      )}
    </div>
  )
}

const FORM_CATEGORY_LABELS = {
  health:       { label: 'Health Insurance', hint: 'Section E health declaration applies. No Q14 / fund direction.', color: 'bg-teal-50 border-teal-200 text-teal-700' },
  life_non_gae: { label: 'Life — Full Underwriting', hint: 'Medical UW required. Q14, beneficiary insurable interest, FNA apply.', color: 'bg-indigo-50 border-indigo-200 text-indigo-700' },
  life_gae:     { label: 'Life — Guaranteed Acceptance', hint: 'No medical UW required. Q14 and signatures still required.', color: 'bg-violet-50 border-violet-200 text-violet-700' },
  unknown:      { label: 'Form type not detected', hint: 'Maximum checks applied. Identify the form type manually.', color: 'bg-gray-50 border-gray-200 text-gray-600' },
}

export default function CaseScoreCard({ caseScore, caseStatus, completeness, criticalFlags, warnings, nbRequirements }) {
  if (caseScore === undefined || caseScore === null) return null

  const cat = nbRequirements?.form_category || 'unknown'
  const catCfg = FORM_CATEGORY_LABELS[cat] || FORM_CATEGORY_LABELS.unknown

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-start justify-between mb-5">
        <h2 className="text-lg font-bold text-gray-800">Case Score</h2>
        {/* Form type chip */}
        <div className={`flex flex-col items-end gap-0.5`}>
          <span className={`text-xs font-semibold px-3 py-1 rounded-full border ${catCfg.color}`}>
            {catCfg.label}
          </span>
          <span className="text-xs text-gray-400 text-right max-w-xs">{catCfg.hint}</span>
        </div>
      </div>

      <div className="flex flex-col md:flex-row gap-8 items-start">
        {/* Circular score */}
        <div className="flex-shrink-0 mx-auto md:mx-0">
          <CircularScore score={caseScore} status={caseStatus} />
        </div>

        {/* Right column */}
        <div className="flex-1 space-y-6 w-full">
          {/* Per-document completeness bars */}
          <div>
            <h3 className="text-sm font-semibold text-gray-600 mb-3 uppercase tracking-wide">
              Document Completeness
            </h3>
            <div className="space-y-4">
              {Object.entries(completeness || {}).map(([dt, data]) => (
                <CompletenessBar key={dt} docType={dt} data={data} />
              ))}
            </div>
          </div>

          {/* Critical flags */}
          {criticalFlags && criticalFlags.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-red-600 mb-2 uppercase tracking-wide">
                Critical Flags
              </h3>
              <ul className="space-y-1.5">
                {criticalFlags.map((f) => (
                  <li
                    key={f.check}
                    className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2"
                  >
                    <span className="mt-0.5">❌</span>
                    <span>{f.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Warnings */}
          {warnings && warnings.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-amber-600 mb-2 uppercase tracking-wide">
                Warnings
              </h3>
              <ul className="space-y-1.5">
                {warnings.map((w) => (
                  <li
                    key={w.check}
                    className="flex items-start gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"
                  >
                    <span className="mt-0.5">⚠️</span>
                    <span>{w.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {criticalFlags?.length === 0 && warnings?.length === 0 && (
            <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              ✅ No flags or warnings — case looks clean.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
