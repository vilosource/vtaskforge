/**
 * Global setup for post-deploy verification.
 *
 * 1. Seeds verification data via REST API
 * 2. Logs in as admin and saves storageState for test reuse
 * 3. Writes seed result to a JSON file for tests to reference
 */
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { seedVerificationData } from './helpers/api';
import { createAuthState } from './helpers/auth';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SEED_FILE = path.join(__dirname, 'seed-data.json');
const AUTH_STATE_FILE = path.join(__dirname, 'auth-state.json');

async function globalSetup() {
  console.log('\n=== Post-Deploy Verification Setup ===');
  const baseUrl = process.env.VTF_BASE_URL || 'http://localhost:8001';
  console.log(`  Target: ${baseUrl}`);

  // Step 1: Seed verification data
  console.log('  Seeding verification data...');
  const seed = await seedVerificationData();
  fs.writeFileSync(SEED_FILE, JSON.stringify(seed, null, 2));
  console.log(`  Project: ${seed.projectId}`);
  console.log(`  Workplan: ${seed.workplanId}`);
  console.log(`  Milestone: ${seed.milestoneId}`);
  console.log(`  Tasks: ${Object.keys(seed.taskIds).join(', ')}`);

  // Step 2: Create auth state
  console.log('  Authenticating...');
  await createAuthState(AUTH_STATE_FILE);
  console.log('  Auth state saved.');

  console.log('=== Setup Complete ===\n');
}

export default globalSetup;
