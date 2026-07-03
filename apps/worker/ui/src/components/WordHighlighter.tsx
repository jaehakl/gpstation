export type WordHighlighterWord = {
  id: string;
  wordId: number | null;
  surface: string;
  lemma: string;
  jpPron: string;
  krMean: string;
  userWordSkill: {
    reading: number;
  } | null;
};

type WordHighlighterProps = {
  words: WordHighlighterWord[];
  selectedWordId: string | null;
  onWordSelect: (word: WordHighlighterWord) => void;
  emptyText: string;
};

type WordSkillStatus = 'unregistered' | 'new' | 'learning' | 'mastered';

const skillStatusClasses: Record<WordSkillStatus, string> = {
  unregistered: 'border-[#dcdcdc] bg-white text-[#1f1f1f]',
  new: 'border-[#ffc9a3] bg-[#fff7ed] text-[#9a3412]',
  learning: 'border-[#9bd8c1] bg-[#ecfdf5] text-[#066047]',
  mastered: 'bg-transparent text-[#555555]',
};

function getSkillStatus(word: WordHighlighterWord): WordSkillStatus {
  if (word.wordId == null) {
    return 'unregistered';
  }

  const reading = word.userWordSkill?.reading ?? null;
  if (reading == null) {
    return 'new';
  }
  if (reading >= 100) {
    return 'mastered';
  }
  return reading > 0 ? 'learning' : 'new';
}

export function WordHighlighter({
  words,
  selectedWordId,
  onWordSelect,
  emptyText,
}: WordHighlighterProps) {
  if (words.length === 0) {
    return (
      <div className="flex min-h-[136px] items-center justify-center rounded-lg border border-dashed border-[var(--app-border)] bg-[#fafafa] px-4 py-8 text-center text-sm font-bold text-[var(--app-muted)]">
        {emptyText}
      </div>
    );
  }

  return (
    <div className="min-h-[136px] rounded-lg border border-[var(--app-border)] bg-white px-4 py-4 text-lg font-bold leading-9 text-[var(--app-text)]">
      {words.map((word) => {
        const isSelected = word.id === selectedWordId;
        const skillStatus = getSkillStatus(word);

        return (
          <button
            key={word.id}
            type="button"
            title={`${word.lemma} / ${word.jpPron || '-'} / ${word.krMean || '-'}`}
            className={[
              'inline-flex max-w-full items-center align-baseline font-black transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]',
              skillStatus === 'mastered'
                ? 'mx-0 rounded-none border-0 px-[1px] py-0 leading-[inherit]'
                : 'mx-0.5 min-h-8 rounded-md border px-2 py-0.5',
              skillStatusClasses[skillStatus],
              isSelected ? 'shadow-[0_0_0_2px_rgba(209,67,67,0.42)]' : 'hover:shadow-sm',
            ].join(' ')}
            onClick={() => onWordSelect(word)}
          >
            <span className="truncate">{word.surface}</span>
          </button>
        );
      })}
    </div>
  );
}
