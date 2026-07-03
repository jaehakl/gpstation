export type ExampleDraft = {
  sourceSentence: string;
  seedWord: string;
  generatedSentence: string;
  krMeaning: string;
  speaker: string;
  tone: string;
  positivePrompt: string;
  negativePrompt: string;
};

export type EditorWordSkill = {
  id?: number | null;
  userId?: string | null;
  wordId: number;
  reading: number;
  listening: number;
  speaking: number;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type EditorWord = {
  id: string;
  wordId: number | null;
  lemmaId: number | null;
  surface: string;
  lemma: string;
  jpPron: string;
  krMean: string;
  userWordSkill: EditorWordSkill | null;
};

export type EditorAudio = {
  id: string;
  speaker: string;
  tone?: string;
  filename: string;
  duration?: string;
  createdAt: string;
  src?: string | null;
};

export type EditorImage = {
  id: string;
  title: string;
  prompt: string;
  negativePrompt: string;
  src: string | null;
  distanceLabel: string;
  linked: boolean;
};
