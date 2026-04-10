/**
 * KeyChecksPanel — 8 key underwriting check cards + full NB Requirements Checklist.
 *
 * Section 1: 8 key checks (cards grid)
 *   1. Age & Gender (with Substandard SI flag)
 *   2. Question #14 — PEP / politically exposed person
 *   3. Payout Option + fund direction trigger
 *   4. US Person / US indicia (FATCA)
 *   5. Height & Weight — always N/A for GAE
 *   6. Email & Contact Number
 *   7. Signatures (PI, AO, FA)
 *   8. Beneficiary / Relationship
 *
 * Section 2: NB Requirements Checklist (from nb_requirements.crucial + .minor)
 *   All checks surfaced here, with "Notify FSS" on any missing/failing item.
 *   This covers the full Allianz PNB Life NB checklist per the validation spreadsheet.
 */

import { useState } from 'react'

function get(extractions, doc, field) {
  return (extractions[doc] || {})[field] ?? null
}

function present(v) {
  if (v === null || v === undefined) return false
  if (typeof v === 'boolean') return true
  return String(v).trim() !== ''
}

// ── Shared email modal ────────────────────────────────────────────────────────

function NotifyFSSModal({ subject, body, onClose, onSend }) {
  const [subj, setSubj] = useState(subject)
  const [msg,  setMsg]  = useState(body)
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(`Subject: ${subj}\n\n${msg}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function handleMailto() {
    window.open(
      `mailto:fss@allianzpnblife.ph?subject=${encodeURIComponent(subj)}&body=${encodeURIComponent(msg)}`
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
            <input className="w-full text-xs border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-300"
              value={subj} onChange={e => setSubj(e.target.value)} />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600 block mb-1">Message</label>
            <textarea rows={9}
              className="w-full text-xs border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-300 font-mono leading-relaxed resize-none"
              value={msg} onChange={e => setMsg(e.target.value)} />
          </div>
        </div>
        <div className="px-5 py-3 border-t border-gray-100 bg-gray-50 flex gap-2 justify-end">
          <button onClick={handleCopy}
            className="text-xs px-4 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-100 font-medium transition-colors">
            {copied ? '✓ Copied' : 'Copy to clipboard'}
          </button>
          <button onClick={handleMailto}
            className="text-xs px-4 py-2 rounded-lg bg-amber-500 text-white hover:bg-amber-600 font-semibold transition-colors">
            Open in Email Client →
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Inline "Notify FSS" button used inside check cards ────────────────────────

function NotifyFSSButton({ requirementLabel, context, caseId }) {
  const [show,     setShow]     = useState(false)
  const [notified, setNotified] = useState(false)

  const subject = `ICR Alert — Missing Field: ${requirementLabel} | Case ${caseId?.slice(0, 8) ?? ''}`
  const body    = `Hi FSS Team,\n\nA required field is missing in the current case submission.\n\nCase ID: ${caseId ?? 'N/A'}\nMissing: ${requirementLabel}\n${context ? `\nContext: ${context}` : ''}\n\nPlease contact the Financial Advisor to obtain this information before the case can proceed.\n\nThank you,\nICR System`

  if (notified) {
    return <span className="text-xs text-emerald-600 font-medium flex items-center gap-1 mt-2"><span className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></span>FSS Notified</span>
  }

  return (
    <>
      <button
        onClick={() => setShow(true)}
        className="mt-2 text-xs px-3 py-1.5 rounded-lg bg-amber-500 text-white hover:bg-amber-600 font-semibold transition-colors shadow-sm"
      >
        Notify FSS
      </button>
      {show && (
        <NotifyFSSModal
          subject={subject}
          body={body}
          onClose={() => setShow(false)}
          onSend={() => { setNotified(true); setShow(false) }}
        />
      )}
    </>
  )
}

// ── Status badge ──────────────────────────────────────────────────────────────

const BADGE = {
  ok:      { label: 'OK',       cls: 'bg-emerald-50 text-emerald-700 border border-emerald-200' },
  flag:    { label: 'Flagged',  cls: 'bg-amber-50 text-amber-700 border border-amber-200' },
  missing: { label: 'Missing',  cls: 'bg-red-50 text-red-700 border border-red-200' },
  na:      { label: 'N/A',      cls: 'bg-gray-50 text-gray-500 border border-gray-200' },
  info:    { label: 'Review',   cls: 'bg-blue-50 text-blue-700 border border-blue-200' },
}

function Badge({ type }) {
  const cfg = BADGE[type] || BADGE.info
  return <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${cfg.cls}`}>{cfg.label}</span>
}

