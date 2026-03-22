import { describe, it, expect } from 'vitest';
import { parseSpec } from './parseSpec';

const FULL_SPEC = `id: "6.1"
name: "Task model — add spec fields"
agent_model: sonnet
isolation: sequential
judge: false

description: |
  Add five new fields to the Task model.

files:
  create:
    - src/tasks/migrations/0003_add_spec.py
  modify:
    - src/tasks/models.py
  affected:
    - src/tasks/serializers.py

implementation:
  approach: |
    Step 1: Add fields

    \`\`\`python
    spec = models.TextField(blank=True)
    \`\`\`

    Step 2: Migrate
  constraints:
    - All new fields must have defaults
    - Do not change existing fields
  references:
    - src/tasks/models.py
    - src/core/mixins.py

contracts:
  establishes:
    - name: "spec-field"
      description: "Task stores full YAML spec"

acceptance_criteria:
  - "Migration applies cleanly"

test_command:
  unit: "docker compose exec api pytest tests/tasks/"
`;

const MINIMAL_SPEC = `id: "1.1"
name: "Simple task"
description: "Just a description"
`;

describe('parseSpec', () => {
  it('returns null for empty string', () => {
    expect(parseSpec('')).toBeNull();
  });

  it('returns null for invalid YAML', () => {
    expect(parseSpec('{{not valid yaml')).toBeNull();
  });

  it('parses a full spec into structured object', () => {
    const result = parseSpec(FULL_SPEC);
    expect(result).not.toBeNull();
    expect(result!.approach).toContain('Step 1: Add fields');
    expect(result!.constraints).toEqual([
      'All new fields must have defaults',
      'Do not change existing fields',
    ]);
    expect(result!.references).toEqual([
      'src/tasks/models.py',
      'src/core/mixins.py',
    ]);
  });

  it('extracts files correctly', () => {
    const result = parseSpec(FULL_SPEC)!;
    expect(result.files.create).toEqual(['src/tasks/migrations/0003_add_spec.py']);
    expect(result.files.modify).toEqual(['src/tasks/models.py']);
    expect(result.files.affected).toEqual(['src/tasks/serializers.py']);
  });

  it('extracts contracts', () => {
    const result = parseSpec(FULL_SPEC)!;
    expect(result.contracts).toEqual([
      { name: 'spec-field', description: 'Task stores full YAML spec' },
    ]);
  });

  it('extracts test command', () => {
    const result = parseSpec(FULL_SPEC)!;
    expect(result.testCommand).toEqual({
      unit: 'docker compose exec api pytest tests/tasks/',
    });
  });

  it('preserves raw YAML', () => {
    const result = parseSpec(FULL_SPEC)!;
    expect(result.raw).toBe(FULL_SPEC);
  });

  it('handles minimal spec with missing optional fields', () => {
    const result = parseSpec(MINIMAL_SPEC);
    expect(result).not.toBeNull();
    expect(result!.approach).toBe('');
    expect(result!.constraints).toEqual([]);
    expect(result!.references).toEqual([]);
    expect(result!.files.create).toEqual([]);
    expect(result!.files.modify).toEqual([]);
    expect(result!.files.affected).toEqual([]);
    expect(result!.contracts).toEqual([]);
  });
});

const STRING_TEST_COMMAND_SPEC = `id: "2.1"
name: "Task with string test_command"
test_command: "cd /app && python -m pytest tests/ -q"
`;

describe('parseSpec string test_command', () => {
  it('normalizes string test_command to Record with default key', () => {
    const result = parseSpec(STRING_TEST_COMMAND_SPEC);
    expect(result).not.toBeNull();
    expect(result!.testCommand).toEqual({
      default: 'cd /app && python -m pytest tests/ -q',
    });
  });

  it('handles missing test_command gracefully', () => {
    const result = parseSpec(MINIMAL_SPEC);
    expect(result).not.toBeNull();
    expect(result!.testCommand).toEqual({});
  });
});
