'use client';

import { AdminGate } from '../AdminGate';
import { ImageExplorerPage } from '../../features/image-explorer/ImageExplorerPage';

export function ImageExplorerClientPage() {
  return (
    <AdminGate>
      <ImageExplorerPage />
    </AdminGate>
  );
}
