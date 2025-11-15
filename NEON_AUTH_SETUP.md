# Neon Auth Setup Guide

## Step 1: Find Your Neon Auth Project ID

You need to get your Neon Auth Project ID from your Neon dashboard. Here's how:

1. **Log into your Neon Dashboard**: Go to [console.neon.tech](https://console.neon.tech)
2. **Select your project** (`lexicon-db` or the project that contains your database)
3. **Navigate to Project Settings**:
   - Click on your project name in the sidebar
   - Look for "Settings" or "Project Settings"
   - OR go to the "Integrations" tab
4. **Find the Project ID**: 
   - In the Settings page, look for "Project ID" or "Project Identifier"
   - It's typically displayed as a UUID (e.g., `abc123def456...`) or alphanumeric string
   - **Note**: This is different from your database name (`lexicon-db`)
   - It might also be labeled as "Neon Project ID" or "Auth Project ID"
   
   **Alternative locations to check:**
   - **Integrations tab**: If you've set up GitHub integration, the Project ID might be shown there
   - **API Keys section**: Sometimes the Project ID is shown alongside API keys
   - **Connection string**: Your connection string might contain a project identifier

**If you can't find it in Neon Console:**

1. **Check Vercel Environment Variables**:
   - Go to your Vercel project: [vercel.com](https://vercel.com)
   - Select project: `preternatural-text-repo`
   - Navigate to: **Settings** → **Environment Variables**
   - Look for variables like:
     - `NEON_PROJECT_ID`
     - `POSTGRES_PRISMA_URL` (the connection string might contain the project ID)
     - Any other Neon-related variables

2. **Extract from Connection String**:
   - Your `POSTGRES_PRISMA_URL` connection string might look like:
     ```
     postgres://user:pass@ep-xxxxx-xxxxx.us-east-2.aws.neon.tech/dbname?sslmode=require
     ```
   - The part after `ep-` and before `.aws.neon.tech` might be related to your project
   - However, the Auth Project ID is usually different from the database endpoint

3. **Check Neon Auth Documentation**:
   - Neon Auth might use the same Project ID as your database project
   - Try using the project identifier from your Neon project settings
   - If Neon Auth is a separate service, you may need to enable it first in your Neon project

## Step 2: Configure Environment Variables

Create a `.env.local` file in your **frontend** directory (same level as `package.json`) with:

```env
VITE_NEON_AUTH_PROJECT_ID=your-project-id-here
```

**Important**: 
- The variable must start with `VITE_` to be accessible in the frontend
- Replace `your-project-id-here` with your actual Neon Auth Project ID
- Do NOT commit this file to git (it should be in `.gitignore`)

## Step 3: Configure Redirect URI in Neon Dashboard

In your Neon Auth settings, make sure you've added the following as an allowed redirect URI:

**For local development:**
```
http://localhost:5173/callback
```

**For production (when you deploy):**
```
https://your-domain.com/callback
```

## Step 4: Restart Your Development Server

After adding the environment variable:

1. Stop your frontend dev server (Ctrl+C)
2. Restart it: `npm run dev` (from the `frontend` directory)

## Step 5: Test the Login Flow

1. Navigate to `/login` in your app
2. Click "Login with GitHub"
3. You should be redirected to GitHub for authentication
4. After authorizing, you'll be redirected back to `/callback`
5. The app will store your JWT token and redirect you back to where you were

## Troubleshooting

### "Neon Auth Project ID not configured" error
- Make sure `.env.local` is in the `frontend` directory
- Make sure the variable name is exactly `VITE_NEON_AUTH_PROJECT_ID`
- Restart your dev server after adding the variable

### "Invalid redirect_uri" error
- Make sure `http://localhost:5173/callback` is added to your allowed redirect URIs in Neon Auth settings
- Check that the URL matches exactly (including `http://` and the port number)

### 403 Forbidden after login
- Make sure your GitHub account is linked to a user in your Neon database
- Make sure that user has the `role` field set to `"editor"` in the database
- Check the JWT token payload in browser console to verify the role

### Token not being saved
- Check browser console for errors
- Make sure localStorage is enabled in your browser
- Check that the callback URL is receiving the `token` query parameter

## Verifying Your Setup

After logging in, you can verify the token is working by:

1. Opening browser DevTools (F12)
2. Go to Console tab
3. Type: `localStorage.getItem('token')`
4. You should see a JWT token string
5. You can decode it at [jwt.io](https://jwt.io) to see the payload (including your role)

## Next Steps

Once authentication is working:
- You'll be able to save story boundaries without errors
- The backend will verify your JWT token on each request
- Only users with `role: "editor"` can modify boundaries

