import { ImagePanel } from '../../../components/ImagePanel';
import { useExampleExplorer } from '../ExampleExplorerContext';

export function ExplorerImagePanel() {
  const { image } = useExampleExplorer();

  return <ImagePanel image={image} />;
}
