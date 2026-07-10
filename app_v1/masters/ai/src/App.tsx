import { Brain, Cable, Hash, ImageIcon, MessageCircle, Wifi } from 'lucide-react';
import { useState } from 'react';

import { ChatPanel } from './panels/ChatPanel';
import { ConnectionPanel } from './panels/ConnectionPanel';
import { EmbeddingPanel } from './panels/EmbeddingPanel';
import { LlmPanel } from './panels/LlmPanel';
import { SdxlPanel } from './panels/SdxlPanel';
import { useAiSession } from './useAiSession';

type TabId = 'connection' | 'llm' | 'chat' | 'embeddings' | 'sdxl';

const tabs = [
  { id: 'connection', label: 'Connection', icon: Cable },
  { id: 'llm', label: 'ai.llm', icon: Brain },
  { id: 'chat', label: 'ai.chat', icon: MessageCircle },
  { id: 'embeddings', label: 'ai.embeddings', icon: Hash },
  { id: 'sdxl', label: 'ai.sdxl.t2i', icon: ImageIcon },
] satisfies { id: TabId; label: string; icon: typeof Cable }[];

export function App() {
  const session = useAiSession();
  const [activeTab, setActiveTab] = useState<TabId>('connection');

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">GP Station v1</p>
          <h1>AI Master Console</h1>
        </div>
        <div className={session.busy ? 'statusPill connected' : 'statusPill'}>
          <Wifi size={16} aria-hidden="true" />
          <span>{session.status}</span>
        </div>
      </section>

      <nav className="tabBar" aria-label="AI test sections">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              type="button"
              key={tab.id}
              className={activeTab === tab.id ? 'tabButton active' : 'tabButton'}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={17} aria-hidden="true" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      <ConnectionPanel session={session} active={activeTab === 'connection'} />
      <LlmPanel session={session} active={activeTab === 'llm'} />
      <ChatPanel session={session} active={activeTab === 'chat'} />
      <EmbeddingPanel session={session} active={activeTab === 'embeddings'} />
      <SdxlPanel session={session} active={activeTab === 'sdxl'} />
    </main>
  );
}
