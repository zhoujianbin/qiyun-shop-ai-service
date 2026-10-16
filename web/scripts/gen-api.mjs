// 从 contracts/openapi.yaml 生成 src/api/generated/schema.d.ts（只读产物，禁止手改）
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const input = path.join(root, 'contracts', 'openapi.yaml');
const outDir = path.join(root, 'src', 'api', 'generated');
if (!existsSync(input)) {
  console.error('缺少契约文件：' + input);
  process.exit(1);
}
mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, 'schema.d.ts');
execFileSync('npx', ['openapi-typescript', input, '-o', out], { stdio: 'inherit', cwd: root });
console.log('已生成 ' + path.relative(root, out));
