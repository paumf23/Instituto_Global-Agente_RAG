export default function PdfModal({ docName, onClose }) {
  // Use the backend to serve the PDF, or fall back to the /documentos path
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
          <button
            className="modal-close-btn"
            onClick={onClose}
            id="modal-close-btn"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>
        <div className="modal-body">
          <iframe
            src={pdfUrl}
            title={formatDocName(docName)}
          />
        </div>
      </div>
    </div>
  );
}
