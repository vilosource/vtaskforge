/**
 * API client for seeding and cleaning up verification data.
 *
 * Uses the REST API with token auth to create/delete test entities.
 * All verification entities use the "_verify" prefix for identification.
 */

const BASE_URL = process.env.VTF_BASE_URL || 'http://localhost:8001';
const API_TOKEN = process.env.VTF_API_TOKEN || '';

interface SeedResult {
  projectId: string;
  workplanId: string;
  milestoneId: string;
  taskIds: Record<string, string>;
  agentId: string;
  viewerUserId?: number;
}

async function api(
  method: string,
  path: string,
  body?: Record<string, unknown>,
): Promise<{ status: number; data: Record<string, unknown> }> {
  const res = await fetch(`${BASE_URL}/v1/${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Token ${API_TOKEN}`,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data = {};
  try {
    data = JSON.parse(text);
  } catch {
    // non-JSON response
  }
  return { status: res.status, data: data as Record<string, unknown> };
}

export async function seedVerificationData(): Promise<SeedResult> {
  // 1. Create project
  const project = await api('POST', 'projects/', {
    name: '_verify Verification Project',
    description: 'Automated post-deploy verification. Safe to delete.',
  });
  if (project.status !== 201) {
    throw new Error(`Failed to create project: ${project.status} ${JSON.stringify(project.data)}`);
  }
  const projectId = project.data.id as string;

  // 2. Create workplan under project
  const workplan = await api('POST', 'workplans/', {
    project: projectId,
    name: '_verify Workplan',
    description: 'Verification workplan',
  });
  if (workplan.status !== 201) {
    throw new Error(`Failed to create workplan: ${workplan.status} ${JSON.stringify(workplan.data)}`);
  }
  const workplanId = workplan.data.id as string;

  // 3. Create milestone under workplan
  const milestone = await api('POST', 'milestones/', {
    workplan: workplanId,
    name: '_verify Milestone',
    status: 'active',
    order: 1,
  });
  if (milestone.status !== 201) {
    throw new Error(`Failed to create milestone: ${milestone.status} ${JSON.stringify(milestone.data)}`);
  }
  const milestoneId = milestone.data.id as string;

  // 4. Register a verification agent (for claiming tasks)
  const agent = await api('POST', 'agents/', {
    name: '_verify-agent',
    tags: ['verify'],
  });
  if (agent.status !== 201) {
    throw new Error(`Failed to create agent: ${agent.status} ${JSON.stringify(agent.data)}`);
  }
  const agentId = agent.data.id as string;

  // 5. Create tasks in various states
  const taskDefs: { key: string; title: string; targetStatus: string }[] = [
    { key: 'draft', title: '_verify Draft Task', targetStatus: 'draft' },
    { key: 'todo', title: '_verify Ready Task', targetStatus: 'todo' },
    { key: 'doing', title: '_verify In-Progress Task', targetStatus: 'doing' },
    { key: 'done', title: '_verify Done Task', targetStatus: 'done' },
  ];

  const taskIds: Record<string, string> = {};

  for (const def of taskDefs) {
    // Create task (starts as draft)
    const task = await api('POST', 'tasks/', {
      title: def.title,
      description: `Verification task for ${def.key} state`,
      project: projectId,
      workplan: workplanId,
      milestone: milestoneId,
    });
    if (task.status !== 201) {
      throw new Error(`Failed to create task ${def.key}: ${task.status} ${JSON.stringify(task.data)}`);
    }
    const taskId = task.data.id as string;
    taskIds[def.key] = taskId;

    // Transition to target status
    if (def.targetStatus === 'draft') continue;

    // draft -> todo (submit)
    const submitRes = await api('POST', `tasks/${taskId}/submit/`, {});
    if (submitRes.status !== 200) {
      console.warn(`  WARN: submit ${def.key} returned ${submitRes.status}: ${JSON.stringify(submitRes.data)}`);
    }

    if (def.targetStatus === 'todo') continue;

    // todo -> doing (claim)
    const claimRes = await api('POST', `tasks/${taskId}/claim/`, {
      agent_id: agentId,
    });
    if (claimRes.status !== 200) {
      console.warn(`  WARN: claim ${def.key} returned ${claimRes.status}: ${JSON.stringify(claimRes.data)}`);
    }

    if (def.targetStatus === 'doing') continue;

    // doing -> done (complete)
    const completeRes = await api('POST', `tasks/${taskId}/complete/`, {});
    if (completeRes.status !== 200) {
      console.warn(`  WARN: complete ${def.key} returned ${completeRes.status}: ${JSON.stringify(completeRes.data)}`);
    }
  }

  // 6. Create non-staff viewer user via service-accounts endpoint
  //    We'll use this for permission tests
  let viewerUserId: number | undefined;
  const viewer = await api('POST', 'service-accounts/', {
    name: '_verify-viewer',
  });
  if (viewer.status === 201) {
    viewerUserId = (viewer.data as { user_id?: number }).user_id;
  }

  const result: SeedResult = {
    projectId,
    workplanId,
    milestoneId,
    taskIds,
    agentId,
    viewerUserId,
  };

  return result;
}

export async function cleanupVerificationData(seed: SeedResult): Promise<void> {
  // Delete in reverse dependency order, tolerate 404s
  for (const taskId of Object.values(seed.taskIds)) {
    await api('DELETE', `tasks/${taskId}/`).catch(() => {});
  }
  await api('DELETE', `milestones/${seed.milestoneId}/`).catch(() => {});
  await api('DELETE', `workplans/${seed.workplanId}/`).catch(() => {});
  await api('DELETE', `projects/${seed.projectId}/`).catch(() => {});
  await api('DELETE', `agents/${seed.agentId}/`).catch(() => {});
  if (seed.viewerUserId) {
    await api('DELETE', `users/${seed.viewerUserId}/`).catch(() => {});
  }
}
