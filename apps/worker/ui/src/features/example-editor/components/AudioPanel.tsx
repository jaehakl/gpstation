import { AudioPanel as CommonAudioPanel } from '../../../components/AudioPanel';
import { AudioListPanel } from '../../../components/AudioListPanel';
import { useExampleEditor } from '../ExampleEditorContext';

export function AudioPanel() {
  const { audio, draft, save, session } = useExampleEditor();

  return (
    <>
      <CommonAudioPanel
        script={draft.value.generatedSentence}
        exampleId={save.savedExampleId}
        autoGenerateRequestKey={audio.autoGenerateRequestKey}
        onSavedAudioChange={audio.refreshSaved}
      />
      <AudioListPanel
        audios={audio.audios}
        isLoading={audio.isLoadingAudios}
        deletingAudioId={audio.deletingAudioId}
        canDelete={session.authReady && session.isAdmin && save.savedExampleId != null}
        onDelete={audio.deleteSaved}
        gridClassName="sm:grid-cols-2 xl:grid-cols-3"
        errors={audio.errors}
        message={audio.saveMessage}
      />
    </>
  );
}
