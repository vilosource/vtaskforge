import yaml from 'js-yaml';

export interface ParsedSpec {
  approach: string;
  constraints: string[];
  references: string[];
  files: {
    create: string[];
    modify: string[];
    affected: string[];
  };
  contracts: Array<{
    name: string;
    description: string;
  }>;
  testCommand: Record<string, string>;
  raw: string;
}


function normalizeTestCommand(raw: unknown): Record<string, string> {
  if (!raw) return {};
  if (typeof raw === 'string') return { default: raw };
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, string>;
  return {};
}

export function parseSpec(rawYaml: string): ParsedSpec | null {
  if (!rawYaml) return null;
  try {
    const parsed = yaml.load(rawYaml) as Record<string, unknown>;
    if (!parsed || typeof parsed !== 'object') return null;

    const impl = (parsed.implementation ?? {}) as Record<string, unknown>;
    const files = (parsed.files ?? {}) as Record<string, unknown>;
    const contractsData = (parsed.contracts as Record<string, unknown>)?.establishes;
    const contracts = Array.isArray(contractsData)
      ? (contractsData as Array<Record<string, string>>)
      : [];

    return {
      approach: String(impl.approach ?? ''),
      constraints: Array.isArray(impl.constraints) ? impl.constraints.map(String) : [],
      references: Array.isArray(impl.references) ? impl.references.map(String) : [],
      files: {
        create: Array.isArray(files.create) ? files.create.map(String) : [],
        modify: Array.isArray(files.modify) ? files.modify.map(String) : [],
        affected: Array.isArray(files.affected) ? files.affected.map(String) : [],
      },
      contracts: contracts.map(c => ({ name: c.name ?? '', description: c.description ?? '' })),
      testCommand: normalizeTestCommand(parsed.test_command),
      raw: rawYaml,
    };
  } catch {
    return null;
  }
}
