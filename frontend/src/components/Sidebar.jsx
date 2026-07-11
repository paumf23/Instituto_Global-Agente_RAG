import { useRef } from 'react';

export default function Sidebar({ documents, onDocClick, onFileUpload }) {
  const fileInputRef = useRef(null);

  const handleChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileUpload(file);
      e.target.value = ''; // reset so the same file can be re-uploaded
    }
  };

  const formatDocName = (name) => {
    return name
      .replace('.pdf', '')
      .replace(/_/g, ' ');
  };

  return (
    <aside className="sidebar" id="sidebar">
      {/* Logo & brand */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <img src="/logo.png" alt="Instituto Global" />
          <h1>Instituto Global</h1>
        </div>
        <p className="sidebar-logo-slogan">Educación sin fronteras, futuro sin límites</p>
      </div>

      {/* Upload */}
      <div className="sidebar-upload">
        <div className="sidebar-section-title">Ingresar documento</div>
        <div className="upload-area" onClick={() => fileInputRef.current?.click()}>
          <input
            type="file"
            ref={fileInputRef}
            accept=".pdf"
            onChange={handleChange}
            id="file-upload-input"
          />
          <div className="upload-icon">📄</div>
          <div className="upload-text">
            <strong>Hacé clic</strong> o arrastrá un PDF
          </div>
        </div>
      </div>

      {/* Document list */}
      <div className="sidebar-documents">
        <div className="sidebar-section-title">Documentos</div>
        {documents.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📂</div>
            <div className="empty-state-text">No hay documentos cargados</div>
          </div>
        ) : (
          <ul className="doc-list" id="doc-list">
            {documents.map((doc, idx) => (
              <li key={doc}>
                <button
                  className={`doc-item ${idx >= 4 ? 'doc-item-new' : ''}`}
                  onClick={() => onDocClick(doc)}
                  id={`doc-item-${idx}`}
                  title={formatDocName(doc)}
                >
                  <span className="doc-item-icon">📑</span>
                  <span className="doc-item-name">{formatDocName(doc)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
