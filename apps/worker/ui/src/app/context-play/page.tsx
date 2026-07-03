import { redirect } from 'next/navigation';
import { fetchRandomExampleId } from '../../api/serverApi';

export const dynamic = 'force-dynamic';

export default async function ContextPlayIndexPage() {
  const exampleId = await fetchRandomExampleId();

  if (exampleId) {
    redirect(`/context-play/${exampleId}`);
  }

  return (
    <div className="flex min-h-full items-center justify-center px-4 text-center text-sm font-black text-[var(--app-accent)]">
      이동할 예문을 찾지 못했습니다.
    </div>
  );
}