// ── Field row ─────────────────────────────────────────────────────────────────

function FieldRow({ label, value }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-500 shrink-0">{label}</span>
      {!present(value) ? (
        <span className="text-xs font-medium text-red-400">— not found</span>
      ) : (
        <span className="text-xs font-semibold text-gray-800 text-right max-w-[180px] truncate" title={String(value)}>
          {String(value)}
        </span>
      )}
    </div>
  )
}

// ── Note callout ──────────────────────────────────────────────────────────────

function Note({ type = 'amber', children }) {
  const styles = {
    amber: 'bg-amber-50 border-amber-200 text-amber-800',
    blue:  'bg-blue-50 border-blue-200 text-blue-800',
    red:   'bg-red-50 border-red-200 text-red-800',
    green: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    gray:  'bg-gray-50 border-gray-200 text-gray-600',
  }
  return (
    <div className={`mt-3 text-xs rounded-lg border px-3 py-2 leading-relaxed ${styles[type]}`}>
      {children}
    </div>
  )
}

// ── Individual check cards ────────────────────────────────────────────────────

function Check1_AgeGender({ extractions, nbRequirements, caseId }) {
  const age    = nbRequirements?.insured_age
  const gender = get(extractions, 'application_form', 'gender') || get(extractions, 'policy_illustration', 'insured_gender')
  const dob    = get(extractions, 'application_form', 'date_of_birth')
  const isSubstandard = get(extractions, 'policy_illustration', 'is_substandard')
  const ageOk    = present(age)
  const genderOk = present(gender)
  const status   = !ageOk || !genderOk ? 'missing' : isSubstandard === true ? 'flag' : 'ok'

  return (
    <CheckCard number={1} title="Age & Gender" icon="👤" status={status}>
      <FieldRow label="Date of Birth"  value={dob} />
      <FieldRow label="Resolved Age"   value={age !== null ? `${age} years old` : null} />
      <FieldRow label="Gender"         value={gender} />
      <FieldRow label="Substandard SI" value={isSubstandard === true ? 'Yes — flagged' : isSubstandard === false ? 'No' : 'Not indicated'} />
      {isSubstandard === true && (
        <Note type="amber">Sales Illustration is marked <strong>Substandard</strong> — additional underwriting requirements apply. Notify the underwriting team.</Note>
      )}
      {(!ageOk || !genderOk) && (
        <>
          <Note type="red">Age or gender could not be extracted. This affects premium calculation — request the FA to verify.</Note>
          <NotifyFSSButton requirementLabel="Insured Age / Gender" context="Could not extract from Application Form or Sales Illustration" caseId={caseId} />
        </>
      )}
    </CheckCard>
  )
}

function Check2_Q14({ extractions, caseId }) {
  const answer   = get(extractions, 'application_form', 'question_14_answer')
  const answered = present(answer)
  const isYes    = answered && String(answer).toLowerCase() === 'yes'
  const status   = !answered ? 'missing' : isYes ? 'flag' : 'ok'

  return (
    <CheckCard number={2} title="PEP Check (Q#14)" icon="🏛️" status={status}>
      <FieldRow label="Question #14 Answer" value={answered ? answer : null} />
      <p className="text-xs text-gray-400 mt-2 leading-relaxed">
        "Are you or any family members / associates entrusted with a prominent public position?"
      </p>
      {isYes && (
        <Note type="amber">
          Client answered <strong>Yes</strong> — an <strong>Additional Intermediary Declaration (AID) Form</strong> plus proof of Applicant Owner's source of funds are required. These are not in the current submission.
        </Note>
      )}
      {!answered && (
        <>
          <Note type="red">Question #14 was not answered. Required for all Life insurance applications.</Note>
          <NotifyFSSButton requirementLabel="Question #14 (PEP Check) — answer missing" context="Question 14 about politically exposed persons was left blank on the Application Form." caseId={caseId} />
        </>
      )}
    </CheckCard>
  )
}

