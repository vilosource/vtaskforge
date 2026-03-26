import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { ActiveProjectProvider, useActiveProject, useSetActiveProject } from './ActiveProjectContext';

function DisplayProject() {
  const projectId = useActiveProject();
  return <div data-testid="project-id">{projectId ?? 'null'}</div>;
}

function SetProject({ id }: { id: string | undefined }) {
  useSetActiveProject(id);
  return null;
}

describe('ActiveProjectContext', () => {
  it('provides null as default projectId', () => {
    render(
      <ActiveProjectProvider>
        <DisplayProject />
      </ActiveProjectProvider>
    );
    expect(screen.getByTestId('project-id').textContent).toBe('null');
  });

  it('sets projectId when useSetActiveProject is called', async () => {
    render(
      <ActiveProjectProvider>
        <SetProject id="proj-123" />
        <DisplayProject />
      </ActiveProjectProvider>
    );
    // useEffect runs after render, so we need to wait
    await act(async () => {});
    expect(screen.getByTestId('project-id').textContent).toBe('proj-123');
  });

  it('cleans up by setting null on unmount', async () => {
    const { rerender } = render(
      <ActiveProjectProvider>
        <SetProject id="proj-456" />
        <DisplayProject />
      </ActiveProjectProvider>
    );
    await act(async () => {});
    expect(screen.getByTestId('project-id').textContent).toBe('proj-456');

    // Unmount the SetProject component
    rerender(
      <ActiveProjectProvider>
        <DisplayProject />
      </ActiveProjectProvider>
    );
    await act(async () => {});
    expect(screen.getByTestId('project-id').textContent).toBe('null');
  });
});
