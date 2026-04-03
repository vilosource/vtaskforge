/**
 * Global teardown for post-deploy verification.
 *
 * Cleans up all verification data seeded during setup.
 * Tolerates 404s (idempotent cleanup).
 */
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { cleanupVerificationData } from './helpers/api';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SEED_FILE = path.join(__dirname, 'seed-data.json');
const AUTH_STATE_FILE = path.join(__dirname, 'auth-state.json');

async function globalTeardown() {
  console.log('\n=== Post-Deploy Verification Teardown ===');

  if (fs.existsSync(SEED_FILE)) {
    const seed = JSON.parse(fs.readFileSync(SEED_FILE, 'utf-8'));
    console.log('  Cleaning up verification data...');
    await cleanupVerificationData(seed);
    fs.unlinkSync(SEED_FILE);
    console.log('  Cleanup complete.');
  } else {
    console.log('  No seed data found, skipping cleanup.');
  }

  // Remove auth state file
  if (fs.existsSync(AUTH_STATE_FILE)) {
    fs.unlinkSync(AUTH_STATE_FILE);
  }

  console.log('=== Teardown Complete ===\n');
}

export default globalTeardown;