function Check3_PayoutOption({ extractions, caseId }) {
  const payout      = get(extractions, 'application_form', 'payout_option')
  const fundSI      = get(extractions, 'policy_illustration', 'fund_direction')
  const answered    = present(payout)
  const isAutomatic = answered && String(payout).toLowerCase().includes('automatic')
  const isDividend  = present(fundSI) && String(fundSI).toLowerCase().includes('dividend')
  const bankRequired = isAutomatic && isDividend
  const status = !answered ? 'missing' : bankRequired ? 'flag' : 'ok'

  return (
    <CheckCard number={3} title="Payout Option" icon="💳" status={status}>
      <FieldRow label="Payout Selection"    value={payout} />
      <FieldRow label="Fund Direction (SI)" value={fundSI} />
      {bankRequired && (
        <Note type="amber">
          Payout is set to <strong>Automatic Transfer</strong> and fund is a <strong>Dividend Paying Fund</strong> — <strong>Proof of Bank Account Ownership</strong> is required as an additional document.
        </Note>
      )}
      {isAutomatic && !isDividend && (
        <Note type="green">Automatic Transfer selected but fund is not a Dividend Paying Fund — no bank proof required.</Note>
      )}
      {!answered && (
        <>
          <Note type="red">Payout option was not selected in Section D. This field is required.</Note>
          <NotifyFSSButton requirementLabel="Payout Option — selection missing" context="Section D (Payout Option) was not completed on the Application Form." caseId={caseId} />
        </>
      )}
    </CheckCard>
  )
}

function Check4_USPerson({ extractions, caseId }) {
  const isUS    = get(extractions, 'application_form', 'is_us_person')
  const pob     = get(extractions, 'application_form', 'place_of_birth')
  const nat     = get(extractions, 'application_form', 'nationality')
  const answered = isUS !== null
  const usKeywords = ['united states', 'u.s.', 'usa', 'american']
  const hasIndicia = usKeywords.some(k =>
    String(pob || '').toLowerCase().includes(k) ||
    String(nat || '').toLowerCase().includes(k)
  )
  const flagged = isUS === true || hasIndicia
  const status  = !answered && !present(pob) && !present(nat) ? 'missing' : flagged ? 'flag' : 'ok'

  return (
    <CheckCard number={4} title="US Person / FATCA" icon="🇺🇸" status={status}>
      <FieldRow label="US Person (checkbox)" value={isUS === true ? 'Yes' : isUS === false ? 'No' : null} />
      <FieldRow label="Place of Birth" value={pob} />
      <FieldRow label="Nationality"    value={nat} />
      {flagged && (
        <Note type="amber">
          US indicia detected — <strong>Addendum to Client Information Form (ACIF)</strong> is required.
          {isUS === true && <> Client confirmed US person — <strong>W-9 Form</strong> also needed.</>}
          {isUS === false && <> Client answered No — <strong>W-8BEN</strong> + non-US passport still required.</>}
        </Note>
      )}
      {!flagged && answered && (
        <Note type="green">No US indicia detected. ACIF / W-9 not required based on available information.</Note>
      )}
      {!answered && !present(pob) && !present(nat) && (
        <>
          <Note type="red">US Person checkbox, place of birth, and nationality could not be determined. Manual review required.</Note>
          <NotifyFSSButton requirementLabel="US Person / FATCA fields missing" context="Could not determine US person status — checkbox, place of birth, and nationality not found." caseId={caseId} />
        </>
      )}
    </CheckCard>
  )
}

function Check5_HeightWeight() {
  return (
    <CheckCard number={5} title="Height & Weight" icon="⚕️" status="na">
      <div className="flex items-start gap-2 mt-1">
        <span className="text-lg">🛡️</span>
        <div>
          <p className="text-xs font-semibold text-gray-700">Not Applicable — Guaranteed Acceptance</p>
          <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">
            This is a GAE (Guaranteed Acceptance Endorsement) application. No medical examination or health declaration is required. Height and weight fields are not collected on this form.
          </p>
        </div>
      </div>
    </CheckCard>
  )
}

