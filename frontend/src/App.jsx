import { useState } from 'react'
import axios from 'axios'
import DocumentUploader from './components/DocumentUploader'
import KeyChecksPanel from './components/KeyChecksPanel'
import ValidationPanel from './components/ValidationPanel'
import FindingsPanel from './components/FindingsPanel'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const EMPTY_FILES = {
  application_form: null,
  government_id: null,
  policy_illustration: null,
}

const PRODUCT_TYPE_LABELS = {
  EAZY_HEALTH: 'eAZy Health',
  IHP: 'Individual Health Plan',
  UL_GAE: 'Unit-Linked GAE',
  UL_NON_GAE: 'Unit-Linked (Non-GAE)',
  TRAD_GAE: 'Traditional GAE',
  TRAD_NON_GAE: 'Traditional (Non-GAE)',
  UNKNOWN: 'Unknown Product',
}

const STATUS_CONFIG = {
  'Ready for Review': { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', dot: 'bg-emerald-500' },
  'Needs Attention':  { bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-200',   dot: 'bg-amber-500'   },
  'Incomplete / Refer Back': { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', dot: 'bg-red-500' },
}

const TABS = [
  { id: 'checks',      label: 'Key Checks',   icon: '✦' },
  { id: 'validation',  label: 'Validations',  icon: '⇄' },
  { id: 'review',      label: 'Human Review', icon: '◉' },
]

export default function App() {
  const [files, setFiles] = useState(EMPTY_FILES)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [page, setPage] = useState('upload')   // 'upload' | 'review'
  const [activeTab, setActiveTab] = useState('checks')

  const handleFileChange = (key, file) => {
    setFiles((prev) => ({ ...prev, [key]: file }))
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      if (files.application_form) form.append('application_form', files.application_form)
      if (files.government_id)    form.append('government_id', files.government_id)
      if (files.policy_illustration) form.append('policy_illustration', files.policy_illustration)

      const { data } = await axios.post(`${API_BASE}/api/evaluate-case`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(data)
      setPage('review')
      setActiveTab('checks')
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleMock = async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await axios.get(`${API_BASE}/api/mock-evaluation`)
      setResult(data)
      setPage('review')
      setActiveTab('checks')
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load mock data')
    } finally {
      setLoading(false)
    }
  }

  const handleBack = () => {
    setPage('upload')
    setResult(null)
    setError(null)
    setFiles(EMPTY_FILES)
  }

  const handleResumed = (updatedResult) => {
    setResult(updatedResult)
  }

  // ── Upload page ──────────────────────────────────────────────────────────────
  if (page === 'upload') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50 flex flex-col">
        <header className="bg-white border-b border-gray-100">
          <div className="max-w-5xl mx-auto px-8 py-5 flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-indigo-600 flex items-center justify-center shadow-sm">
              <span className="text-white text-sm font-bold tracking-tight">ICR</span>
            </div>
            <div>
              <h1 className="text-base font-bold text-gray-900 leading-tight">Intelligent Case Review</h1>
              <p className="text-xs text-gray-400">Life Insurance — New Business Evaluation</p>
            </div>
          </div>
        </header>

        <main className="flex-1 flex flex-col items-center justify-center px-6 py-12">
          <div className="w-full max-w-2xl">
            <div className="text-center mb-10">
              <div className="inline-flex items-center gap-2 bg-indigo-50 border border-indigo-100 text-indigo-600 text-xs font-semibold px-3 py-1.5 rounded-full mb-4">
                <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full"></span>
                Life GAE · Guaranteed Acceptance Endorsement
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload Case Documents</h2>
              <p className="text-sm text-gray-500 max-w-sm mx-auto">
                Upload the application form, government ID, and sales illustration to run automated checks.
              </p>
            </div>

            <DocumentUploader
              files={files}
              onFileChange={handleFileChange}
              onSubmit={handleSubmit}
              onMock={handleMock}
              loading={loading}
            />

            {error && (
              <div className="mt-4 bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
                <strong>Error:</strong> {error}
              </div>
            )}
          </div>
        </main>

        <footer className="text-center text-xs text-gray-300 py-5">
          ICR Prototype · GPT-4o Vision · Tesseract OCR
        </footer>
      </div>
    )
  }

  // ── Review page ──────────────────────────────────────────────────────────────
  const productLabel = PRODUCT_TYPE_LABELS[result?.product_type] || result?.product_type || 'Unknown'
  const caseStatus   = result?.case_status || 'Unknown'
  const statusCfg    = STATUS_CONFIG[caseStatus] || STATUS_CONFIG['Incomplete / Refer Back']
  const openCount    = (result?.findings || []).filter(f => f.status === 'open').length
  const failCount    = (result?.validations || []).filter(v => v.status === 'fail').length

  // Badge counts per tab
  const tabBadge = {
    checks:     null,
    validation: failCount > 0 ? failCount : null,
    review:     openCount > 0 ? openCount : null,
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Review header */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-4">
          <button
            onClick={handleBack}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 font-medium transition-colors group"
          >
            <span className="text-lg leading-none group-hover:-translate-x-0.5 transition-transform">←</span>
            <span>New Case</span>
          </button>

          <div className="w-px h-5 bg-gray-200" />

          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-lg bg-indigo-600 flex items-center justify-center">
              <span className="text-white text-xs font-bold">ICR</span>
            </div>
            <span className="text-sm font-semibold text-gray-800">{productLabel}</span>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <div className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${statusCfg.bg} ${statusCfg.text} ${statusCfg.border}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot}`}></span>
              {caseStatus}
            </div>
            <span className="text-xs text-gray-400 font-mono hidden sm:block">
              #{result?.case_id?.slice(0, 8)}
            </span>
          </div>
        </div>

        {/* Tab bar */}
        <div className="max-w-6xl mx-auto px-6">
          <nav className="flex gap-1 -mb-px">
            {TABS.map(tab => {
              const badge = tabBadge[tab.id]
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                    isActive
                      ? 'border-indigo-600 text-indigo-700'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-200'
                  }`}
                >
                  <span className="text-base leading-none">{tab.icon}</span>
                  {tab.label}
                  {badge !== null && (
                    <span className={`text-xs font-bold px-1.5 py-0.5 rounded-full ${
                      isActive ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {badge}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>
        </div>
      </header>

      {/* Tab content */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-6">
        {activeTab === 'checks' && (
          <KeyChecksPanel
            extractions={result?.extractions || {}}
            nbRequirements={result?.nb_requirements || {}}
            caseId={result?.case_id}
          />
        )}

        {activeTab === 'validation' && (
          <ValidationPanel
            validations={result?.validations || []}
            caseId={result?.case_id}
            extractions={result?.extractions || {}}
          />
        )}

        {activeTab === 'review' && (
          <div>
            {result?.findings && result.findings.length > 0 ? (
              <FindingsPanel
                findings={result.findings}
                caseId={result.case_id}
                onResumed={handleResumed}
              />
            ) : (
              <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center">
                <div className="text-4xl mb-3">✅</div>
                <h3 className="text-base font-semibold text-gray-800 mb-1">No items require human review</h3>
                <p className="text-sm text-gray-500">All automated checks passed cleanly. The case is ready to proceed.</p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
