import { useState } from 'react'

const SEVERITY_CONFIG = {
  blocking: {
    label: 'Blocking',
    badge: 'bg-red-100 text-red-700 border border-red-200',
    headerBg: 'bg-red-50 border-b border-red-100',
    border: 'border border-red-200',
    icon: '🚫',
    sectionTitle: 'text-red-700',
  },
  attention: {
    label: 'Needs Attention',
    badge: 'bg-amber-100 text-amber-700 border border-amber-200',
    headerBg: 'bg-amber-50 border-b border-amber-100',
    border: 'border border-amber-200',
    icon: '⚠️',
    sectionTitle: 'text-amber-700',
  },
  advisory: {
    label: 'Advisory',
    badge: 'bg-blue-100 text-blue-700 border border-blue-200',
    headerBg: 'bg-blue-50 border-b border-blue-100',
    border: 'border border-blue-200',
    icon: 'ℹ️',
    sectionTitle: 'text-blue-700',
  },
}

const STATUS_LABELS = {
  open: null,
  reviewed: { label: 'Confirmed', cls: 'bg-green-100 text-green-700' },
  waived: { label: 'Waived', cls: 'bg-purple-100 text-purple-700' },
}

// Derive a short category label from the rule_id prefix
function categoryFromRuleId(ruleId) {
  if (ruleId.startsWith('validation.')) return 'Cross-Document Mismatch'
  if (ruleId.startsWith('nb_external.')) return 'External Document Required'
  if (ruleId.startsWith('nb_trigger.')) return 'Follow-up Triggered'
  if (ruleId.startsWith('nb_crucial.')) return 'Required Field Missing'
  if (ruleId.startsWith('nb_minor.')) return 'Field Missing'
  return 'Issue'
}

