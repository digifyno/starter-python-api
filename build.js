const fs = require('fs');
const path = require('path');

const distDir = path.join(__dirname, 'dist');
if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}

// dist/index.html is committed to git; nothing to do if it already exists
const indexPath = path.join(distDir, 'index.html');
if (!fs.existsSync(indexPath)) {
  fs.writeFileSync(indexPath, '<html><body><h1>FastAPI Backend</h1><p>See /health</p></body></html>');
}

console.log('Build complete — dist/index.html ready for nginx');
