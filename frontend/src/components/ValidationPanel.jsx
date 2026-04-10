/**
 * ValidationPanel — cross-document validation checks with FSS notification.
 *
 * Severity mapping (from New Business Document Type.xlsx, Validation sheet):
 *   All cross-doc data mismatches → "manual notification to FSS to verify"
 *   None of the 7 checks trigger outright rejection (rejection is for wrong form version,
 *   which cannot be automated).
 *
 * UI behaviour:
 *   pass       → green row
 *   unverified → gray row (missing data, cannot check)
 *   fail       → amber row + "Notify FSS" button → email draft modal
 */

import { useState } from 'react'

const CHECK_LABELS = {
  name_match_form_vs_id:           { label: 'Name — Form vs. ID',                docs: ['Application Form', 'Government ID'] },
  name_match_form_vs_policy:       { label: 'Name — Form vs. Sales Illustration', docs: ['Application Form', 'Sales Illustration'] },
  dob_match_form_vs_id:            { label: 'Date of Birth — Form vs. ID',        docs: ['Application Form', 'Government ID'] },
  dob_match_form_vs_policy:        { label: 'Date of Birth — Form vs. SI',        docs: ['Application Form', 'Sales Illustration'] },
  pincode_match_form_vs_id:        { label: 'Postal Code — Form vs. ID',          docs: ['Application Form', 'Government ID'] },
  sum_assured_match_form_vs_policy:{ label: 'Sum Assured — Form vs. SI',          docs: ['Application Form', 'Sales Illustration'] },
  plan_name_match:                 { label: 'Plan Name — Form vs. SI',            docs: ['Application Form', 'Sales Illustration'] },
  fund_direction_match:            { label: 'Fund Direction — Form vs. SI',       docs: ['Application Form', 'Sales Illustration'] },
}

function statusConfig(status) {
  if (status === 'pass')       return { icon: '✓', row: 'bg-emerald-50/40', badge: 'bg-emerald-100 text-emerald-700', label: 'Match'      }
  if (status === 'fail')       return { icon: '✕', row: 'bg-amber-50/60',   badge: 'bg-amber-100 text-amber-700',   label: 'Mismatch'   }
  if (status === 'unverified') return { icon: '?', row: 'bg-gray-50/60',    badge: 'bg-gray-100 text-gray-500',     label: 'Unverified' }
  return                              { icon: '–', row: '',                  badge: 'bg-gray-100 text-gray-400',     label: status       }
}

function buildEmailDraft(check, validation, caseId) {
  const cfg    = CHECK_LABELS[check] || { label: check }
  const lines  = Object.entries(validation.values || {})
    .map(([k, v]) => `  • ${k}: ${v ?? '(not found)'}`)
    .join('\n')

  return {
    subject: `ICR Alert — ${cfg.label} Mismatch | Case ${caseId?.slice(0, 8) ?? ''}`,
    body: `Hi FSS Team,\n\nA data mismatch was detected during automated case review.\n\nCheck: ${cfg.label}\nCase ID: ${caseId ?? 'N/A'}\n\nValues found:\n${lines}\n\nPlease verify this discrepancy with the Financial Advisor and advise on the correct value before proceeding with the case.\n\nThank you,\nICR System`,
  }
}

