import { useEffect, useRef } from 'react';
import { Play, Trash2, Volume2 } from 'lucide-react';

export type AudioListItem = {
  id: string;
  speaker: string;
  tone?: string;
  duration?: string;
  filename: string;
  src?: string | null;
};

export type AudioListPanelProps = {
  audios: AudioListItem[];
  isLoading: boolean;
  deletingAudioId: string | null;
  canDelete: boolean;
  onDelete: (audioId: string) => Promise<void> | void;
  autoPlayKey?: number;
  gridClassName: string;
  errors?: string[];
  message?: string | null;
};

export function AudioListPanel({
  audios,
  isLoading,
  deletingAudioId,
  canDelete,
  onDelete,
  autoPlayKey = 0,
  gridClassName,
  errors = [],
  message = null,
}: AudioListPanelProps) {
  const savedAudioRefs = useRef<Record<string, HTMLAudioElement | null>>({});

  useEffect(() => {
    if (autoPlayKey <= 0) {
      return;
    }

    const firstPlayableAudio = audios.find((savedAudio) => savedAudio.src);
    if (!firstPlayableAudio) {
      return;
    }

    const audioElement = savedAudioRefs.current[firstPlayableAudio.id];
    if (!audioElement) {
      return;
    }

    audioElement.currentTime = 0;
    void audioElement.play().catch(() => {});
  }, [audios, autoPlayKey]);

  return (
    <section className="rounded-lg border border-[var(--app-border)] bg-[var(--app-panel)] p-4 shadow-sm">
      <div className="flex flex-col gap-2 border-b border-[var(--app-border)] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase text-[var(--app-accent)]">Audio</p>
          <h2 className="mt-1 text-xl font-black text-[var(--app-text)]">저장된 오디오</h2>
        </div>
      </div>

      <div className={['mt-4 grid gap-3', gridClassName].join(' ')}>
        {isLoading ? (
          <div className="col-span-full flex min-h-[132px] items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 text-center text-sm font-bold text-[var(--app-muted)]">
            오디오를 불러오는 중입니다.
          </div>
        ) : audios.length === 0 ? (
          <div className="col-span-full flex min-h-[132px] items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 text-center text-sm font-bold text-[var(--app-muted)]">
            저장된 오디오가 없습니다.
          </div>
        ) : (
          audios.map((savedAudio) => {
            const metadata = [savedAudio.speaker, savedAudio.tone, savedAudio.duration]
              .filter(Boolean)
              .join(' · ');
            const savedAudioId = Number(savedAudio.id);
            const isValidAudioId = Number.isInteger(savedAudioId);
            const isDeletingAudio = deletingAudioId === savedAudio.id;
            const canDeleteAudio = canDelete && isValidAudioId && deletingAudioId == null;

            return (
              <article
                key={savedAudio.id}
                className="rounded-lg border border-[var(--app-border)] bg-white p-3 shadow-sm"
              >
                <div className="flex items-start gap-3">
                  <div className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#0f0f0f] text-white">
                    <Volume2 className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-black text-[var(--app-text)]">
                      {savedAudio.filename}
                    </p>
                    {metadata ? (
                      <p className="mt-1 truncate text-xs font-bold text-[var(--app-muted)]">
                        {metadata}
                      </p>
                    ) : null}
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  {savedAudio.src ? (
                    <audio
                      ref={(element) => {
                        savedAudioRefs.current[savedAudio.id] = element;
                      }}
                      controls
                      src={savedAudio.src}
                      className="min-w-0 flex-1"
                    />
                  ) : (
                    <button
                      type="button"
                      disabled
                      className="inline-flex h-9 flex-1 items-center justify-center gap-2 rounded-lg border border-[var(--app-border)] bg-white text-sm font-black opacity-65"
                    >
                      <Play className="h-4 w-4" aria-hidden="true" />
                      재생
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={!canDeleteAudio}
                    aria-label={isDeletingAudio ? '오디오 삭제 중' : '오디오 삭제'}
                    title={isDeletingAudio ? '삭제 중' : '삭제'}
                    className={[
                      'inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#ffd1d1] bg-white text-[var(--app-accent)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
                      canDeleteAudio ? 'hover:bg-[#fff4f4]' : 'cursor-not-allowed opacity-65',
                    ].join(' ')}
                    onClick={() => {
                      if (window.confirm('이 오디오를 삭제할까요?')) {
                        void onDelete(savedAudio.id);
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </article>
            );
          })
        )}
      </div>

      {errors.length > 0 || message ? (
        <div className="mt-3 grid gap-2">
          {errors.map((error) => (
            <p key={error} className="text-xs font-black text-[var(--app-accent)]">
              {error}
            </p>
          ))}
          {message ? (
            <p className="text-xs font-black text-[#167347]">{message}</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
