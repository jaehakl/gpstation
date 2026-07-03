import { AudioListPanel } from '../../../components/AudioListPanel';
import { AudioPanel } from '../../../components/AudioPanel';
import { useExampleExplorer } from '../ExampleExplorerContext';

export function ExplorerAudioPanel() {
  const { audio, selectedExample, session } = useExampleExplorer();

  return (
    <>
      <AudioPanel
        script={selectedExample?.jp_text ?? ''}
        exampleId={selectedExample?.id ?? null}
        onSavedAudioChange={audio.refreshSaved}
      />
      <AudioListPanel
        audios={audio.audios}
        isLoading={audio.isLoadingAudios}
        deletingAudioId={audio.deletingAudioId}
        canDelete={session.authReady && session.isAdmin && selectedExample?.id != null}
        onDelete={audio.deleteSaved}
        autoPlayKey={audio.autoPlayKey}
        gridClassName="sm:grid-cols-2 2xl:grid-cols-3"
        errors={audio.errors}
        message={audio.saveMessage}
      />
    </>
  );
}
