// Publish a complete build by updating the release pointer after all uploads succeed.
// Runs inside the Cloud Run job; credentials come from the job's service account
// via the metadata server, so no key file is used.
import { readdir, readFile } from 'node:fs/promises';
import { join, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const bucket = process.env.DASHBOARD_BUCKET;
const release = process.env.DASHBOARD_RELEASE;
if (!/^[a-f0-9]{32}$/.test(release || '')) throw new Error('Invalid DASHBOARD_RELEASE');
const prefix = `site/releases/${release}/`;
const root = fileURLToPath(new URL('../build/', import.meta.url));
if (!bucket) throw new Error('DASHBOARD_BUCKET is not set');

const types = {
	'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript',
	'.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
	'.ico': 'image/x-icon', '.wasm': 'application/wasm', '.parquet': 'application/octet-stream',
	'.webmanifest': 'application/manifest+json', '.txt': 'text/plain', '.woff2': 'font/woff2'
};

async function token() {
	const r = await fetch(
		'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token',
		{ headers: { 'Metadata-Flavor': 'Google' } }
	);
	if (!r.ok) throw new Error(`metadata token ${r.status}`);
	return (await r.json()).access_token;
}

async function* walk(dir) {
	for (const e of await readdir(dir, { withFileTypes: true })) {
		const p = join(dir, e.name);
		if (e.isDirectory()) yield* walk(p);
		else yield p;
	}
}

const auth = { Authorization: `Bearer ${await token()}` };
const files = [];
for await (const f of walk(root)) files.push(f);
if (!files.includes(join(root, 'index.html'))) throw new Error('Missing dashboard index.html');

async function put(name, body, contentType) {
	const url = `https://storage.googleapis.com/upload/storage/v1/b/${bucket}/o?uploadType=media&name=${encodeURIComponent(name)}`;
	for (let attempt = 1; attempt <= 3; attempt++) {
		const r = await fetch(url, {
			method: 'POST',
			headers: { ...auth, 'Content-Type': contentType },
			body
		});
		if (r.ok) return;
		if (attempt === 3) throw new Error(`upload ${name}: ${r.status} ${await r.text()}`);
	}
}

for (let i = 0; i < files.length; i += 16) {
	await Promise.all(files.slice(i, i + 16).map(async (file) => {
		const name = prefix + relative(root, file).replaceAll('\\', '/');
		await put(name, await readFile(file), types[extname(file)] || 'application/octet-stream');
	}));
}
await put('site/current-release.txt', release, 'text/plain');
console.log(JSON.stringify({ status: 'PUBLISHED', release, uploaded: files.length, at: new Date().toISOString() }));
