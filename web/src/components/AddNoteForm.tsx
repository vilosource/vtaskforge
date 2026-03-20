import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { addNote } from '../api/taskActions';

interface AddNoteFormProps {
  taskId: string;
}

export function AddNoteForm({ taskId }: AddNoteFormProps) {
  const [text, setText] = useState('');
  const [actorId, setActorId] = useState('human');
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => addNote(taskId, text, actorId),
    onSuccess: () => {
      setText('');
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    mutation.mutate();
  }

  return (
    <form className="add-note-form" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Actor ID (e.g. human-jason)"
        value={actorId}
        onChange={(e) => setActorId(e.target.value)}
        className="add-note-actor"
        aria-label="Actor ID"
      />
      <textarea
        placeholder="Add a note..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="add-note-input"
        rows={3}
        aria-label="Note text"
      />
      {mutation.isError && (
        <p className="add-note-error" role="alert">
          Failed to add note. Please try again.
        </p>
      )}
      <button
        type="submit"
        disabled={!text.trim() || mutation.isPending}
        className="btn btn-primary"
      >
        {mutation.isPending ? 'Adding...' : 'Add note'}
      </button>
    </form>
  );
}
