import { useCallback, useState } from 'react'

const DOC_TYPES = [
  {
    key: 'application_form',
    label: 'Application Form',
    icon: '📋',
    color: 'border-blue-400 bg-blue-50',
    activeColor: 'border-blue-500 bg-blue-100',
    badgeColor: 'bg-blue-100 text-blue-800',
  },
  {
    key: 'government_id',
    label: 'Government ID',
    icon: '🪪',
    color: 'border-emerald-400 bg-emerald-50',
    activeColor: 'border-emerald-500 bg-emerald-100',
    badgeColor: 'bg-emerald-100 text-emerald-800',
  },
  {
    key: 'policy_illustration',
    label: 'Policy Illustration',
    icon: '📄',
    color: 'border-purple-400 bg-purple-50',
    activeColor: 'border-purple-500 bg-purple-100',
    badgeColor: 'bg-purple-100 text-purple-800',
  },
]

const ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp'

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function DropZone({ docType, file, onFile }) {
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault()
      setDragging(false)
      const dropped = e.dataTransfer.files[0]
      if (dropped) onFile(docType.key, dropped)
    },
    [docType.key, onFile],
  )

  const handleChange = (e) => {
    if (e.target.files[0]) onFile(docType.key, e.target.files[0])
  }

  const zoneClass = dragging ? docType.activeColor : docType.color

  return (
    <div
      className={`relative flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-6 transition-colors cursor-pointer ${zoneClass}`}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => document.getElementById(`input-${docType.key}`).click()}
    >
      <input
        id={`input-${docType.key}`}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={handleChange}
      />

      <span className="text-3xl mb-2">{docType.icon}</span>
      <p className="font-semibold text-gray-700">{docType.label}</p>

      {file ? (
        <div className={`mt-3 px-3 py-1.5 rounded-full text-xs font-medium ${docType.badgeColor}`}>
          {file.name} &nbsp;·&nbsp; {formatBytes(file.size)}
        </div>
      ) : (
        <p className="text-xs text-gray-400 mt-2">PDF, JPG, PNG — drag &amp; drop or click</p>
      )}

      {file && (
        <button
          className="absolute top-2 right-2 text-gray-400 hover:text-red-500 text-sm"
          onClick={(e) => {
            e.stopPropagation()
            onFile(docType.key, null)
          }}
        >
          ✕
        </button>
      )}
    </div>
  )
}

export default function DocumentUploader({ files, onFileChange, onSubmit, onMock, loading }) {
  const canSubmit =
    !loading && files.application_form && files.government_id

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
      <h2 className="text-lg font-bold text-gray-800 mb-1">Upload Documents</h2>
      <p className="text-sm text-gray-500 mb-5">
        At minimum, upload the Application Form and Government ID to evaluate a case.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {DOC_TYPES.map((dt) => (
          <DropZone
            key={dt.key}
            docType={dt}
            file={files[dt.key]}
            onFile={onFileChange}
          />
        ))}
      </div>

      <div className="flex items-center gap-3 mt-6">
        <button
          onClick={onSubmit}
          disabled={!canSubmit}
          className={`px-6 py-2.5 rounded-lg font-semibold text-sm transition-colors ${
            canSubmit
              ? 'bg-indigo-600 hover:bg-indigo-700 text-white'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
          }`}
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8v8H4z"
                />
              </svg>
              Evaluating…
            </span>
          ) : (
            'Evaluate Case'
          )}
        </button>

        <button
          onClick={onMock}
          disabled={loading}
          className="px-5 py-2.5 rounded-lg font-semibold text-sm border border-gray-300 text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Load Mock Data
        </button>
      </div>
    </div>
  )
}
