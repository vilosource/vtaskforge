import type { ExecutionSummary } from '../api/tasks';

interface Props {
  summary: ExecutionSummary | null;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const min = Math.floor(seconds / 60);
  const sec = seconds % 60;
  return sec > 0 ? `${min}m ${sec}s` : `${min}m`;
}

export default function ExecutionSummaryCard({ summary }: Props) {
  if (!summary?.structured) return null;

  const s = summary.structured;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
        Execution Summary
      </h3>

      {/* NL summary (Phase B — null until then) */}
      {summary.nl_summary?.what_happened && (
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
          {summary.nl_summary.what_happened}
        </p>
      )}

      {/* Duration and turns */}
      <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400 mb-2">
        <span>{formatDuration(s.duration_seconds)}</span>
        <span>{s.turn_count} turns</span>
        {s.model && <span>{s.model}</span>}
      </div>

      {/* Tools used */}
      {s.tools_used.length > 0 && (
        <div className="mb-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Tools: </span>
          <span className="text-xs text-gray-600 dark:text-gray-300">
            {s.tools_used.join(', ')}
          </span>
        </div>
      )}

      {/* Files modified */}
      {s.files_modified.length > 0 && (
        <div className="mb-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Modified: </span>
          <div className="mt-1">
            {s.files_modified.map((f) => (
              <span key={f} className="inline-block text-xs font-mono bg-gray-100 dark:bg-gray-700 rounded px-1.5 py-0.5 mr-1 mb-1 text-gray-700 dark:text-gray-300">
                {f.split('/').pop()}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Test results */}
      {s.tests && (
        <div className="mb-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Tests: </span>
          <span className={`text-xs font-medium ${s.tests.failed > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {s.tests.passed} passed
            {s.tests.failed > 0 && `, ${s.tests.failed} failed`}
          </span>
        </div>
      )}

      {/* Commits */}
      {s.commits.length > 0 && (
        <div className="mb-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Commits: </span>
          <div className="mt-1">
            {s.commits.map((c, i) => (
              <div key={i} className="text-xs font-mono text-gray-600 dark:text-gray-300">
                {c}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Key decisions (Phase B) */}
      {summary.nl_summary?.key_decisions && summary.nl_summary.key_decisions.length > 0 && (
        <div className="mb-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Decisions: </span>
          <ul className="mt-1 text-xs text-gray-600 dark:text-gray-300 list-disc list-inside">
            {summary.nl_summary.key_decisions.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Failure reason (Phase B) */}
      {summary.nl_summary?.if_failed && (
        <div className="mb-2 p-2 bg-red-50 dark:bg-red-900/20 rounded">
          <span className="text-xs font-medium text-red-600 dark:text-red-400">
            {summary.nl_summary.if_failed}
          </span>
        </div>
      )}

      {/* Trace link */}
      {summary.trace_url && (
        <a
          href={summary.trace_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block mt-2 text-xs text-blue-600 dark:text-blue-400 hover:underline"
        >
          View Trace →
        </a>
      )}
    </div>
  );
}