function EmailModal({ draft, onClose, onSend }) {
  const [subject, setSubject] = useState(draft.subject)
  const [body, setBody]       = useState(draft.body)
  const [copied, setCopied]   = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function handleMailto() {
    window.open(
      `mailto:fss@allianzpnblife.ph?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
    )
    onSend()
  }

  return (
    <div
      className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg border border-gray-100 overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-amber-50">
          <div className="flex items-center gap-2">
            <span className="text-lg">📧</span>
            <div>
              <h3 className="text-sm font-bold text-gray-800">Notify FSS Team</h3>
              <p className="text-xs text-gray-500">Review and send the notification below</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">×</button>
        </div>

        <div className="p-5 space-y-3">
          <div>
            <label className="text-xs font-semibold text-gray-600 block mb-1">Subject</label>
            <input
              className="w-full text-xs border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-300"
              value={subject}
              onChange={e => setSubject(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600 block mb-1">Message</label>
            <textarea
              rows={10}
              className="w-full text-xs border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-300 font-mono leading-relaxed resize-none"
              value={body}
              onChange={e => setBody(e.target.value)}
            />
          </div>
        </div>

        <div className="px-5 py-3 border-t border-gray-100 bg-gray-50 flex gap-2 justify-end">
          <button
            onClick={handleCopy}
            className="text-xs px-4 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-100 font-medium transition-colors"
          >
            {copied ? '✓ Copied' : 'Copy to clipboard'}
          </button>
          <button
            onClick={handleMailto}
            className="text-xs px-4 py-2 rounded-lg bg-amber-500 text-white hover:bg-amber-600 font-semibold transition-colors"
          >
            Open in Email Client →
          </button>
        </div>
      </div>
    </div>
  )
}

function ValidationRow({ validation, caseId, notifiedChecks, onNotify }) {
  const [showModal, setShowModal] = useState(false)
  const cfg      = CHECK_LABELS[validation.check] || { label: validation.check }
  const st       = statusConfig(validation.status)
  const draft    = buildEmailDraft(validation.check, validation, caseId)
  const notified = notifiedChecks.has(validation.check)

  const valEntries = Object.entries(validation.values || {})

  return (
    <>
      <tr className={`border-b border-gray-50 last:border-0 ${st.row} transition-colors`}>
        <td className="px-4 py-3.5">
          <span className="text-sm font-medium text-gray-800">{cfg.label}</span>
        </td>
        <td className="px-3 py-3.5 text-xs text-gray-600">
          <span className="block max-w-[150px] truncate" title={String(valEntries[0]?.[1] ?? '')}>
            {valEntries[0]?.[1] ?? <span className="text-gray-300 italic">—</span>}
          </span>
        </td>
        <td className="px-3 py-3.5 text-xs text-gray-600">
          <span className="block max-w-[150px] truncate" title={String(valEntries[1]?.[1] ?? '')}>
            {valEntries[1]?.[1] ?? <span className="text-gray-300 italic">—</span>}
          </span>
        </td>
        <td className="px-3 py-3.5 text-center">
          {validation.score !== null ? (
            <span className={`text-xs font-bold ${validation.score >= 85 ? 'text-emerald-600' : validation.score >= 60 ? 'text-amber-600' : 'text-red-600'}`}>
              {validation.score}
            </span>
          ) : (
            <span className="text-xs text-gray-300">—</span>
          )}
        </td>
        <td className="px-3 py-3.5">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${st.badge}`}>
            {st.icon} {st.label}
          </span>
        </td>
        <td className="px-4 py-3.5 text-right">
          {validation.status === 'fail' ? (
            notified ? (
              <span className="text-xs text-emerald-600 font-medium flex items-center justify-end gap-1">
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></span> Notified
              </span>
            ) : (
              <button
                onClick={() => setShowModal(true)}
                className="text-xs px-3 py-1.5 rounded-lg bg-amber-500 text-white hover:bg-amber-600 font-semibold transition-colors shadow-sm whitespace-nowrap"
              >
                Notify FSS
              </button>
            )
          ) : (
            <span className="text-xs text-gray-300">—</span>
          )}
        </td>
      </tr>

      {showModal && (
        <tr>
          <td colSpan={6} className="p-0">
            <EmailModal
              draft={draft}
              onClose={() => setShowModal(false)}
              onSend={() => { onNotify(validation.check); setShowModal(false) }}
            />
          </td>
        </tr>
      )}
    </>
  )
}

export default function ValidationPanel({ validations, caseId }) {
  const [notifiedChecks, setNotifiedChecks] = useState(new Set())

  if (!validations || validations.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center">
        <p className="text-sm text-gray-400">No validation checks available.</p>
      </div>
    )
  }

  const passCount       = validations.filter(v => v.status === 'pass').length
  const failCount       = validations.filter(v => v.status === 'fail').length
  const unverifiedCount = validations.filter(v => v.status === 'unverified').length

  function handleNotify(check) {
    setNotifiedChecks(prev => new Set([...prev, check]))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-base font-bold text-gray-900">Cross-Document Validation</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Automated comparison across Application Form, Government ID, and Sales Illustration
          </p>
        </div>
        <div className="flex items-center gap-2">
          {passCount > 0 && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              {passCount} passed
            </span>
          )}
          {unverifiedCount > 0 && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-gray-50 text-gray-500 border border-gray-200">
              {unverifiedCount} unverified
            </span>
          )}
          {failCount > 0 && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
              {failCount} mismatch{failCount !== 1 ? 'es' : ''}
            </span>
          )}
        </div>
      </div>

      {failCount > 0 && (
        <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-start gap-3">
          <span className="text-lg shrink-0 mt-0.5">📋</span>
          <p className="text-xs text-amber-800 leading-relaxed">
            <strong>FSS Notification Required:</strong> Per Allianz PNB Life NB guidelines, data mismatches require a manual notification to the Financial Services Support team to verify with the Financial Advisor. Use <strong>"Notify FSS"</strong> on each mismatched row.
          </p>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/80">
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Check</th>
              <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Form Value</th>
              <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">ID / SI Value</th>
              <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-center w-16">Score</th>
              <th className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide w-28">Result</th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide text-right w-32">Action</th>
            </tr>
          </thead>
          <tbody>
            {validations.map(v => (
              <ValidationRow
                key={v.check}
                validation={v}
                caseId={caseId}
                notifiedChecks={notifiedChecks}
                onNotify={handleNotify}
              />
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-gray-400 text-right">
        Mismatches trigger FSS notification — not automatic rejection per NB guidelines
      </p>
    </div>
  )
}
