# Local Development Setup for Stack Auth

Stack Auth requires redirect URIs to use domains with at least two labels (e.g., `example.com`). `localhost` doesn't work.

## Solution: Use a Local Domain

We'll set up `app.local` to point to your local machine. Using `.local` instead of `.dev` because browsers force HTTPS on `.dev` domains, but our dev server runs on HTTP.

### Step 1: Update Windows Hosts File

1. Open Notepad **as Administrator** (Right-click → Run as administrator)
2. Open the file: `C:\Windows\System32\drivers\etc\hosts`
3. Add this line at the end:
   ```
   127.0.0.1    app.local
   ```
4. Save the file

### Step 2: Flush DNS Cache (Optional but Recommended)

Open Command Prompt or PowerShell **as Administrator** and run:
```
ipconfig /flushdns
```

### Step 3: Configure Stack Auth

1. Go to your Stack Auth dashboard
2. Navigate to **Domain & Handlers** or **Redirect URIs**
3. Add: `http://app.local:5173/callback`
4. Save the configuration

### Step 4: Update Your Development Server

Your Vite dev server should automatically work with `app.local` since it's mapped to `127.0.0.1`.

### Step 5: Access Your App

Instead of `http://localhost:5173`, use:
```
http://app.local:5173
```

The code will automatically use the correct domain for the redirect URI.

## Alternative: Use ngrok (No Hosts File Changes)

If you prefer not to modify your hosts file, you can use ngrok:

1. Install ngrok: https://ngrok.com/download
2. Run: `ngrok http 5173`
3. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)
4. Add `https://abc123.ngrok.io/callback` to Stack Auth redirect URIs
5. Update your app to use the ngrok URL

Note: The ngrok URL changes each time you restart it (unless you have a paid plan).

