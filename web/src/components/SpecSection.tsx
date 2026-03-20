import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ParsedSpec } from '../utils/parseSpec';

interface SpecSectionProps {
  spec: ParsedSpec;
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h4 style={{ fontSize: 14, fontWeight: 600, color: '#444', margin: '16px 0 8px 0' }}>
      {children}
    </h4>
  );
}

function FileList({ label, files, color }: { label: string; files: string[]; color: string }) {
  if (files.length === 0) return null;
  return (
    <div style={{ marginBottom: 8 }}>
      <span style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: color,
        marginRight: 6,
      }} />
      <span style={{ fontSize: 12, color: '#666', fontWeight: 600 }}>{label}</span>
      <ul style={{ margin: '4px 0 0 20px', padding: 0, listStyle: 'none' }}>
        {files.map(f => (
          <li key={f} style={{ fontFamily: 'monospace', fontSize: 12, color: '#333', padding: '1px 0' }}>
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
          <div className="spec-markdown" style={{ fontSize: 13, lineHeight: 1.6 }}>
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
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
            {spec.constraints.map((c, i) => (
              <li key={i} style={{ marginBottom: 4 }}>{c}</li>
            ))}
          </ul>
        </>
      )}

      {/* References */}
      {spec.references.length > 0 && (
        <>
          <SectionHeading>References</SectionHeading>
          <ul style={{ margin: 0, paddingLeft: 20, listStyle: 'none', fontSize: 12 }}>
            {spec.references.map(r => (
              <li key={r} style={{ fontFamily: 'monospace', padding: '1px 0' }}>{r}</li>
            ))}
          </ul>
        </>
      )}

      {/* Contracts */}
      {spec.contracts.length > 0 && (
        <>
          <SectionHeading>Contracts</SectionHeading>
          {spec.contracts.map(c => (
            <div key={c.name} style={{ fontSize: 13, marginBottom: 4 }}>
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
            <div key={key} style={{ fontFamily: 'monospace', fontSize: 12, marginBottom: 2 }}>
              <span style={{ color: '#666' }}>{key}:</span> {cmd}
            </div>
          ))}
        </>
      )}

      {/* Raw Spec (collapsible) */}
      {spec.raw && (
        <div style={{ marginTop: 16 }}>
          <h4
            onClick={() => setRawExpanded(!rawExpanded)}
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: '#888',
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            {rawExpanded ? '\u25BE' : '\u25B8'} Raw Spec
          </h4>
          {rawExpanded && (
            <pre style={{
              background: '#f5f5f5',
              padding: 12,
              borderRadius: 6,
              fontSize: 11,
              lineHeight: 1.5,
              overflow: 'auto',
              maxHeight: 400,
              marginTop: 8,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {spec.raw}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