function Check6_ContactDetails({ extractions, caseId }) {
  const email   = get(extractions, 'application_form', 'email')
  const phone   = get(extractions, 'application_form', 'phone')
  const emailOk = present(email)
  const phoneOk = present(phone)
  const status  = !emailOk || !phoneOk ? 'missing' : 'ok'

  return (
    <CheckCard number={6} title="Email & Contact" icon="📱" status={status}>
      <FieldRow label="Email Address" value={email} />
      <FieldRow label="Mobile Number" value={phone} />
      {(!emailOk || !phoneOk) && (
        <>
          <Note type="red">
            {!emailOk && !phoneOk ? 'Email and mobile number are both missing. '
              : !emailOk ? 'Email address is missing. '
              : 'Mobile number is missing. '}
            These are mandatory for e-Policy delivery and OTP notifications.
          </Note>
          <NotifyFSSButton
            requirementLabel={!emailOk && !phoneOk ? 'Email address and Mobile Number' : !emailOk ? 'Email address' : 'Mobile Number'}
            context="Mandatory contact fields missing from the Application Form. Required for e-Policy delivery and notifications."
            caseId={caseId}
          />
        </>
      )}
    </CheckCard>
  )
}

function Check7_Signatures({ extractions, nbRequirements, caseId }) {
  const insuredSig = get(extractions, 'application_form', 'insured_signature_present')
  const payorSig   = get(extractions, 'application_form', 'payor_signature_present')
  const faSig      = get(extractions, 'application_form', 'fa_signature_present')
  const sigDate    = get(extractions, 'application_form', 'signing_date')
  const sigPlace   = get(extractions, 'application_form', 'signing_place')
  const age        = nbRequirements?.insured_age
  const insuredRequired = age === null || age >= 18
  const insuredMissing  = insuredRequired && insuredSig !== true
  const faMissing       = faSig !== true
  const status = insuredMissing || faMissing ? 'missing' : 'ok'

  function SigRow({ label, p, notRequired = false }) {
    return (
      <div className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
        <span className="text-xs text-gray-500">{label}</span>
        {notRequired ? (
          <span className="text-xs text-gray-400 italic">same person as PI</span>
        ) : p === true ? (
          <span className="text-xs font-semibold text-emerald-700 flex items-center gap-1"><span className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></span>Present</span>
        ) : p === false ? (
          <span className="text-xs font-semibold text-red-600 flex items-center gap-1"><span className="w-1.5 h-1.5 bg-red-500 rounded-full"></span>Missing</span>
        ) : (
          <span className="text-xs text-gray-400">— unclear</span>
        )}
      </div>
    )
  }

  return (
    <CheckCard number={7} title="Signatures" icon="✍️" status={status}>
      <SigRow label="Proposed Insured"            p={insuredSig} />
      <SigRow label="Applicant Owner (if ≠ PI)"   p={payorSig} notRequired={payorSig === false && insuredSig === true} />
      <SigRow label="Financial Advisor"            p={faSig} />
      <FieldRow label="Signing Date"  value={sigDate} />
      <FieldRow label="Signing Place" value={sigPlace} />
      {age !== null && age < 18 && (
        <Note type="blue">Insured is a minor (age {age}) — AO signs on behalf. Authorization to Insure Child may be required if AO is not a parent.</Note>
      )}
      {(insuredMissing || faMissing) && (
        <>
          <Note type="red">
            {insuredMissing && faMissing ? 'Insured and FA signatures are missing. '
              : insuredMissing ? 'Insured signature is missing. '
              : 'Financial Advisor signature is missing. '}
            Application cannot proceed without required signatures.
          </Note>
          <NotifyFSSButton
            requirementLabel={insuredMissing && faMissing ? 'Insured + FA Signatures' : insuredMissing ? 'Proposed Insured Signature' : 'Financial Advisor Signature'}
            context="Required signatures missing from the Application Form signature page."
            caseId={caseId}
          />
        </>
      )}
    </CheckCard>
  )
}

function Check8_Beneficiary({ extractions, caseId }) {
  const name         = get(extractions, 'application_form', 'nominee_name')
  const relationship = get(extractions, 'application_form', 'nominee_relationship')
  const nameOk       = present(name)
  const relOk        = present(relationship)
  const immediateFamily = ['spouse', 'child', 'parent', 'sibling', 'son', 'daughter', 'mother', 'father', 'brother', 'sister']
  const isNonFamily  = relOk && !immediateFamily.some(f => String(relationship || '').toLowerCase().includes(f))
  const status = !nameOk || !relOk ? 'missing' : isNonFamily ? 'flag' : 'ok'

  return (
    <CheckCard number={8} title="Beneficiary" icon="👨‍👩‍👧" status={status}>
      <FieldRow label="Beneficiary Name"   value={name} />
      <FieldRow label="Relationship to PI" value={relationship} />
      {isNonFamily && (
        <Note type="amber">
          Beneficiary is a <strong>{relationship}</strong> — not an immediate family member. FA must justify insurable interest on <strong>Page 2 of the Agent's Confidential Report (ACR)</strong>.
        </Note>
      )}
      {(!nameOk || !relOk) && (
        <>
          <Note type="red">Beneficiary name or relationship is missing. Both are required fields.</Note>
          <NotifyFSSButton
            requirementLabel="Beneficiary Name / Relationship"
            context="Beneficiary information missing from Section B of the Application Form."
            caseId={caseId}
          />
        </>
      )}
    </CheckCard>
  )
}

