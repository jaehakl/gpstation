import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PencilLine, RefreshCw, Save, Sparkles, Volume2 } from 'lucide-react';
import { dbTables } from '../api/api';
import { voicevoxApi } from '../api/apiAi';
import type { VoicevoxSpeaker, VoicevoxSpeakerInfo, VoicevoxStyle } from '../api/apiAi';
import { useAuthStore } from '../stores/authStore';

export type AudioPanelPreview = {
  blob: Blob;
  filename: string;
  speaker: string;
  tone: string;
  text: string;
  styleId: number;
  url: string;
};

export type AudioPanelProps = {
  script: string;
  exampleId: number | null;
  autoGenerateRequestKey?: number;
  onSavedAudioChange?: () => Promise<void> | void;
};

const selectClass =
  'h-11 rounded-lg border border-[var(--app-border)] bg-white px-3 text-sm font-semibold text-[var(--app-text)] outline-none transition focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)] disabled:bg-[#f3f3f3] disabled:text-[var(--app-muted)]';
const textareaClass =
  'min-h-24 w-full rounded-lg border border-[var(--app-border)] bg-white px-3 py-2 text-sm font-semibold text-[var(--app-text)] outline-none transition placeholder:text-[#9a9a9a] focus:border-[var(--app-accent)] focus:ring-2 focus:ring-[var(--app-focus)]';

const BLACKLISTED_VOICEVOX_STYLE_IDS = new Set<number>([
  0, 1, 5, 7,
  15, 18, 19,
  22, 23, 24, 25, 26, 28, 
  32, 33, 34, 35, 38, 39,
  41, 42, 43, 44, 45, 46, 47, 48, 49,
  50, 52, 53, 56, 57, 58, 59,
  60, 62, 63, 64, 67,
  70, 71, 72, 73, 75, 76, 77, 78, 79, 80,
  84, 85, 86, 87, 89,
  90, 91, 92, 93, 95, 97, 98,
  101, 102, 103, 104, 105, 106, 
  110, 111, 112, 115, 116, 117,
  120, 121, 122, 123, 124, 125
]);

