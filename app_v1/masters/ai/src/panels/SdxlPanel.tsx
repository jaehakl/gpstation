import { FileImage, ImageIcon, Send } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ReceivedFile } from '@gpstation/v1-master-js-sdk';

import { formatJson, parseRequiredFloat, parseRequiredInt } from '../format';
import type { AiSession } from '../useAiSession';

const SDXL_TIMEOUT_MS = 600_000;

type SdxlImageMeta = {
  attachment_id: string;
  name: string;
  format: string;
  mimeType: string;
  size: number;
  seed: number;
};

type SdxlResponse = {
  images: SdxlImageMeta[];
  count: number;
};

type DisplayFile = ReceivedFile & {
  url: string;
  isImage: boolean;
  meta?: SdxlImageMeta;
};

export function SdxlPanel({ session, active }: { session: AiSession; active: boolean }) {
  const [prompts, setPrompts] = useState('a compact workstation on a clean desk');
  const [negativePrompts, setNegativePrompts] = useState('');
  const [seeds, setSeeds] = useState('123');
  const [step, setStep] = useState('30');
  const [cfg, setCfg] = useState('7');
  const [width, setWidth] = useState('1024');
  const [height, setHeight] = useState('1024');
  const [format, setFormat] = useState('png');
  const [result, setResult] = useState<SdxlResponse | null>(null);
  const [rawJson, setRawJson] = useState('');
  const [files, setFiles] = useState<DisplayFile[]>([]);
  const filesRef = useRef<DisplayFile[]>([]);

  useEffect(() => {
    return () => revokeFiles(filesRef.current);
  }, []);

  if (!active) {
    return null;
  }

  function replaceFiles(nextFiles: DisplayFile[]) {
    revokeFiles(filesRef.current);
    filesRef.current = nextFiles;
    setFiles(nextFiles);
  }

  async function callSdxl() {
    let payload;
    try {
      payload = buildPayload({ prompts, negativePrompts, seeds, step, cfg, width, height, format });
    } catch (error) {
      session.reportError(error, 'ai.sdxl.t2i');
      return;
    }

    replaceFiles([]);
    try {
      const response = await session.runJob<typeof payload, SdxlResponse>('ai.sdxl.t2i', payload, SDXL_TIMEOUT_MS);
      const metaByAttachmentId = new Map(response.payload.images.map((image) => [image.attachment_id, image]));
      const nextFiles = response.files.map((file) => ({
        ...file,
        url: URL.createObjectURL(file.blob),
        isImage: Boolean(file.mimeType?.startsWith('image/')),
        meta: metaByAttachmentId.get(file.id),
      }));
      setResult(response.payload);
      setRawJson(formatJson(response.payload));
      replaceFiles(nextFiles);
    } catch {
      // The shared session hook records connection and job failures.
    }
  }

  return (
    <section className="tabGrid sdxlGrid">
      <div className="panel formPanel">
        <div className="panelHeader">
          <h2>ai.sdxl.t2i</h2>
          <ImageIcon size={17} aria-hidden="true" />
        </div>
        <label>
          <span>Prompts</span>
          <textarea value={prompts} onChange={(event) => setPrompts(event.target.value)} rows={5} />
        </label>
        <label>
          <span>Negative Prompts</span>
          <textarea value={negativePrompts} onChange={(event) => setNegativePrompts(event.target.value)} rows={4} />
        </label>
        <div className="formGrid compact">
          <label>
            <span>Seeds</span>
            <input value={seeds} onChange={(event) => setSeeds(event.target.value)} />
          </label>
          <label>
            <span>Format</span>
            <select value={format} onChange={(event) => setFormat(event.target.value)}>
              <option value="png">png</option>
              <option value="jpg">jpg</option>
            </select>
          </label>
          <label>
            <span>Step</span>
            <input value={step} inputMode="numeric" onChange={(event) => setStep(event.target.value)} />
          </label>
          <label>
            <span>CFG</span>
            <input value={cfg} inputMode="decimal" onChange={(event) => setCfg(event.target.value)} />
          </label>
          <label>
            <span>Width</span>
            <input value={width} inputMode="numeric" onChange={(event) => setWidth(event.target.value)} />
          </label>
          <label>
            <span>Height</span>
            <input value={height} inputMode="numeric" onChange={(event) => setHeight(event.target.value)} />
          </label>
        </div>
        <button
          type="button"
          className="primaryButton"
          onClick={() => {
            void callSdxl();
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
          <span>{result ? `${result.count} image(s)` : 'empty'}</span>
        </div>
        <pre className="resultBox">{rawJson || 'No metadata yet.'}</pre>
        <div className="imageResults">
          {files.map((file) => (
            <a key={file.id} className="imageResult" href={file.url} download={file.name || file.id}>
              {file.isImage ? <img src={file.url} alt={file.name || file.id} /> : <FileImage size={40} aria-hidden="true" />}
              <span>{file.meta?.name || file.name || file.id}</span>
              <span>
                {file.meta ? `seed ${file.meta.seed} | ` : ''}
                {formatBytes(file.size)}
              </span>
            </a>
          ))}
          {files.length === 0 ? <p className="emptyText">No image attachments yet.</p> : null}
        </div>
      </div>
    </section>
  );
}

function buildPayload(input: {
  prompts: string;
  negativePrompts: string;
  seeds: string;
  step: string;
  cfg: string;
  width: string;
  height: string;
  format: string;
}) {
  const prompts = parseLines(input.prompts);
  if (prompts.length === 0) {
    throw new Error('prompts is required');
  }
  const negativePrompts = parseLines(input.negativePrompts);
  return {
    prompts,
    negative_prompts: negativePrompts.length > 0 ? negativePrompts : undefined,
    seeds: parseSeeds(input.seeds),
    step: parseRequiredInt(input.step, 'step'),
    cfg: parseRequiredFloat(input.cfg, 'cfg'),
    width: parseRequiredInt(input.width, 'width'),
    height: parseRequiredInt(input.height, 'height'),
    format: input.format,
  };
}

function parseLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseSeeds(value: string): (number | null)[] | undefined {
  const items = value
    .split(/[\r\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (items.length === 0) {
    return undefined;
  }
  return items.map((item) => {
    if (item.toLowerCase() === 'null') {
      return null;
    }
    const parsed = Number(item);
    if (!Number.isInteger(parsed)) {
      throw new Error('seeds must be integers or null');
    }
    return parsed;
  });
}

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function revokeFiles(files: DisplayFile[]) {
  for (const file of files) {
    URL.revokeObjectURL(file.url);
  }
}