function FindingCard({ finding, localAction, onAction }) {
  const [overrideVal, setOverrideVal] = useState('')
  const [reason, setReason] = useState('')
  const [showOverride, setShowOverride] = useState(false)

  const sev = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.advisory
  // Merge server status with local optimistic action
  const displayStatus = localAction
    ? (localAction.action === 'waive' ? 'waived' : 'reviewed')
    : finding.status
  const statusTag = STATUS_LABELS[displayStatus]
  const isActioned = displayStatus !== 'open'

  const category = categoryFromRuleId(finding.rule_id)

  return (
    <div className={`rounded-xl overflow-hidden ${sev.border} ${isActioned ? 'opacity-55' : ''} mb-3`}>
      {/* Card header */}
      <div className={`px-4 py-3 flex items-start gap-3 ${sev.headerBg}`}>
        <span className="text-xl mt-0.5 shrink-0">{sev.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${sev.badge}`}>
              {category}
            </span>
            {finding.source && (
              <span className="text-xs text-gray-500 bg-white border border-gray-200 px-2 py-0.5 rounded-full">
                {finding.source}
              </span>
            )}
            {statusTag && (
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusTag.cls}`}>
                ✓ {statusTag.label}
              </span>
            )}
          </div>
          {/* Human-readable title */}
          <p className="text-sm font-semibold text-gray-800 leading-snug">
            {finding.description}
          </p>
        </div>
      </div>

      {/* Note / remediation guidance */}
      {finding.note && (
        <div className="px-4 py-2.5 bg-white text-xs text-gray-600 leading-relaxed border-t border-gray-100">
          <span className="font-medium text-gray-700">What to do: </span>
          {finding.note}
        </div>
      )}

      {/* Action bar — only shown for open findings */}
      {!isActioned && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 flex flex-wrap gap-2 items-start">
          <button
            onClick={() => onAction(finding.rule_id, 'confirm', null, reason)}
            className="text-xs px-3 py-1.5 rounded-lg bg-green-100 text-green-700 hover:bg-green-200 font-semibold transition-colors"
          >
            ✓ Confirm / Acknowledged
          </button>
          <button
            onClick={() => { setShowOverride((v) => !v); }}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-100 text-indigo-700 hover:bg-indigo-200 font-semibold transition-colors"
          >
            ✏️ Override value
          </button>
          <button
            onClick={() => onAction(finding.rule_id, 'waive', null, reason)}
            className="text-xs px-3 py-1.5 rounded-lg bg-purple-100 text-purple-700 hover:bg-purple-200 font-semibold transition-colors"
          >
            ↷ Waive
          </button>
          <input
            type="text"
            placeholder="Reason / notes (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 flex-1 min-w-[160px] bg-white focus:outline-none focus:ring-1 focus:ring-indigo-300"
          />
          {showOverride && (
            <div className="w-full flex gap-2 mt-1">
              <input
                type="text"
                placeholder="Enter corrected value…"
                value={overrideVal}
                onChange={(e) => setOverrideVal(e.target.value)}
                className="text-xs border border-indigo-300 rounded-lg px-2.5 py-1.5 flex-1 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-400"
              />
              <button
                onClick={() => {
                  onAction(finding.rule_id, 'override', overrideVal, reason)
                  setShowOverride(false)
                }}
                disabled={!overrideVal.trim()}
                className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 font-semibold transition-colors"
              >
                Apply override
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Section({ severity, findings, localActions, onAction }) {
  const items = findings.filter((f) => f.severity === severity)
  if (items.length === 0) return null
  const sev = SEVERITY_CONFIG[severity]

  return (
    <div className="mb-6">
      <h3 className={`text-xs font-bold uppercase tracking-wider mb-3 flex items-center gap-2 ${sev.sectionTitle}`}>
        <span>{sev.icon}</span>
        {sev.label}
        <span className="font-normal text-gray-400">({items.length})</span>
      </h3>
      {items.map((f) => (
        <FindingCard
          key={f.rule_id}
          finding={f}
          localAction={localActions[f.rule_id]}
          onAction={onAction}
        />
      ))}
    </div>
  )
}

export default function FindingsPanel({ findings, caseId, onResumed }) {
  const [localActions, setLocalActions] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  if (!findings || findings.length === 0) return null

  function handleAction(ruleId, action, correctedValue, reason) {
    setLocalActions((prev) => ({
      ...prev,
      [ruleId]: {
        finding_rule_id: ruleId,
        action,
        corrected_value: correctedValue || null,
        reason: reason || null,
      },
    }))
  }

  const pendingActions = Object.values(localActions)

  // Count open findings after local actions are applied
  const openAfterActions = findings.filter((f) => {
    if (localActions[f.rule_id]) return false
    return f.status === 'open'
  }).length

  const blockingOpen = findings.filter((f) => {
    const actioned = !!localActions[f.rule_id]
    return f.severity === 'blocking' && !actioned && f.status === 'open'
  }).length

  async function handleSubmit() {
    if (!caseId || pendingActions.length === 0) return
    setSubmitting(true)
    setError(null)
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
      const res = await fetch(`${API_BASE}/api/resume-case/${caseId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer_actions: pendingActions }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail?.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setLocalActions({})
      onResumed(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
      {/* Panel header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-gray-800">Reviewer Checklist</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Review each finding below. Confirm, override, or waive — then submit to finalise the case.
            {blockingOpen > 0 && (
              <span className="ml-1 text-red-600 font-semibold">
                {blockingOpen} blocking issue{blockingOpen !== 1 ? 's' : ''} must be resolved.
              </span>
            )}
          </p>
        </div>
        <button
          onClick={handleSubmit}
          disabled={submitting || pendingActions.length === 0}
          className="ml-4 shrink-0 text-sm px-4 py-2 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 font-semibold transition-colors"
        >
          {submitting
            ? 'Submitting…'
            : pendingActions.length > 0
            ? `Submit ${pendingActions.length} action${pendingActions.length !== 1 ? 's' : ''}`
            : 'Submit'}
        </button>
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      <Section severity="blocking"  findings={findings} localActions={localActions} onAction={handleAction} />
      <Section severity="attention" findings={findings} localActions={localActions} onAction={handleAction} />
      <Section severity="advisory"  findings={findings} localActions={localActions} onAction={handleAction} />

      {openAfterActions === 0 && pendingActions.length > 0 && (
        <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3 mt-2">
          All findings addressed — click <strong>Submit</strong> to finalise the case.
        </div>
      )}
    </div>
  )
}
