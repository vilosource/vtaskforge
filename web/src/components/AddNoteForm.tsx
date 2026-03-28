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
    <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Actor ID (e.g. human-jason)"
        value={actorId}
        onChange={(e) => setActorId(e.target.value)}
        className="bg-surface-container-low border-none rounded-lg px-3 py-2 text-sm font-body text-on-surface placeholder:text-on-surface-variant focus:ring-2 focus:ring-primary"
        aria-label="Actor ID"
      />
      <textarea
        placeholder="Add a note..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="bg-surface-container-low border-none rounded-lg px-3 py-2 text-sm font-body text-on-surface placeholder:text-on-surface-variant focus:ring-2 focus:ring-primary resize-y"
        rows={3}
        aria-label="Note text"
      />
      {mutation.isError && (
        <p className="text-sm text-error font-body" role="alert">
          Failed to add note. Please try again.
        </p>
      )}
      <button
        type="submit"
        disabled={!text.trim() || mutation.isPending}
        className="self-start inline-flex items-center justify-center px-4 py-2 font-headline text-xs font-bold rounded-full primary-gradient text-on-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {mutation.isPending ? 'Adding...' : 'Add note'}
      </button>
    </form>
  );
}
