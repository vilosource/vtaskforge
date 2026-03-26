import React, { createContext, useContext, useEffect, useState } from 'react';

interface ActiveProjectContextValue {
  projectId: string | null;
  setProjectId: React.Dispatch<React.SetStateAction<string | null>>;
}

const ActiveProjectContext = createContext<ActiveProjectContextValue>({
  projectId: null,
  setProjectId: () => {},
});

export function ActiveProjectProvider({ children }: { children: React.ReactNode }) {
  const [projectId, setProjectId] = useState<string | null>(null);

  return (
    <ActiveProjectContext.Provider value={{ projectId, setProjectId }}>
      {children}
    </ActiveProjectContext.Provider>
  );
}

export function useActiveProject(): string | null {
  return useContext(ActiveProjectContext).projectId;
}

export function useSetActiveProject(id: string | undefined): void {
  const { setProjectId } = useContext(ActiveProjectContext);

  useEffect(() => {
    setProjectId(id ?? null);
    return () => {
      setProjectId(null);
    };
  }, [id, setProjectId]);
}
