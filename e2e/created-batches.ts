import { appendFileSync } from 'node:fs';

// Optional audit trail for cleaning up only batches created by an E2E run.
export function recordCreatedBatch(id: number) {
  const filename = process.env.TCC_E2E_CREATED_BATCH_LOG;
  if (filename) appendFileSync(filename, `${JSON.stringify({ id })}\n`);
}
