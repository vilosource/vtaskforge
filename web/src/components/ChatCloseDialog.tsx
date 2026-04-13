interface ChatCloseDialogProps {
  onRelease: () => void;
  onKeepAlive: () => void;
  onCancel: () => void;
}

export function ChatCloseDialog({ onRelease, onKeepAlive, onCancel }: ChatCloseDialogProps) {
  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface/80 backdrop-blur-sm rounded-xl">
      <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-5 mx-4 max-w-[320px] w-full">
        <h3 className="text-sm font-headline font-bold text-on-surface mb-1">
          Release architect session?
        </h3>
        <p className="text-xs text-on-surface-variant mb-4">
          Releasing will end the agent session. Keeping alive lets you reconnect later.
        </p>
        <div className="flex flex-col gap-2">
          <button
            data-testid="close-release"
            onClick={onRelease}
            className="w-full px-3 py-2 rounded-lg bg-error text-on-error text-sm font-medium hover:bg-error/90 transition-colors"
          >
            Release Session
          </button>
          <button
            data-testid="close-keep-alive"
            onClick={onKeepAlive}
            className="w-full px-3 py-2 rounded-lg bg-primary text-on-primary text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Keep Alive
          </button>
          <button
            data-testid="close-cancel"
            onClick={onCancel}
            className="w-full px-3 py-2 rounded-lg bg-surface-container-high text-on-surface text-sm font-medium hover:bg-surface-container-highest transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
