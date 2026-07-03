import { notFound } from 'next/navigation';
import { ContextPlayPage } from '../../../features/play-context/ContextPlayPage';

export const dynamic = 'force-dynamic';

type ContextPlayDetailPageProps = {
  params: Promise<{
    example_id: string;
  }>;
};

export default async function ContextPlayDetailPage({
  params,
}: ContextPlayDetailPageProps) {
  const { example_id: rawExampleId } = await params;
  const exampleId = Number(rawExampleId);

  if (!Number.isInteger(exampleId) || exampleId <= 0) {
    notFound();
  }

  return (
    <ContextPlayPage
      key={exampleId}
      exampleId={exampleId}
    />
  );
}
