import { useEffect, useRef } from 'react';

export default function ChatArea({
  preguntas,
  inputValue,
  onInputChange,
  onKeyDown,
  onSubmit,
  onPreguntaClick,
  onReset,
  isLoading,
  statusMessage,
  currentQuestion,
  responseText,
  isStreaming,
  metadata,
  hasResponded,
  inputRef,
}) {
  const responseEndRef = useRef(null);

  // Auto-scroll as response streams in
  useEffect(() => {
    if (responseText || statusMessage) {
      responseEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [responseText, statusMessage]);

  const showPreguntas = !isLoading && !hasResponded;

  return (
    <main className="main-area" id="main-area">
      {/* Header bar with slogan */}
      <div className="header-bar">
        <div className="slogan-badge">Educación sin fronteras, futuro sin límites</div>
      </div>

      {/* Chat container */}
      <div className="chat-container" id="chat-container">
        {/* Welcome */}
        {showPreguntas && (
          <div className="welcome-section">
            <h2 className="welcome-title">Hola, preguntame lo que quieras</h2>
            <p className="welcome-subtitle">Soy el asistente virtual de Instituto Global</p>
          </div>
        )}

        {/* Predefined questions */}
        {showPreguntas && (
          <div className="preguntas-grid" id="preguntas-grid">
            {preguntas.map((p, idx) => (
              <button
                key={idx}
                className="pregunta-btn"
                onClick={() => onPreguntaClick(p.text)}
                id={`pregunta-btn-${idx}`}
              >
                <span className="pregunta-btn-icon">{p.icon}</span>
                <span>{p.text}</span>
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="input-area" id="input-area">
          <div className="input-wrapper">
            <input
              ref={inputRef}
              type="text"
              className="input-field"
              placeholder="Escribí tu pregunta acá..."
              value={inputValue}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={onKeyDown}
              disabled={isLoading}
              id="question-input"
              autoComplete="off"
            />
            <button
              className="send-btn"
              onClick={onSubmit}
              disabled={isLoading || !inputValue.trim()}
              id="send-btn"
              aria-label="Enviar"
            >
              {isLoading ? '⏳' : '➤'}
            </button>
          </div>
        </div>

        {/* User question bubble */}
        {currentQuestion && (isLoading || hasResponded) && (
          <div className="user-question">
            <div className="user-question-bubble">{currentQuestion}</div>
          </div>
        )}

        {/* Status messages (process feedback) */}
        {statusMessage && (
          <div className="status-container" id="status-container">
            <div className="status-message" key={statusMessage}>
              <span className="status-dot" />
              {statusMessage}
            </div>
          </div>
        )}

        {/* Response */}
        {(responseText || hasResponded) && responseText && (
          <div className="response-area" id="response-area">
            <div className="response-card">
              <div className="response-label">
                <span className="response-label-dot" />
                Respuesta
                {metadata?.tipo_pregunta && (
                  <span className={`tipo-badge ${metadata.tipo_pregunta}`}>
                    {metadata.tipo_pregunta === 'consulta_academica'
                      ? '📚 Académica'
                      : metadata.tipo_pregunta === 'charla_casual'
                      ? '💬 Casual'
                      : '🚫 Fuera de tema'}
                  </span>
                )}
              </div>
              <div className={`response-text ${isStreaming ? 'streaming-cursor' : ''}`}>
                {responseText}
              </div>

              {/* Citations */}
              {metadata?.citas && metadata.citas.length > 0 && (
                <div className="citations-section">
                  <div className="citations-title">📎 Fuentes</div>
                  <div className="citations-list">
                    {metadata.citas.map((cita, idx) => (
                      <span key={idx} className="citation-chip">
                        📑 {cita}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* New question button after response */}
        {hasResponded && !isLoading && (
          <div style={{ textAlign: 'center', marginTop: '16px' }}>
            <button
              className="pregunta-btn"
              onClick={onReset}
              id="new-question-btn"
              style={{ display: 'inline-flex', justifyContent: 'center' }}
            >
              🔄 Nueva consulta
            </button>
          </div>
        )}

        <div ref={responseEndRef} />
      </div>
    </main>
  );
}
