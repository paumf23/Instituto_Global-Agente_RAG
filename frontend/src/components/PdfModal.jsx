export default function PdfModal({ docName, onClose }) {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const pdfUrl = `${API_URL}/documentos/${encodeURIComponent(docName)}`;

  const formatDocName = (name) => {
    return name.replace('.pdf', '').replace(/_/g, ' ');
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div className="modal-overlay" onClick={handleOverlayClick} id="pdf-modal">
      <div className="modal-content">
        <div className="modal-header">
          <div className="modal-title">
            <span>📑</span>
            {formatDocName(docName)}
          </div>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <a
              href={`${pdfUrl}?download=true`}
              className="modal-download-btn"
              title="Descargar PDF"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '18px',
                color: 'inherit',
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '4px'
              }}
            >
              📥
            </a>
            <button
              className="modal-close-btn"
              onClick={onClose}
              id="modal-close-btn"
              aria-label="Cerrar"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="modal-body">
          <iframe
            src={`${pdfUrl}#navpanes=0&zoom=100`}
            title={formatDocName(docName)}
          />
        </div>
      </div>
    </div>
  );
}
