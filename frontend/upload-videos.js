import { put } from '@vercel/blob';
import fs from 'fs';
import path from 'path';

const videoFiles = [
  'Lamp.mp4',
  'Library.mp4',
  'Quick.mp4',
  'Stream.mp4',
  'Two Figures.mp4',
  'Webs.mp4',
  'Which Way.mp4',
];

async function uploadVideos() {
  const urls = {};
  
  for (const filename of videoFiles) {
    const filePath = path.join('public', filename);
    const file = fs.readFileSync(filePath);
    
    console.log(`Uploading ${filename}...`);
    const blob = await put(filename, file, {
      access: 'public',
      token: process.env.BLOB_READ_WRITE_TOKEN,
    });
    
    urls[filename] = blob.url;
    console.log(`✓ ${filename} -> ${blob.url}`);
  }
  
  console.log('\nAll URLs:');
  console.log(JSON.stringify(urls, null, 2));
}

uploadVideos().catch(console.error);