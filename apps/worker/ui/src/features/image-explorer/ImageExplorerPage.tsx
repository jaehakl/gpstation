import { ImageIcon } from 'lucide-react';
import { ImageExplorerProvider } from './ImageExplorerProvider';
import { ImageDetailPanel } from './components/ImageDetailPanel';
import { ImageListPanel } from './components/ImageListPanel';

export function ImageExplorerPage() {
  return (
    <ImageExplorerProvider>
      <ImageExplorerContent />
    </ImageExplorerProvider>
  );
}

function ImageExplorerContent() {
  return (
    <div className="mx-auto flex min-h-full w-full max-w-[1800px] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8 lg:py-6">
      <header className="rounded-lg border border-[#0f0f0f] bg-[#0f0f0f] px-5 py-5 text-white shadow-sm">
        <div className="flex items-center gap-4">
          <span className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-white text-[var(--app-accent)]">
            <ImageIcon className="h-6 w-6" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="text-xs font-black uppercase text-white/50">Onigiri Neo</p>
            <h1 className="mt-1 truncate text-2xl font-black leading-tight sm:text-3xl">
              Image Explorer
            </h1>
          </div>
        </div>
      </header>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(360px,0.95fr)_minmax(0,1.35fr)]">
        <ImageListPanel />
        <ImageDetailPanel />
      </div>
    </div>
  );
}
