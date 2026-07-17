import { useState, useRef, useCallback, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import PdfModal from './components/PdfModal';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';


const INITIAL_DOCS = [
  'FAQ_Cursos_y_Certificados.pdf',
  'Politica_de_Reembolsos.pdf',
  'Programa_Becas_y_Afiliados.pdf',
  'Reglamento_del_Estudiante.pdf',
];


const PREGUNTAS = [
  { text: '¿Cómo funciona el programa de referidos?' },
  { text: '¿Quién eres y qué puedes hacer?' },
  { text: 'Si me voy de vacaciones un mes, ¿Puedo pausar el tiempo de mi curso y retomarlo a la vuelta?' },
  { text: '¿Cuántos días tengo para pedir un reembolso completo desde que empieza el curso?' },
  { text: '¿Cuál es la capital de Argentina?' },
  { text: '¿Qué promedio necesito para no perder mi beca?' },
];

export default function App() {
  const [documents, setDocuments] = useState(INITIAL_DOCS);
  const [modalDoc, setModalDoc] = useState(null);


  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [responseText, setResponseText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [metadata, setMetadata] = useState(null); // { tipo_pregunta, citas }
  const [hasResponded, setHasResponded] = useState(false);

  const inputRef = useRef(null);

  // ---------------------------------------------------------------
  // Enviar pregunta al backend mediante SSE
  // ---------------------------------------------------------------
  const handleSubmit = useCallback(async (questionText) => {
    const pregunta = (questionText || inputValue).trim();
    if (!pregunta || isLoading) return;

    // Estado inicial
    setCurrentQuestion(pregunta);
    setInputValue('');
    setIsLoading(true);
    setStatusMessage('');
    setResponseText('');
    setIsStreaming(true);
    setMetadata(null);
    setHasResponded(false);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pregunta }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulatedText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            const eventType = line.slice(6).trim();
            continue;
          }

          if (line.startsWith('data:')) {
            const rawData = line.slice(5).trim();
            if (!rawData) continue;
          }
        }
      }
    } catch (err) {
      console.error('Error en la consulta:', err);
      setResponseText('Ocurrió un error al procesar la consulta. Asegurate de que el backend esté corriendo.');
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
      setStatusMessage('');
      setHasResponded(true);
    }
  }, [inputValue, isLoading]);


  const handleSubmitSSE = useCallback(async (questionText) => {
    const pregunta = (questionText || inputValue).trim();
    if (!pregunta || isLoading) return;

    setCurrentQuestion(pregunta);
    setInputValue('');
    setIsLoading(true);
    setStatusMessage('');
    setResponseText('');
    setIsStreaming(true);
    setMetadata(null);
    setHasResponded(false);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pregunta }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulatedText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Normalizar \r\n a \n (sse-starlette envía \r\n)
        buffer = buffer.replace(/\r\n/g, '\n');

        const eventBlocks = buffer.split('\n\n');
        buffer = eventBlocks.pop() || '';

        for (const block of eventBlocks) {
          if (!block.trim()) continue;

          const blockLines = block.trim().split('\n');
          let eventType = '';
          let eventData = '';

          for (const bLine of blockLines) {
            if (bLine.startsWith('event:')) {
              eventType = bLine.slice(6).trim();
            } else if (bLine.startsWith('data:')) {
              eventData = bLine.slice(5).trim();
            }
          }

          if (!eventType) continue;

          if (eventType === 'status') {
            try {
              const parsed = JSON.parse(eventData);
              setStatusMessage(parsed.message);
            } catch { }
          } else if (eventType === 'token') {
            try {
              const parsed = JSON.parse(eventData);
              accumulatedText += parsed.token;
              setResponseText(accumulatedText);
            } catch { }
          } else if (eventType === 'metadata') {
            try {
              const parsed = JSON.parse(eventData);
              setMetadata(parsed);
            } catch { }
          } else if (eventType === 'done') {
          }
        }
      }
    } catch (err) {
      console.error('Error en la consulta:', err);
      setResponseText('Ocurrió un error al procesar la consulta. Asegurate de que el backend esté corriendo.');
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
      setStatusMessage('');
      setHasResponded(true);
    }
  }, [inputValue, isLoading]);

  // ---------------------------------------------------------------
  // Preguntas predefinidas
  // ---------------------------------------------------------------
  const handlePreguntaClick = useCallback((text) => {
    setInputValue(text);
    setTimeout(() => {
      handleSubmitSSE(text);
    }, 150);
  }, [handleSubmitSSE]);

  // ---------------------------------------------------------------
  // Carga de archivos PDF
  // ---------------------------------------------------------------
  const handleFileUpload = useCallback((file) => {
    if (!file || !file.name.endsWith('.pdf')) return;
    const name = file.name;
    if (!documents.includes(name)) {
      setDocuments(prev => [...prev, name]);
    }
  }, [documents]);

  // ---------------------------------------------------------------
  // Presionar tecla Enter
  // ---------------------------------------------------------------
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmitSSE();
    }
  }, [handleSubmitSSE]);

  // ---------------------------------------------------------------
  // Nuevo Chat / reset
  // ---------------------------------------------------------------
  const handleReset = useCallback(() => {
    setInputValue('');
    setCurrentQuestion('');
    setResponseText('');
    setStatusMessage('');
    setMetadata(null);
    setIsLoading(false);
    setIsStreaming(false);
    setHasResponded(false);
    inputRef.current?.focus();
  }, []);

  return (
    <div className="app-layout">
      <Sidebar
        documents={documents}
        onDocClick={(docName) => setModalDoc(docName)}
        onFileUpload={handleFileUpload}
      />

      <ChatArea
        preguntas={PREGUNTAS}
        inputValue={inputValue}
        onInputChange={setInputValue}
        onKeyDown={handleKeyDown}
        onSubmit={() => handleSubmitSSE()}
        onPreguntaClick={handlePreguntaClick}
        onReset={handleReset}
        isLoading={isLoading}
        statusMessage={statusMessage}
        currentQuestion={currentQuestion}
        responseText={responseText}
        isStreaming={isStreaming}
        metadata={metadata}
        hasResponded={hasResponded}
        inputRef={inputRef}
      />

      {modalDoc && (
        <PdfModal
          docName={modalDoc}
          onClose={() => setModalDoc(null)}
        />
      )}
    </div>
  );
}
