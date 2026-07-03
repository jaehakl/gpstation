'use client';

import { AdminGate } from '../AdminGate';
import { ExampleEditorPage } from '../../features/example-editor/ExampleEditorPage';

export function ExampleEditorClientPage() {
  return (
    <AdminGate>
      <ExampleEditorPage />
    </AdminGate>
  );
}
