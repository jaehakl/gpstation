import { ImagePanel as CommonImagePanel } from '../../../components/ImagePanel';
import { useExampleEditor } from '../ExampleEditorContext';

export function ImagePanel() {
  const { image } = useExampleEditor();

  return <CommonImagePanel image={image} />;
}