// ── Check card shell ──────────────────────────────────────────────────────────

function CheckCard({ number, title, icon, status, children }) {
  const borderColors = { ok: 'border-emerald-100', flag: 'border-amber-200', missing: 'border-red-200', na: 'border-gray-100', info: 'border-blue-100' }
  const headerColors = { ok: 'text-emerald-600', flag: 'text-amber-600', missing: 'text-red-500', na: 'text-gray-400', info: 'text-blue-600' }
  return (
    <div className={`bg-white rounded-2xl border p-5 flex flex-col gap-1 transition-colors ${borderColors[status] || borderColors.info}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl leading-none">{icon}</span>
          <div>
            <span className={`text-xs font-bold uppercase tracking-widest ${headerColors[status]}`}>Check {number}</span>
            <h3 className="text-sm font-bold text-gray-800 leading-tight">{title}</h3>
          </div>
        </div>
        <Badge type={status} />
      </div>
      <div className="flex-1">{children}</div>
    </div>
  )
}

// ── NB Requirements Checklist ─────────────────────────────────────────────────

const STATUS_STYLE = {
  present:                    { dot: 'bg-emerald-500', text: 'text-emerald-700', label: 'Present',          row: '' },
  missing:                    { dot: 'bg-red-500',     text: 'text-red-700',     label: 'Missing',          row: 'bg-red-50/40' },
  not_required:               { dot: 'bg-gray-300',    text: 'text-gray-400',    label: 'N/A',              row: '' },
  external_document_required: { dot: 'bg-blue-400',    text: 'text-blue-600',    label: 'External Doc',     row: 'bg-blue-50/30' },
}

function NbRow({ item, caseId }) {
  const [showModal, setShowModal] = useState(false)
  const [notified,  setNotified]  = useState(false)

  const st      = STATUS_STYLE[item.status] || STATUS_STYLE.present
  const canNotify = item.status === 'missing'

  const subject = `ICR Alert — Required Field Missing: ${item.requirement} | Case ${caseId?.slice(0, 8) ?? ''}`
  const body    = `Hi FSS Team,\n\nA required field or document is missing in the current case submission.\n\nCase ID: ${caseId ?? 'N/A'}\nItem: ${item.requirement}\nSource: ${item.source}\n${item.note ? `\nNote: ${item.note}` : ''}\n\nPlease contact the Financial Advisor to obtain this information before the case can proceed.\n\nThank you,\nICR System`

  return (
    <tr className={`border-b border-gray-50 last:border-0 ${st.row}`}>
      <td className="px-4 py-3 text-sm text-gray-800">{item.requirement}</td>
      <td className="px-3 py-3 text-xs text-gray-500">{item.source}</td>
      <td className="px-3 py-3">
        <span className={`flex items-center gap-1.5 text-xs font-semibold ${st.text}`}>
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${st.dot}`}></span>
          {st.label}
        </span>
      </td>
      <td className="px-3 py-3 text-xs text-gray-500 max-w-xs">
        <span className="line-clamp-2">{item.note || '—'}</span>
      </td>
      <td className="px-4 py-3 text-right">
        {canNotify && !notified && (
          <>
            <button
              onClick={() => setShowModal(true)}
              className="text-xs px-3 py-1.5 rounded-lg bg-amber-500 text-white hover:bg-amber-600 font-semibold transition-colors shadow-sm"
            >
              Notify FSS
            </button>
            {showModal && (
              <NotifyFSSModal
                subject={subject}
                body={body}
                onClose={() => setShowModal(false)}
                onSend={() => { setNotified(true); setShowModal(false) }}
              />
            )}
          </>
        )}
        {canNotify && notified && (
          <span className="text-xs text-emerald-600 font-medium flex items-center justify-end gap-1">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></span>Notified
          </span>
        )}
        {!canNotify && <span className="text-xs text-gray-300">—</span>}
      </td>
    </tr>
  )
}

