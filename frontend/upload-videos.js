import { put } from '@vercel/blob';
import fs from 'fs';
import path from 'path';

const videoFiles = [
  'Best.mp4',
  'Branches Light.mp4',
  'Growth.mp4',
  'Intro.mp4',
  'Lots of leaves.mp4',
  'MYstical.mp4',
  'No fire.mp4',
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