export function AudioPanel({
  script,
  exampleId,
  autoGenerateRequestKey = 0,
  onSavedAudioChange,
}: AudioPanelProps) {
  const user = useAuthStore((state) => state.user);
  const authReady = useAuthStore((state) => state.authReady);
  const isAdmin = user?.roles.includes('admin') ?? false;
  const [voicevoxSpeakers, setVoicevoxSpeakers] = useState<VoicevoxSpeaker[]>([]);
  const [selectedSpeakerInfo, setSelectedSpeakerInfo] = useState<{
    uuid: string;
    info: VoicevoxSpeakerInfo;
  } | null>(null);
  const [selectedSpeakerUuid, setSelectedSpeakerUuid] = useState('');
  const [selectedStyleId, setSelectedStyleId] = useState<number | null>(null);
  const [isLoadingSpeakers, setIsLoadingSpeakers] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [speakerError, setSpeakerError] = useState<string | null>(null);
  const [speakerInfoError, setSpeakerInfoError] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<AudioPanelPreview | null>(null);
  const [isEditingScript, setIsEditingScript] = useState(false);
  const [editableScript, setEditableScript] = useState(script);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const speakersLoadPromiseRef = useRef<Promise<VoicevoxSpeaker[]> | null>(null);
  const isMountedRef = useRef(true);
  const handledAutoGenerateKeyRef = useRef(0);
  const activeScript = isEditingScript ? editableScript : script;
  const normalizedScript = activeScript.trim();

  const talkSpeakers = useMemo(
    () =>
      voicevoxSpeakers
        .map((speaker) => ({
          ...speaker,
          styles: speaker.styles.filter(
            (style) =>
              (style.type == null || style.type === 'talk')
              && !BLACKLISTED_VOICEVOX_STYLE_IDS.has(style.id),
          ),
        }))
        .filter((speaker) => speaker.styles.length > 0),
    [voicevoxSpeakers],
  );
  const selectedSpeaker =
    talkSpeakers.find((speaker) => speaker.speaker_uuid === selectedSpeakerUuid)
    ?? talkSpeakers[0]
    ?? null;
  const toneOptions = selectedSpeaker?.styles ?? [];
  const selectedTone =
    toneOptions.find((style) => style.id === selectedStyleId)
    ?? toneOptions[0]
    ?? null;
  const selectedSpeakerUuidValue = selectedSpeaker?.speaker_uuid ?? '';
  const selectedStyleIdValue = selectedTone?.id ?? null;
  const selectedSpeakerMetadata =
    selectedSpeakerInfo?.uuid === selectedSpeakerUuidValue ? selectedSpeakerInfo.info : null;
  const selectedPortrait =
    selectedSpeakerMetadata?.style_infos?.find((styleInfo) => styleInfo.id === selectedStyleIdValue)
      ?.portrait
    ?? selectedSpeakerMetadata?.portrait
    ?? null;
  const saveDisabledReason =
    !preview
      ? '미리듣기 오디오를 먼저 생성해 주세요.'
      : preview.text !== normalizedScript
        ? '문장이 바뀌어 오디오를 다시 생성해 주세요.'
        : exampleId == null
          ? '예문이 저장/선택되어야 오디오를 저장할 수 있습니다.'
          : !authReady
            ? '사용자 정보를 확인 중입니다.'
            : !isAdmin
              ? 'admin 권한이 있어야 오디오를 저장할 수 있습니다.'
              : null;
  const canGenerate =
    !isGenerating && Boolean(normalizedScript) && selectedSpeaker != null && selectedTone != null;
  const canSave = !isSaving && saveDisabledReason == null;
  const errors = [
    speakerError,
    speakerInfoError,
    generationError,
    saveError,
  ].filter((message): message is string => Boolean(message));

  const loadVoicevoxSpeakers = useCallback(async () => {
    if (speakersLoadPromiseRef.current) {
      return speakersLoadPromiseRef.current;
    }

    setIsLoadingSpeakers(true);
    setSpeakerError(null);

    const loadPromise = voicevoxApi.speakers();
    speakersLoadPromiseRef.current = loadPromise;

    try {
      const speakers = await loadPromise;
      if (isMountedRef.current) {
        setVoicevoxSpeakers(speakers);
      }
      return speakers;
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : 'VOICEVOX 성우 목록을 불러오지 못했습니다.';
      if (isMountedRef.current) {
        setSpeakerError(message);
      }
      throw new Error(message);
    } finally {
      if (speakersLoadPromiseRef.current === loadPromise) {
        speakersLoadPromiseRef.current = null;
      }
      if (isMountedRef.current) {
        setIsLoadingSpeakers(false);
      }
    }
  }, []);

  const generateAudio = useCallback(async (
    text: string,
    speaker: VoicevoxSpeaker,
    tone: VoicevoxStyle,
  ) => {
    const trimmedText = text.trim();
    if (!trimmedText) {
      setGenerationError('일본어 문장을 입력해 주세요.');
      return;
    }
    if (isGenerating) {
      return;
    }

    setIsGenerating(true);
    setGenerationError(null);
    setSaveError(null);
    setSaveMessage(null);

    try {
      const audioQuery = await voicevoxApi.audioQuery({
        text: trimmedText,
        speaker: tone.id,
      });
      const blob = await voicevoxApi.synthesis(audioQuery, { speaker: tone.id });
      const url = URL.createObjectURL(blob);

      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
      previewUrlRef.current = url;
      setPreview({
        blob,
        filename: `voicevox-${tone.id}-${Date.now()}.wav`,
        speaker: speaker.name,
        tone: tone.name,
        text: trimmedText,
        styleId: tone.id,
        url,
      });
    } catch (error) {
      setGenerationError(
        error instanceof Error ? error.message : 'VOICEVOX 오디오 생성에 실패했습니다.',
      );
    } finally {
      setIsGenerating(false);
    }
  }, [isGenerating]);

  const rerollAndGenerate = useCallback(async () => {
    let speakers = talkSpeakers;

    if (speakers.length === 0) {
      try {
        const loadedSpeakers = await loadVoicevoxSpeakers();
        speakers = loadedSpeakers
          .map((speaker) => ({
            ...speaker,
            styles: speaker.styles.filter(
              (style) =>
                (style.type == null || style.type === 'talk')
                && !BLACKLISTED_VOICEVOX_STYLE_IDS.has(style.id),
            ),
          }))
          .filter((speaker) => speaker.styles.length > 0);
      } catch {
        return;
      }
    }

    const candidates = speakers.flatMap((speaker) =>
      speaker.styles.map((style) => ({ speaker, style })),
    );
    const candidate = candidates[Math.floor(Math.random() * candidates.length)] ?? null;
    if (!candidate) {
      setGenerationError('VOICEVOX 성우와 톤을 찾지 못했습니다.');
      return;
    }

    setSelectedSpeakerUuid(candidate.speaker.speaker_uuid);
    setSelectedStyleId(candidate.style.id);
    await generateAudio(normalizedScript, candidate.speaker, candidate.style);
  }, [generateAudio, loadVoicevoxSpeakers, normalizedScript, talkSpeakers]);

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  useEffect(() => {
    void loadVoicevoxSpeakers().catch(() => {});
  }, [loadVoicevoxSpeakers]);

  useEffect(() => {
    setEditableScript(script);
  }, [script]);

  useEffect(() => {
    let ignore = false;

    if (!selectedSpeakerUuidValue) {
      return () => {
        ignore = true;
      };
    }

    voicevoxApi
      .speakerInfo({ speaker_uuid: selectedSpeakerUuidValue, resource_format: 'url' })
      .then((info) => {
        if (!ignore) {
          setSelectedSpeakerInfo({ uuid: selectedSpeakerUuidValue, info });
          setSpeakerInfoError(null);
        }
      })
      .catch((error) => {
        if (!ignore) {
          setSelectedSpeakerInfo(null);
          setSpeakerInfoError(
            error instanceof Error ? error.message : '선택한 성우 정보를 불러오지 못했습니다.',
          );
        }
      });

    return () => {
      ignore = true;
    };
  }, [selectedSpeakerUuidValue]);

  useEffect(() => {
    const previewAudio = previewAudioRef.current;
    if (!previewAudio || !preview?.url) {
      return;
    }

    previewAudio.currentTime = 0;
    void previewAudio.play().catch(() => {});
  }, [preview?.url]);

  useEffect(() => {
    if (
      autoGenerateRequestKey <= 0
      || handledAutoGenerateKeyRef.current === autoGenerateRequestKey
    ) {
      return;
    }

    handledAutoGenerateKeyRef.current = autoGenerateRequestKey;
    void rerollAndGenerate();
  }, [autoGenerateRequestKey, rerollAndGenerate]);

  const handleSelectSpeaker = (speakerUuid: string) => {
    const speaker = talkSpeakers.find((item) => item.speaker_uuid === speakerUuid);
    const style = speaker?.styles[0] ?? null;
    if (speaker && style) {
      setSelectedSpeakerUuid(speaker.speaker_uuid);
      setSelectedStyleId(style.id);
      void generateAudio(normalizedScript, speaker, style);
    }
  };

  const handleSelectTone = (styleId: number) => {
    const style = toneOptions.find((item) => item.id === styleId);
    if (selectedSpeaker && style) {
      setSelectedSpeakerUuid(selectedSpeaker.speaker_uuid);
      setSelectedStyleId(style.id);
      void generateAudio(normalizedScript, selectedSpeaker, style);
    }
  };

  const handleToggleScriptEdit = () => {
    if (isEditingScript) {
      setIsEditingScript(false);
      return;
    }

    setEditableScript(script);
    setIsEditingScript(true);
  };

  const handleGenerate = () => {
    if (!selectedSpeaker || !selectedTone) {
      setGenerationError('성우와 톤을 선택해 주세요.');
      return;
    }

    void generateAudio(normalizedScript, selectedSpeaker, selectedTone);
  };

  const handleSave = async () => {
    if (!preview || exampleId == null || !authReady || !isAdmin || isSaving) {
      return;
    }

    setIsSaving(true);
    setSaveError(null);
    setSaveMessage(null);

    try {
      const file = new File([preview.blob], preview.filename, {
        type: preview.blob.type || 'audio/wav',
      });
      await dbTables.Audio.upsertFormRow(
        {
          example_id: exampleId,
          speaker: `${preview.speaker} · ${preview.tone}`,
        },
        { object_key: file },
      );
      await onSavedAudioChange?.();
      setSaveMessage('오디오를 저장했습니다.');
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : '오디오를 저장하지 못했습니다.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="rounded-lg border border-[var(--app-border)] bg-[var(--app-panel)] p-4 shadow-sm">
      <div className="flex flex-col gap-2 border-b border-[var(--app-border)] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase text-[var(--app-accent)]">Audio</p>
          <h2 className="mt-1 text-xl font-black text-[var(--app-text)]">오디오 생성</h2>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <button
            type="button"
            aria-pressed={isEditingScript}
            className={[
              'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
              isEditingScript
                ? 'border-[#2e2d2d] bg-[#0f0f0f] text-white hover:bg-[#242424]'
                : 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]',
            ].join(' ')}
            onClick={handleToggleScriptEdit}
          >
            <PencilLine className="h-4 w-4" aria-hidden="true" />
            직접 입력
          </button>
          <button
            type="button"
            disabled={!canGenerate}
            className={[
              'inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
              canGenerate
                ? 'border-[#b02c2c] bg-[var(--app-accent)] text-white hover:bg-[var(--app-accent-strong)]'
                : 'border-[var(--app-border)] bg-[#d1d1d1] text-white opacity-70',
            ].join(' ')}
            onClick={handleGenerate}
          >
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            {isGenerating ? '생성 중' : '생성'}
          </button>
        </div>
      </div>

      {isEditingScript ? (
        <label className="mt-4 grid gap-1.5 text-sm font-black text-[var(--app-text)]">
          생성 스크립트
          <textarea
            value={editableScript}
            rows={3}
            placeholder="VOICEVOX로 생성할 일본어 문장"
            className={textareaClass}
            onChange={(event) => setEditableScript(event.target.value)}
          />
        </label>
      ) : null}

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1.15fr)_minmax(220px,0.85fr)_auto] lg:items-stretch">
        <div className="flex min-w-0 items-center gap-3 rounded-lg border border-[var(--app-border)] bg-white p-3">
          {selectedPortrait ? (
            <img
              src={selectedPortrait}
              alt={selectedSpeaker?.name ?? 'VOICEVOX'}
              className="h-20 w-20 shrink-0 object-contain"
            />
          ) : (
            <Volume2 className="h-7 w-7 shrink-0 text-[var(--app-muted)]" aria-hidden="true" />
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-black text-[var(--app-text)]">
              {selectedSpeaker?.name ?? 'VOICEVOX'}
            </p>
            <p className="mt-1 truncate text-xs font-bold text-[var(--app-muted)]">
              {selectedTone ? `${selectedTone.name} #${selectedTone.id}` : '톤 없음'}
            </p>
            {speakerInfoError ? (
              <p className="mt-1 text-xs font-bold text-[#b02c2c]">{speakerInfoError}</p>
            ) : null}
          </div>
        </div>

        <div className="grid gap-3">
          <label className="grid">
            <span className="sr-only">성우</span>
            <select
              value={selectedSpeakerUuidValue}
              disabled={isLoadingSpeakers || talkSpeakers.length === 0}
              className={selectClass}
              onChange={(event) => handleSelectSpeaker(event.target.value)}
            >
              {talkSpeakers.length === 0 ? (
                <option value="">성우 없음</option>
              ) : (
                talkSpeakers.map((speaker) => (
                  <option key={speaker.speaker_uuid} value={speaker.speaker_uuid}>
                    {speaker.name}
                  </option>
                ))
              )}
            </select>
          </label>
          <label className="grid">
            <span className="sr-only">톤</span>
            <select
              value={selectedStyleIdValue ?? ''}
              disabled={toneOptions.length === 0}
              className={selectClass}
              onChange={(event) => handleSelectTone(Number(event.target.value))}
            >
              {toneOptions.length === 0 ? (
                <option value="">톤 없음</option>
              ) : (
                toneOptions.map((tone) => (
                  <option key={tone.id} value={tone.id}>
                    {tone.name}
                  </option>
                ))
              )}
            </select>
          </label>
        </div>

        <button
          type="button"
          title="무작위 reroll"
          disabled={talkSpeakers.length === 0 || isGenerating}
          className="inline-flex min-h-11 items-center justify-center gap-2 self-stretch rounded-lg border border-[#2e2d2d] bg-white px-3 text-sm font-black transition hover:bg-[#f3f3f3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:border-[var(--app-border)] disabled:text-[var(--app-muted)] disabled:opacity-70"
          onClick={() => {
            void rerollAndGenerate();
          }}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Reroll
        </button>
      </div>

      <div className="mt-4 grid gap-3">
        {preview ? (
          <div className="rounded-lg border border-[var(--app-border)] bg-white p-3">
            <div className="flex items-start gap-3">
              <div className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#0f0f0f] text-white">
                <Volume2 className="h-5 w-5" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-black text-[var(--app-text)]">
                  {preview.filename}
                </p>
                <p className="mt-1 truncate text-xs font-bold text-[var(--app-muted)]">
                  {preview.speaker} · {preview.tone} · #{preview.styleId}
                </p>
              </div>
            </div>
            <audio
              ref={previewAudioRef}
              controls
              src={preview.url}
              className="mt-3 w-full"
            />
            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs font-bold text-[var(--app-muted)]">
                {saveDisabledReason ?? '백엔드에 저장할 수 있습니다.'}
              </p>
              <button
                type="button"
                disabled={!canSave}
                className={[
                  'inline-flex h-9 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                  canSave
                    ? 'border-[#2e2d2d] bg-white text-[var(--app-text)] hover:bg-[#f3f3f3]'
                    : 'border-[var(--app-border)] bg-[#f3f3f3] text-[var(--app-muted)] opacity-70',
                ].join(' ')}
                onClick={() => {
                  void handleSave();
                }}
              >
                <Save className="h-4 w-4" aria-hidden="true" />
                {isSaving ? '저장 중' : '오디오 저장'}
              </button>
            </div>
          </div>
        ) : (
          <div className="flex min-h-[112px] items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 text-center text-sm font-bold text-[var(--app-muted)]">
            미리듣기 오디오가 없습니다.
          </div>
        )}

        {errors.map((message) => (
          <p key={message} className="text-xs font-black text-[var(--app-accent)]">
            {message}
          </p>
        ))}
        {saveMessage ? (
          <p className="text-xs font-black text-[#167347]">{saveMessage}</p>
        ) : null}
      </div>
    </section>
  );
}
