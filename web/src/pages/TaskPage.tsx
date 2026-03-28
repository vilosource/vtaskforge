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

const statusColor: Record<string, string> = {
  done: 'bg-tertiary/10 text-tertiary',
  doing: 'bg-primary/10 text-primary',
  todo: 'bg-primary-fixed text-on-primary-fixed',
  draft: 'bg-surface-container-high text-on-surface-variant',
  blocked: 'bg-error-container text-on-error-container',
  needs_attention: 'bg-error-container/60 text-error',
  cancelled: 'bg-surface-container-high text-on-surface-variant',
};

function statusBadge(status: string) {
  return statusColor[status] ?? statusColor.draft;
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
    return <div className="px-8 pb-12 pt-6 text-center text-on-surface-variant">Loading task...</div>;
  }

  if (isError || !task) {
    return <div className="px-8 pb-12 pt-6 text-center text-error">Failed to load task.</div>;
  }

  const parsedSpec = parseSpec(task.spec);
  const upstreamLinks = (task.links ?? []).filter(l => l.link_type === 'depends_on');
  const downstreamLinks = downstream?.results ?? [];

  return (
    <div className="mx-auto max-w-[1200px] px-8 pb-12 pt-6">
      {/* Breadcrumb */}
      <Breadcrumb segments={[
        { label: project?.name ?? 'Project', to: `/projects/${task.project}` },
        ...(workplan ? [{ label: workplan.name, to: `/projects/${task.project}/workplans/${task.workplan}` }] : []),
        ...(milestone ? [{ label: milestone.name, to: `/projects/${task.project}/workplans/${task.workplan}/milestones/${task.milestone}` }] : []),
        { label: task.title }
      ]} />

      {/* Title row */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <span className={`inline-block rounded-full px-3 py-0.5 text-xs font-semibold ${statusBadge(task.status)}`}>
            {task.status}
          </span>
          <span className="text-xs text-on-surface-variant font-label">#{task.id.slice(0, 8)}</span>
          {task.claimed_by && (
            <span className="ml-auto flex items-center gap-1.5 text-xs text-on-surface-variant">
              <span className="material-symbols-outlined text-[16px]">smart_toy</span>
              {task.claimed_by}
            </span>
          )}
        </div>
        <h1 className="text-3xl font-headline font-extrabold tracking-tight text-on-surface">{task.title}</h1>
      </div>

      {/* Action buttons row */}
      <div className="mb-8">
        <ActionButtons taskId={task.id} status={task.status} />
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-3 gap-8 items-start">
        {/* LEFT COLUMN (main content) */}
        <div className="col-span-2 space-y-6">
          {/* Description */}
          {task.description && (
            <section className="bg-surface-container-lowest p-8 rounded-xl shadow">
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-4">Description</h2>
              <div className="text-sm leading-relaxed text-on-surface whitespace-pre-wrap prose-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.description}</ReactMarkdown>
              </div>
            </section>
          )}

          {/* Acceptance criteria */}
          {task.acceptance_criteria.length > 0 && (
            <section className="bg-surface-container-lowest p-8 rounded-xl shadow">
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-4">Acceptance Criteria</h2>
              <ul className="space-y-2">
                {task.acceptance_criteria.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-on-surface">
                    <span className="material-symbols-outlined text-[18px] mt-0.5 text-outline-variant">radio_button_unchecked</span>
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Parsed spec sections */}
          {parsedSpec && (
            <section className="bg-surface-container-lowest p-8 rounded-xl shadow">
              <SpecSection spec={parsedSpec} />
            </section>
          )}

          {/* Dependency chain */}
          {(upstreamLinks.length > 0 || downstreamLinks.length > 0) && (
            <section className="bg-surface-container-lowest p-8 rounded-xl shadow">
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-4">Dependencies</h2>
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
          <section className="bg-surface-container-lowest p-8 rounded-xl shadow">
            <h2
              onClick={() => setEventsExpanded(!eventsExpanded)}
              className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-4 cursor-pointer select-none flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-[16px]">{eventsExpanded ? 'expand_more' : 'chevron_right'}</span>
              Event Timeline
            </h2>
            {eventsExpanded && <EventTimeline events={task.events ?? []} />}
          </section>

          {/* Notes */}
          <section className="bg-surface-container-lowest p-8 rounded-xl shadow">
            <h2 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-4">Notes</h2>
            {task.notes && task.notes.length > 0 ? (
              <ul className="space-y-3">
                {task.notes.map((note, i) => {
                  const noteObj = note as unknown as { id?: string; text?: string; actor_id?: string; created_at?: string };
                  const initials = noteObj.actor_id ? noteObj.actor_id.slice(0, 2).toUpperCase() : '??';
                  return (
                    <li key={noteObj.id ?? i} className="flex items-start gap-3">
                      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold ${
                        noteObj.actor_id && isAgent(noteObj.actor_id)
                          ? 'bg-tertiary-container text-on-tertiary-container'
                          : 'bg-secondary-container text-on-secondary-container'
                      }`}>
                        {initials}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline gap-2">
                          {noteObj.actor_id && (
                            <span className="text-xs font-semibold text-on-surface">{noteObj.actor_id}</span>
                          )}
                          {noteObj.created_at && (
                            <span className="text-[11px] text-on-surface-variant">
                              {new Date(noteObj.created_at).toLocaleString()}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-on-surface mt-0.5">{noteObj.text ?? String(note)}</p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-on-surface-variant">No notes yet.</p>
            )}
            <div className="mt-4 pt-4 border-t border-outline-variant/20">
              <AddNoteForm taskId={task.id} />
            </div>
          </section>
        </div>

        {/* RIGHT COLUMN (sidebar) */}
        <div className="col-span-1 sticky top-5 space-y-4">
          {/* Metadata card */}
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow">
            <h2 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Metadata</h2>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-on-surface-variant text-xs">Status</dt>
                <dd className="font-semibold text-on-surface">{task.status}</dd>
              </div>
              {task.agent_model && (
                <div>
                  <dt className="text-on-surface-variant text-xs">Agent Model</dt>
                  <dd className="text-on-surface">{task.agent_model}</dd>
                </div>
              )}
              {task.isolation && (
                <div>
                  <dt className="text-on-surface-variant text-xs">Isolation</dt>
                  <dd className="text-on-surface">{task.isolation}</dd>
                </div>
              )}
              <div>
                <dt className="text-on-surface-variant text-xs">Judge Required</dt>
                <dd className="text-on-surface">{task.judge ? 'Yes' : 'No'}</dd>
              </div>
            </dl>
          </div>

          {/* Assignment card */}
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow">
            <h2 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Assignment</h2>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-on-surface-variant text-xs">Claimed by</dt>
                <dd className="text-on-surface">{task.claimed_by ?? '\u2014'}</dd>
              </div>
              <div>
                <dt className="text-on-surface-variant text-xs">Assigned to</dt>
                <dd className="text-on-surface">{task.assigned_to ?? '\u2014'}</dd>
              </div>
              {task.requires.length > 0 && (
                <div>
                  <dt className="text-on-surface-variant text-xs">Requires</dt>
                  <dd className="text-on-surface">{task.requires.join(', ')}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Context card */}
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow">
            <h2 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Context</h2>
            <dl className="space-y-2 text-sm">
              {milestone && (
                <div>
                  <dt className="text-on-surface-variant text-xs">Milestone</dt>
                  <dd>
                    <Link to={`/projects/${task.project}/workplans/${task.workplan}/milestones/${task.milestone}`}
                      className="text-primary hover:underline no-underline">
                      {milestone.name}
                    </Link>
                  </dd>
                </div>
              )}
              {workplan && (
                <div>
                  <dt className="text-on-surface-variant text-xs">Workplan</dt>
                  <dd>
                    <Link to={`/projects/${task.project}/workplans/${task.workplan}`}
                      className="text-primary hover:underline no-underline">
                      {workplan.name}
                    </Link>
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-on-surface-variant text-xs">Created</dt>
                <dd className="text-on-surface">{new Date(task.created_at).toLocaleDateString()}</dd>
              </div>
              <div>
                <dt className="text-on-surface-variant text-xs">Updated</dt>
                <dd className="text-on-surface">{new Date(task.updated_at).toLocaleDateString()}</dd>
              </div>
            </dl>
          </div>

          {/* Execution Traces */}
          {task.traces && (
            <div className="bg-surface-container-lowest p-6 rounded-xl shadow">
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Execution Traces</h2>
              {task.traces.length === 0 ? (
                <p className="text-sm text-on-surface-variant">No traces recorded</p>
              ) : (
                <ul className="space-y-0 divide-y divide-outline-variant/20">
                  {task.traces.map((trace, i) => (
                    <li key={trace.context_id} className="py-2 first:pt-0 last:pb-0">
                      <a
                        href={trace.web_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-primary hover:underline"
                      >
                        {trace.title || `Attempt ${i + 1}`}
                      </a>
                      <div className="text-[11px] text-on-surface-variant mt-0.5 flex items-center gap-1">
                        {trace.is_live && (
                          <span className="inline-block w-1.5 h-1.5 rounded-full bg-tertiary" />
                        )}
                        <span>{trace.head_depth} turns</span>
                        {trace.created_at_unix_ms > 0 && (
                          <span> &middot; {new Date(trace.created_at_unix_ms).toLocaleDateString()}</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Links card */}
          {(upstreamLinks.length > 0 || downstreamLinks.length > 0) && (
            <div className="bg-surface-container-lowest p-6 rounded-xl shadow">
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Dependencies</h2>
              {upstreamLinks.length > 0 && (
                <div className="mb-3">
                  <div className="text-[10px] font-semibold uppercase text-on-surface-variant mb-1 flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">arrow_back</span> Blocks
                  </div>
                  <ul className="space-y-1">
                    {upstreamLinks.map(l => {
                      const isDone = false; // status not available from link
                      return (
                        <li key={l.id} className="text-sm">
                          <Link to={`/tasks/${l.target_id}`} className={`text-primary hover:underline ${isDone ? 'line-through opacity-60' : ''}`}>
                            {l.target_title ?? l.target_id}
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
              {downstreamLinks.length > 0 && (
                <div>
                  <div className="text-[10px] font-semibold uppercase text-on-surface-variant mb-1 flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">arrow_forward</span> Blocked by this
                  </div>
                  <ul className="space-y-1">
                    {downstreamLinks.map(l => (
                      <li key={l.id} className="text-sm">
                        <Link to={`/tasks/${l.source_id}`} className="text-primary hover:underline">
                          {l.source_title ?? l.source_id}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