function NbRequirementsSection({ nbRequirements, caseId }) {
  const [showMinor, setShowMinor] = useState(false)
  const crucial = nbRequirements?.crucial || []
  const minor   = nbRequirements?.minor   || []

  const missingCrucial = crucial.filter(i => i.status === 'missing').length
  const missingMinor   = minor.filter(i => i.status === 'missing').length

  if (crucial.length === 0 && minor.length === 0) return null

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-bold text-gray-900">NB Requirements Checklist</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Complete list of NB checks per Allianz PNB Life guidelines — all checks shown regardless of pass/fail
          </p>
        </div>
        <div className="flex items-center gap-2">
          {missingCrucial > 0 && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-red-50 text-red-700 border border-red-200">
              {missingCrucial} crucial missing
            </span>
          )}
          {missingCrucial === 0 && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              All crucial present
            </span>
          )}
        </div>
      </div>

      {/* Crucial requirements */}
      <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden mb-4">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-100">
          <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Crucial Requirements</h3>
          <p className="text-xs text-gray-400 mt-0.5">Missing crucial items block case processing</p>
        </div>
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-gray-50">
              <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Requirement</th>
              <th className="px-3 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Source</th>
              <th className="px-3 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide w-28">Status</th>
              <th className="px-3 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Note</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide text-right w-32">Action</th>
            </tr>
          </thead>
          <tbody>
            {crucial.map((item, i) => <NbRow key={i} item={item} caseId={caseId} />)}
          </tbody>
        </table>
      </div>

      {/* Minor requirements (collapsible) */}
      {minor.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
          <button
            onClick={() => setShowMinor(v => !v)}
            className="w-full px-4 py-3 bg-gray-50 border-b border-gray-100 flex items-center justify-between hover:bg-gray-100 transition-colors"
          >
            <div>
              <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide text-left">
                Minor Requirements & External Documents
                <span className="ml-2 text-gray-400 font-normal normal-case">({minor.length} items{missingMinor > 0 ? `, ${missingMinor} missing` : ''})</span>
              </h3>
              <p className="text-xs text-gray-400 mt-0.5 text-left">Missing minor items trigger FSS attention but don't block processing</p>
            </div>
            <span className="text-gray-400 text-xs ml-4">{showMinor ? '▲ Collapse' : '▼ Expand'}</span>
          </button>
          {showMinor && (
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-50">
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Requirement</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Source</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide w-28">Status</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Note</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-gray-400 uppercase tracking-wide text-right w-32">Action</th>
                </tr>
              </thead>
              <tbody>
                {minor.map((item, i) => <NbRow key={i} item={item} caseId={caseId} />)}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export default function KeyChecksPanel({ extractions, nbRequirements, caseId }) {
  const crucial = nbRequirements?.crucial || []
  const missingCount = crucial.filter(i => i.status === 'missing').length

  return (
    <div>
      {/* Summary bar */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-base font-bold text-gray-900">Key Underwriting Checks</h2>
          <p className="text-xs text-gray-500 mt-0.5">8 required fields evaluated for Life GAE applications</p>
        </div>
        {missingCount > 0 ? (
          <div className="text-xs font-semibold px-3 py-1.5 rounded-full bg-red-50 text-red-700 border border-red-200">
            {missingCount} item{missingCount !== 1 ? 's' : ''} need attention
          </div>
        ) : (
          <div className="text-xs font-semibold px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            All key checks passed
          </div>
        )}
      </div>

      {/* 8 check cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Check1_AgeGender    extractions={extractions} nbRequirements={nbRequirements} caseId={caseId} />
        <Check2_Q14          extractions={extractions} caseId={caseId} />
        <Check3_PayoutOption extractions={extractions} caseId={caseId} />
        <Check4_USPerson     extractions={extractions} caseId={caseId} />
        <Check5_HeightWeight />
        <Check6_ContactDetails extractions={extractions} caseId={caseId} />
        <Check7_Signatures   extractions={extractions} nbRequirements={nbRequirements} caseId={caseId} />
        <Check8_Beneficiary  extractions={extractions} caseId={caseId} />
      </div>

      {/* Full NB Requirements Checklist */}
      <NbRequirementsSection nbRequirements={nbRequirements} caseId={caseId} />
    </div>
  )
}
