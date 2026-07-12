export type ThinkingEffort = 'default' | 'low';
export type ResponseFormat = 'text' | 'json';

type GenerationOptionsFieldsProps = {
  think: boolean;
  thinkingEffort: ThinkingEffort;
  responseFormat: ResponseFormat;
  onThinkChange: (value: boolean) => void;
  onThinkingEffortChange: (value: ThinkingEffort) => void;
  onResponseFormatChange: (value: ResponseFormat) => void;
};

export function GenerationOptionsFields({
  think,
  thinkingEffort,
  responseFormat,
  onThinkChange,
  onThinkingEffortChange,
  onResponseFormatChange,
}: GenerationOptionsFieldsProps) {
  return (
    <div className="formGrid compact">
      <label>
        <span>Thinking</span>
        <select value={think ? 'enabled' : 'disabled'} onChange={(event) => onThinkChange(event.target.value === 'enabled')}>
          <option value="enabled">Enabled</option>
          <option value="disabled">Disabled</option>
        </select>
      </label>
      <label>
        <span>Thinking Effort</span>
        <select
          value={thinkingEffort}
          disabled={!think}
          onChange={(event) => onThinkingEffortChange(event.target.value as ThinkingEffort)}
        >
          <option value="low">Low</option>
          <option value="default">Default</option>
        </select>
      </label>
      <label>
        <span>Response Format</span>
        <select value={responseFormat} onChange={(event) => onResponseFormatChange(event.target.value as ResponseFormat)}>
          <option value="text">Text</option>
          <option value="json">JSON</option>
        </select>
      </label>
    </div>
  );
}
