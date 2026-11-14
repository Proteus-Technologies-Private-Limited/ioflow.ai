#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Z-index hierarchy:
// Navigation: z-20 to z-50
// Modal backdrops: z-[100]
// Modal content: z-[110]
// Nested modals: z-[120]

const fixes = [
  // Fix modal backdrops and content
  { pattern: /className="fixed inset-0 bg-\S+ bg-opacity-\d+ .*?z-50/g, replacement: (match) => match.replace('z-50', 'z-[100]') },
  { pattern: /className="fixed inset-0 z-50/g, replacement: 'className="fixed inset-0 z-[100]' },
  { pattern: /className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50/g, replacement: 'className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[100]' },
  { pattern: /className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50/g, replacement: 'className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]' },
  { pattern: /className="fixed inset-0 z-10 overflow-y-auto/g, replacement: 'className="fixed inset-0 z-[100] overflow-y-auto' },
  { pattern: /className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50/g, replacement: 'className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[100]' },
  
  // Fix nested modals (z-60 to z-[120])
  { pattern: /z-60/g, replacement: 'z-[120]' },
];

const directories = [
  path.join(__dirname, 'src/components'),
  path.join(__dirname, 'src/pages')
];

function processFile(filePath) {
  if (!filePath.endsWith('.js') && !filePath.endsWith('.jsx')) {
    return;
  }

  let content = fs.readFileSync(filePath, 'utf8');
  let modified = false;

  fixes.forEach(fix => {
    const newContent = content.replace(fix.pattern, fix.replacement);
    if (newContent !== content) {
      content = newContent;
      modified = true;
    }
  });

  if (modified) {
    fs.writeFileSync(filePath, content);
    console.log(`Fixed z-index in: ${filePath}`);
  }
}

function processDirectory(dir) {
  const files = fs.readdirSync(dir);
  
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat.isDirectory()) {
      processDirectory(filePath);
    } else {
      processFile(filePath);
    }
  });
}

console.log('Fixing z-index values for modals...');
directories.forEach(dir => {
  if (fs.existsSync(dir)) {
    processDirectory(dir);
  }
});
console.log('Done!');