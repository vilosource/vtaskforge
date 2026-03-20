import { useParams } from 'react-router-dom';
import { KanbanBoard } from './KanbanBoard';

export function BoardView() {
  const { id } = useParams<{ id: string }>();

  if (!id) {
    return <div className="error">Invalid workplan ID.</div>;
  }

  return <KanbanBoard workplanId={id} />;
}
