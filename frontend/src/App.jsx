import { useState } from 'react'
import axios from 'axios'
import DocumentUploader from './components/DocumentUploader'
import ExtractionPanel from './components/ExtractionPanel'
import ValidationPanel from './components/ValidationPanel'
import CaseScoreCard from './components/CaseScoreCard'

// Read API base from Vite environment variable (set in frontend/.env or at build time).
// Falls back to localhost for development when not provided.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const EMPTY_FILES = {
  application_form: null,
  government_id: null,
  policy_illustration: null,
}

export default function App() {
  const [files, setFiles] = useState(EMPTY_FILES)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleFileChange = (key, file) => {
    setFiles((prev) => ({ ...prev, [key]: file }))
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const form = new FormData()
      if (files.application_form) form.append('application_form', files.application_form)
      if (files.government_id) form.append('government_id', files.government_id)
      if (files.policy_illustration) form.append('policy_illustration', files.policy_illustration)

      const { data } = await axios.post(`${API_BASE}/api/evaluate-case`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleMock = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const { data } = await axios.get(`${API_BASE}/api/mock-evaluation`)
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load mock data')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <span className="text-white text-sm font-bold">ICR</span>
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900">Intelligent Case Review</h1>
            <p className="text-xs text-gray-500">Insurance Onboarding — Document Evaluation</p>
          </div>
          {result && (
            <div className="ml-auto">
              <span className="text-xs text-gray-400 font-mono">Case ID: {result.case_id}</span>
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        <DocumentUploader
          files={files}
          onFileChange={handleFileChange}
          onSubmit={handleSubmit}
          onMock={handleMock}
          loading={loading}
        />

        {/* Error state */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-sm text-red-700">
            <strong>Error:</strong> {error}
          </div>
        )}

        {result && (
          <>
            <CaseScoreCard
              caseScore={result.case_score}
              caseStatus={result.case_status}
              completeness={result.completeness}
              criticalFlags={result.critical_flags}
              warnings={result.warnings}
            />

            <ExtractionPanel extractions={result.extractions} />

            <ValidationPanel validations={result.validations} />
          </>
        )}
      </main>

      <footer className="text-center text-xs text-gray-400 py-6">
        ICR Prototype · Powered by GPT-4o (vision) + Tesseract OCR (government ID)
      </footer>
    </div>
  )
}
