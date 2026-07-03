'use client';

import { AdminGate } from '../AdminGate';
import { ExampleExplorerPage } from '../../features/example-explorer/ExampleExplorerPage';

export function ExampleExplorerClientPage() {
  return (
    <AdminGate>
      <ExampleExplorerPage />
    </AdminGate>
  );
}
