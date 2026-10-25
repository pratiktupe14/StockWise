import { spawn } from 'child_process';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');
const backendDir = path.join(rootDir, 'backend');

// 1. Check if backend is already alive on port 8000
function checkPort8000() {
  return new Promise((resolve) => {
    const req = http.get('http://127.0.0.1:8000/api/health', (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function main() {
  const isRunning = await checkPort8000();
  if (isRunning) {
    console.log('\x1b[36m[BACKEND]\x1b[0m FastAPI backend is already running on http://127.0.0.1:8000 (status: healthy)');
    // Keep alive so concurrently doesn't exit if -k is set
    setInterval(() => {}, 60000);
    return;
  }

  // Find python executable
  let pythonPath = 'python';
  const venvWin = path.join(backendDir, '.venv', 'Scripts', 'python.exe');
  const venvUnix = path.join(backendDir, '.venv', 'bin', 'python');

  if (fs.existsSync(venvWin)) {
    pythonPath = venvWin;
  } else if (fs.existsSync(venvUnix)) {
    pythonPath = venvUnix;
  }

  console.log(`\x1b[36m[BACKEND]\x1b[0m Starting FastAPI uvicorn using ${pythonPath}...`);

  const proc = spawn(
    pythonPath,
    ['-m', 'uvicorn', 'app.main:app', '--app-dir', backendDir, '--host', '127.0.0.1', '--port', '8000', '--reload'],
    { cwd: backendDir, stdio: 'inherit' }
  );

  proc.on('error', (err) => {
    console.error(`\x1b[31m[BACKEND ERROR]\x1b[0m Failed to start backend:`, err.message);
  });

  proc.on('close', (code) => {
    console.log(`\x1b[36m[BACKEND]\x1b[0m Exited with code ${code}`);
  });
}

main();
