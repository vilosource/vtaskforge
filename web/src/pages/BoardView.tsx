import { useParams } from 'react-router-dom';

export function BoardView() {
  const { id } = useParams<{ id: string }>();

  return (
    <div>
      <h1>Board View</h1>
      <p>Board for workplan <strong>{id}</strong> — stub. Implementation coming in a later task.</p>
    </div>
  );
}
