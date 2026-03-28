import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useTaskDetail, useDownstreamLinks } from '../api/tasks';
import { useWorkplan } from '../api/tasks';
import { useMilestone } from '../api/milestones';
import { useProject } from '../api/projects';
import { parseSpec } from '../utils/parseSpec';
import { SpecSection } from '../components/SpecSection';
import { DependencyChain } from '../components/DependencyChain';
import { EventTimeline } from '../components/EventTimeline';
import { ActionButtons } from '../components/ActionButtons';
import { AddNoteForm } from '../components/AddNoteForm';
import { Breadcrumb } from '../components/Breadcrumb';
import { useSetActiveProject } from '../contexts/ActiveProjectContext';

function isAgent(actorId: string) {
  return actorId.includes('agent') || actorId.includes('supervisor') || actorId.includes('executor');
}

export function TaskPage() {
  const { id } = useParams<{ id: string }>();
  const { data: task, isLoading, isError } = useTaskDetail(id ?? null);
  const { data: downstream } = useDownstreamLinks(id ?? null);
  const { data: workplan } = useWorkplan(task?.workplan ?? '');
  const { data: milestone } = useMilestone(task?.milestone ?? undefined);
  const { data: project } = useProject(task?.project);
  useSetActiveProject(task?.project);
  const [eventsExpanded, setEventsExpanded] = useState(false);

  if (isLoading) {
    return <div style={{ padding: 40, textAlign: 'center' }}>Loading task...</div>;
  }

  if (isError || !task) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#c62828' }}>Failed to load task.</div>;
  }

  const parsedSpec = parseSpec(task.spec);
  const upstreamLinks = (task.links ?? []).filter(l => l.link_type === 'depends_on');
  const downstreamLinks = downstream?.results ?? [];

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>
      {/* Breadcrumb */}
      <Breadcrumb segments={[
        { label: project?.name ?? 'Project', to: `/projects/${task.project}` },
        ...(workplan ? [{ label: workplan.name, to: `/projects/${task.project}/workplans/${task.workplan}` }] : []),
        ...(milestone ? [{ label: milestone.name, to: `/projects/${task.project}/workplans/${task.workplan}/milestones/${task.milestone}` }] : []),
        { label: task.title }
      ]} />

      {/* Two-column layout */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '2fr 1fr',
        gap: 24,
        alignItems: 'start',
      }}>
        {/* LEFT COLUMN */}
        <div>
          {/* Title + status */}
          <div style={{ marginBottom: 16 }}>
            <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0, lineHeight: 1.3 }}>{task.title}</h1>
            <span style={{
              display: 'inline-block',
              marginTop: 8,
              padding: '2px 10px',
              borderRadius: 4,
              fontSize: 12,
              fontWeight: 600,
              background: '#e3f2fd',
              color: '#1565c0',
            }}>
              {task.status}
            </span>
          </div>

          {/* Description */}
          {task.description && (
            <section style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: '#333', marginBottom: 8 }}>Description</h3>
              <div style={{ fontSize: 13, lineHeight: 1.6, color: '#444' }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.description}</ReactMarkdown>
              </div>
            </section>
          )}

          {/* Acceptance criteria */}
          {task.acceptance_criteria.length > 0 && (
            <section style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: '#333', marginBottom: 8 }}>Acceptance Criteria</h3>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
                {task.acceptance_criteria.map((c, i) => (
                  <li key={i} style={{ marginBottom: 4 }}>{c}</li>
                ))}
              </ul>
            </section>
          )}

          {/* Parsed spec sections */}
          {parsedSpec && (
            <section style={{ marginBottom: 20 }}>
              <SpecSection spec={parsedSpec} />
            </section>
          )}
        </div>

        {/* RIGHT COLUMN */}
        <div style={{ position: 'sticky', top: 20, alignSelf: 'start' }}>
          {/* Metadata card */}
          <div style={{
            background: '#fafafa',
            border: '1px solid #e0e0e0',
            borderRadius: 8,
            padding: 16,
            marginBottom: 16,
          }}>
            <h4 style={{ margin: '0 0 12px 0', fontSize: 13, color: '#666' }}>Metadata</h4>
            <dl style={{ margin: 0, fontSize: 13 }}>
              <dt style={{ color: '#888', marginTop: 6 }}>Status</dt>
              <dd style={{ margin: '2px 0 0 0', fontWeight: 600 }}>{task.status}</dd>
              {task.agent_model && (
                <>
                  <dt style={{ color: '#888', marginTop: 6 }}>Agent Model</dt>
                  <dd style={{ margin: '2px 0 0 0' }}>{task.agent_model}</dd>
                </>
              )}
              {task.isolation && (
                <>
                  <dt style={{ color: '#888', marginTop: 6 }}>Isolation</dt>
                  <dd style={{ margin: '2px 0 0 0' }}>{task.isolation}</dd>
                </>
              )}
              <dt style={{ color: '#888', marginTop: 6 }}>Judge Required</dt>
              <dd style={{ margin: '2px 0 0 0' }}>{task.judge ? 'Yes' : 'No'}</dd>
            </dl>
          </div>

          {/* Assignment card */}
          <div style={{
            background: '#fafafa',
            border: '1px solid #e0e0e0',
            borderRadius: 8,
            padding: 16,
            marginBottom: 16,
          }}>
            <h4 style={{ margin: '0 0 12px 0', fontSize: 13, color: '#666' }}>Assignment</h4>
            <dl style={{ margin: 0, fontSize: 13 }}>
              <dt style={{ color: '#888' }}>Claimed by</dt>
              <dd style={{ margin: '2px 0 0 0' }}>{task.claimed_by ?? '\u2014'}</dd>
              <dt style={{ color: '#888', marginTop: 6 }}>Assigned to</dt>
              <dd style={{ margin: '2px 0 0 0' }}>{task.assigned_to ?? '\u2014'}</dd>
              {task.requires.length > 0 && (
                <>
                  <dt style={{ color: '#888', marginTop: 6 }}>Requires</dt>
                  <dd style={{ margin: '2px 0 0 0' }}>{task.requires.join(', ')}</dd>
                </>
              )}
            </dl>
          </div>

          {/* Context card */}
          <div style={{
            background: '#fafafa',
            border: '1px solid #e0e0e0',
            borderRadius: 8,
            padding: 16,
            marginBottom: 16,
          }}>
            <h4 style={{ margin: '0 0 12px 0', fontSize: 13, color: '#666' }}>Context</h4>
            <dl style={{ margin: 0, fontSize: 13 }}>
              {milestone && (
                <>
                  <dt style={{ color: '#888' }}>Milestone</dt>
                  <dd style={{ margin: '2px 0 0 0' }}>
                    <Link to={`/projects/${task.project}/workplans/${task.workplan}/milestones/${task.milestone}`}
                      style={{ color: '#1976d2', textDecoration: 'none' }}>
                      {milestone.name}
                    </Link>
                  </dd>
                </>
              )}
              {workplan && (
                <>
                  <dt style={{ color: '#888', marginTop: 6 }}>Workplan</dt>
                  <dd style={{ margin: '2px 0 0 0' }}>
                    <Link to={`/projects/${task.project}/workplans/${task.workplan}`}
                      style={{ color: '#1976d2', textDecoration: 'none' }}>
                      {workplan.name}
                    </Link>
                  </dd>
                </>
              )}
              <dt style={{ color: '#888', marginTop: 6 }}>Created</dt>
              <dd style={{ margin: '2px 0 0 0' }}>{new Date(task.created_at).toLocaleDateString()}</dd>
              <dt style={{ color: '#888', marginTop: 6 }}>Updated</dt>
              <dd style={{ margin: '2px 0 0 0' }}>{new Date(task.updated_at).toLocaleDateString()}</dd>
            </dl>
          </div>

          {/* Execution Traces */}
          {task.traces && (
            <div style={{
              background: '#fafafa',
              border: '1px solid #e0e0e0',
              borderRadius: 8,
              padding: 16,
              marginBottom: 16,
            }}>
              <h4 style={{ margin: '0 0 12px 0', fontSize: 13, color: '#666' }}>Execution Traces</h4>
              {task.traces.length === 0 ? (
                <p style={{ color: '#999', fontSize: 13, margin: 0 }}>No traces recorded</p>
              ) : (
                <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
                  {task.traces.map((trace, i) => (
                    <li key={trace.context_id} style={{
                      padding: '6px 0',
                      borderBottom: i < task.traces!.length - 1 ? '1px solid #f0f0f0' : 'none',
                      fontSize: 13,
                    }}>
                      <a
                        href={trace.web_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: '#1976d2', textDecoration: 'none' }}
                      >
                        {trace.title || `Attempt ${i + 1}`}
                      </a>
                      <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
                        {trace.is_live && (
                          <span style={{
                            display: 'inline-block',
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            background: '#4caf50',
                            marginRight: 4,
                            verticalAlign: 'middle',
                          }} />
                        )}
                        {trace.head_depth} turns
                        {trace.created_at_unix_ms > 0 && (
                          <> &middot; {new Date(trace.created_at_unix_ms).toLocaleDateString()}</>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Actions */}
          <div style={{
            background: '#fafafa',
            border: '1px solid #e0e0e0',
            borderRadius: 8,
            padding: 16,
          }}>
            <h4 style={{ margin: '0 0 12px 0', fontSize: 13, color: '#666' }}>Actions</h4>
            <ActionButtons taskId={task.id} status={task.status} />
          </div>
        </div>
      </div>

      {/* FULL WIDTH sections */}
      <div style={{ marginTop: 24 }}>
        {/* Dependency chain */}
        {(upstreamLinks.length > 0 || downstreamLinks.length > 0) && (
          <section style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#333', marginBottom: 8 }}>Dependencies</h3>
            <DependencyChain
              taskId={task.id}
              taskTitle={task.title}
              taskStatus={task.status}
              upstreamLinks={upstreamLinks}
              downstreamLinks={downstreamLinks}
            />
          </section>
        )}

        {/* Event timeline (collapsible) */}
        <section style={{ marginBottom: 20 }}>
          <h3
            onClick={() => setEventsExpanded(!eventsExpanded)}
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: '#333',
              cursor: 'pointer',
              userSelect: 'none',
              marginBottom: 8,
            }}
          >
            {eventsExpanded ? '\u25BE' : '\u25B8'} Event Timeline
          </h3>
          {eventsExpanded && <EventTimeline events={task.events ?? []} />}
        </section>

        {/* Notes */}
        <section>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: '#333', marginBottom: 8 }}>Notes</h3>
          {task.notes && task.notes.length > 0 ? (
            <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
              {task.notes.map((note, i) => {
                const noteObj = note as unknown as { id?: string; text?: string; actor_id?: string; created_at?: string };
                return (
                  <li key={noteObj.id ?? i} style={{
                    padding: '8px 0',
                    borderBottom: '1px solid #f0f0f0',
                    fontSize: 13,
                  }}>
                    <span style={{ marginRight: 6 }}>
                      {noteObj.actor_id && isAgent(noteObj.actor_id) ? '\u{1F916}' : '\u{1F464}'}
                    </span>
                    {noteObj.actor_id && (
                      <span style={{ fontWeight: 600, marginRight: 6 }}>{noteObj.actor_id}</span>
                    )}
                    <span>{noteObj.text ?? String(note)}</span>
                    {noteObj.created_at && (
                      <span style={{ color: '#999', fontSize: 11, marginLeft: 8 }}>
                        {new Date(noteObj.created_at).toLocaleString()}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p style={{ color: '#999', fontSize: 13 }}>No notes yet.</p>
          )}
          <div style={{ marginTop: 12 }}>
            <AddNoteForm taskId={task.id} />
          </div>
        </section>
      </div>
    </div>
  );
}
