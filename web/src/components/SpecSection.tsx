import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ParsedSpec } from '../utils/parseSpec';

interface SpecSectionProps {
  spec: ParsedSpec;
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="text-sm font-semibold text-on-surface mt-4 mb-2 first:mt-0">
      {children}
    </h4>
  );
}

function FileList({ label, files, color }: { label: string; files: string[]; color: string }) {
  if (files.length === 0) return null;
  return (
    <div className="mb-2">
      <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ background: color }} />
      <span className="text-xs text-on-surface-variant font-semibold">{label}</span>
      <ul className="mt-1 ml-5 space-y-0.5">
        {files.map(f => (
          <li key={f} className="font-mono text-xs text-on-surface">
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SpecSection({ spec }: SpecSectionProps) {
  const [rawExpanded, setRawExpanded] = useState(false);

  const hasFiles = spec.files.create.length > 0 || spec.files.modify.length > 0 || spec.files.affected.length > 0;

  return (
    <div>
      {/* Implementation Approach */}
      {spec.approach && (
        <>
          <SectionHeading>Implementation Approach</SectionHeading>
          <div className="spec-markdown text-[13px] leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{spec.approach}</ReactMarkdown>
          </div>
        </>
      )}

      {/* Files */}
      {hasFiles && (
        <>
          <SectionHeading>Files</SectionHeading>
          <FileList label="Create" files={spec.files.create} color="#4caf50" />
          <FileList label="Modify" files={spec.files.modify} color="#1976d2" />
          <FileList label="Affected" files={spec.files.affected} color="#9e9e9e" />
        </>
      )}

      {/* Constraints */}
      {spec.constraints.length > 0 && (
        <>
          <SectionHeading>Constraints</SectionHeading>
          <ul className="pl-5 space-y-1 text-[13px] text-on-surface">
            {spec.constraints.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </>
      )}

      {/* References */}
      {spec.references.length > 0 && (
        <>
          <SectionHeading>References</SectionHeading>
          <ul className="pl-5 list-none space-y-0.5">
            {spec.references.map(r => (
              <li key={r} className="font-mono text-xs text-on-surface">{r}</li>
            ))}
          </ul>
        </>
      )}

      {/* Contracts */}
      {spec.contracts.length > 0 && (
        <>
          <SectionHeading>Contracts</SectionHeading>
          {spec.contracts.map(c => (
            <div key={c.name} className="text-[13px] text-on-surface mb-1">
              <strong>{c.name}</strong>: {c.description}
            </div>
          ))}
        </>
      )}

      {/* Test Commands */}
      {Object.keys(spec.testCommand).length > 0 && (
        <>
          <SectionHeading>Test Commands</SectionHeading>
          {Object.entries(spec.testCommand).map(([key, cmd]) => (
            <div key={key} className="font-mono text-xs mb-0.5">
              <span className="text-on-surface-variant">{key}:</span> <span className="text-on-surface">{cmd}</span>
            </div>
          ))}
        </>
      )}

      {/* Raw Spec (collapsible) */}
      {spec.raw && (
        <div className="mt-4">
          <h4
            onClick={() => setRawExpanded(!rawExpanded)}
            className="text-[13px] font-semibold text-on-surface-variant cursor-pointer select-none flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-[16px]">{rawExpanded ? 'expand_more' : 'chevron_right'}</span>
            Raw Spec
          </h4>
          {rawExpanded && (
            <pre className="bg-surface-container-high p-3 rounded-lg text-[11px] leading-normal overflow-auto max-h-[400px] mt-2 whitespace-pre-wrap break-words text-on-surface">
              {spec.raw}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
