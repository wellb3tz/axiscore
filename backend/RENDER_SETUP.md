# Render Setup Instructions

## Manual Configuration via Render Dashboard

If you prefer configuring your Render deployment through the dashboard, follow these steps:

1. Log in to your Render account
2. Go to Dashboard and select your web service
3. Navigate to "Settings"
4. Under "Build & Deploy" section, find the "Build Command"
5. Enter the following command:

```
apt-get update && apt-get install -y p7zip-full unrar unzip && pip install -r requirements.txt
```

6. Click "Save Changes"
7. Trigger a manual deploy by clicking "Manual Deploy" > "Deploy latest commit"

## Verifying Installation

After deployment, to verify the archive tools are installed correctly, you can:

1. Go to "Shell" in your Render dashboard
2. Run the following commands:
   ```
   which 7z
   which unrar
   which unzip
   ```
3. You should see the paths to each command if they're installed correctly

## Troubleshooting

If you're still encountering issues:

1. Check the build logs for any errors during installation
2. Try running the extraction through Python fallbacks by modifying `archive_utils.py`:
   ```python
   # Set this to False to force Python-based extraction
   USE_COMMAND_LINE_TOOLS = False
   ```
3. Verify your environment variables are set correctly 