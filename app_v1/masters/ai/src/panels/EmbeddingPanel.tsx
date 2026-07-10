import { Hash, Send } from 'lucide-react';
import { useState } from 'react';

import { formatJson } from '../format';
import type { AiSession } from '../useAiSession';

const EMBEDDING_TIMEOUT_MS = 600_000;

type EmbeddingResponse = {
  embedding: number[];
  dimensions: number;
};

export function EmbeddingPanel({ session, active }: { session: AiSession; active: boolean }) {
  const [text, setText] = useState('GP Station AI slave embedding test');
  const [result, setResult] = useState<EmbeddingResponse | null>(null);
  const [rawJson, setRawJson] = useState('');

  if (!active) {
    return null;
  }

  async function callEmbeddings() {
    const payload = { text };
    try {
      const response = await session.runJob<typeof payload, EmbeddingResponse>(
        'ai.embeddings',
        payload,
        EMBEDDING_TIMEOUT_MS,
      );
      setResult(response.payload);
      setRawJson(formatJson(response.payload));
    } catch {
      // The shared session hook records connection and job failures.
    }
  }

  return (
    <section className="tabGrid workGrid">
      <div className="panel formPanel">
        <div className="panelHeader">
          <h2>ai.embeddings</h2>
          <Hash size={17} aria-hidden="true" />
        </div>
        <label>
          <span>Text</span>
          <textarea value={text} onChange={(event) => setText(event.target.value)} rows={10} />
        </label>
        <button
          type="button"
          className="primaryButton"
          onClick={() => {
            void callEmbeddings();
          }}
          disabled={session.busy}
        >
          <Send size={17} aria-hidden="true" />
          <span>Send</span>
        </button>
      </div>

      <div className="panel resultPanel">
        <div className="panelHeader">
          <h2>Output</h2>
          <span>{result ? `${result.dimensions} dims` : 'empty'}</span>
        </div>
        <div className="metricStrip">
          <div>
            <span>Dimensions</span>
            <strong>{result?.dimensions ?? '-'}</strong>
          </div>
          <div>
            <span>Preview</span>
            <strong>{result ? result.embedding.slice(0, 8).map((value) => Number(value).toFixed(4)).join(', ') : '-'}</strong>
          </div>
        </div>
        <pre className="resultBox">{rawJson || 'No raw result yet.'}</pre>
      </div>
    </section>
  );
}
