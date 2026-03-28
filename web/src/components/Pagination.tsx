interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between py-3">
      <span className="text-sm font-body text-on-surface-variant">
        {start}–{end} of {total}
      </span>
      <div className="flex items-center gap-2">
        <button
          className="px-3 py-1.5 text-sm font-headline font-bold text-on-surface-variant hover:text-on-surface disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          Prev
        </button>
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-on-primary text-sm font-headline font-bold">
          {page}
        </span>
        <span className="text-sm font-body text-on-surface-variant">
          / {totalPages}
        </span>
        <button
          className="px-3 py-1.5 text-sm font-headline font-bold text-on-surface-variant hover:text-on-surface disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
        >
          Next
        </button>
      </div>
    </div>
  );
}
