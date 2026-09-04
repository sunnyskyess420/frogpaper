"""Provider UX configuration data for the Settings tab.

Single home for the CLOUD_PROVIDER_UX and AI_PROVIDER_UX dictionaries
that drive the dynamic setup guides, key fields and account-ID fields
in the Cloud and Generation settings sections.

Moved here from settings_tab.py (roadmap #7 Phase A) so the long
setup-step text lives in a data module instead of the UI facade.
"""

# Cloud provider UX configuration
CLOUD_PROVIDER_UX = {
    "google_drive": {
        "display_name": "Google Drive",
        "id_var_attr": "google_client_id_var",
        "secret_var_attr": "google_client_secret_var",
        "id_label": "Client ID",
        "secret_label": "Client Secret",
        "setup_url": "https://console.cloud.google.com/apis/credentials",
        "setup_steps": [
            "Go to https://console.cloud.google.com and create a project (or select existing).",
            'Enable the "Google Drive API" under APIs & Services > Library.',
            'Go to APIs & Services > OAuth consent screen and configure it (select "External" user type, fill in app name and your email, and save).',
            'While the app is in "Testing" mode, go to OAuth consent screen > Audience, click "Add Users", and add the Google account email you will sign in with. (This step is not needed once the app is published to Production.)',
            "Go to APIs & Services > Credentials > Create Credentials > OAuth client ID.",
            'Select "Desktop app" as the application type, give it a name, and click Create.',
            "Copy the Client ID and Client Secret into the fields above.",
        ],
        "icon_char": "G",
        "cloud_url": "https://drive.google.com/drive/my-drive",
    },
    "onedrive": {
        "display_name": "OneDrive",
        "id_var_attr": "onedrive_client_id_var",
        "secret_var_attr": "onedrive_client_secret_var",
        "id_label": "Client ID",
        "secret_label": "Client Secret",
        "setup_url": "https://developer.microsoft.com/en-us/microsoft-365/dev-program",
        "setup_steps": [
            "Go to https://developer.microsoft.com/en-us/microsoft-365/dev-program and join the FREE M365 Developer Program.",
            "This gives you an Azure directory (needed for personal MS accounts like hotmail.com / outlook.com).",
            "After joining, go to https://portal.azure.com > App registrations > New registration.",
            'Name it "FrogPaper", select "Accounts in any organizational directory and personal Microsoft accounts".',
            "Go to API permissions > Add a permission > Microsoft Graph > Delegated permissions. Search for and add \"Files.ReadWrite\".",
            'Select "Mobile and desktop applications" as the platform (NOT "Web"). No redirect URI is needed.',
            "Go to Certificates & secrets > New client secret. Copy the Value (NOT the Secret ID).",
            "Copy the Application (client) ID and the secret Value into the fields above.",
        ],
        "icon_char": "O",
        "cloud_url": "https://onedrive.live.com",
    },
    "dropbox": {
        "display_name": "Dropbox",
        "id_var_attr": "dropbox_app_key_var",
        "secret_var_attr": "dropbox_app_secret_var",
        "id_label": "App Key",
        "secret_label": "App Secret",
        "setup_url": "https://www.dropbox.com/developers/apps",
        "setup_steps": [
            "Go to https://www.dropbox.com/developers/apps and click \"Create app\".",
            'Choose "Scoped access" then "Full Dropbox" as the access type. Name it "FrogPaper".',
            "No redirect URI is needed — FrogPaper uses the copy-paste auth code flow.",
            "Go to the Permissions tab, enable files.content.write and files.content.read, then click Submit.",
            "Copy the App key and App secret (from the Settings tab) into the fields above.",
        ],
        "icon_char": "D",
        "cloud_url": "https://www.dropbox.com/home",
    },
}

# AI provider UX configuration — drives dynamic setup fields and guides
AI_PROVIDER_UX = {
    "Pollinations": {
        "display_name": "Pollinations.ai",
        "needs_key": False,
        "setup_steps": [
            "Pollinations.ai is completely free and requires no API key or account.",
            "Simply select it as your provider and start generating wallpapers immediately.",
            "It supports multiple FLUX models with no rate limits for normal use.",
            "If you experience slow generation, try switching to a faster provider like Fal.ai.",
        ],
    },
    "Prodia": {
        "display_name": "Prodia",
        "needs_key": True,
        "key_config_field": "prodia_key",
        "key_label": "Prodia API Key",
        "get_key_url": "https://app.prodia.com/api-keys",
        "setup_steps": [
            "Go to https://app.prodia.com and sign up for a Pro account (required for API access).",
            "Once logged in, go to https://app.prodia.com/api-keys.",
            "Click \"Create API Key\" and copy the key.",
            "Paste the key in the field above.",
            "Prodia uses the v2 API at inference.prodia.com for fast, reliable generation.",
            "Check https://app.prodia.com/pricing for current rates and plans.",
        ],
    },
    "Cloudflare": {
        "display_name": "Cloudflare Workers AI",
        "needs_key": True,
        "key_config_field": "cloudflare_token",
        "key_label": "Cloudflare API Token",
        "get_key_url": "https://dash.cloudflare.com/profile/api-tokens",
        "needs_account_id": True,
        "account_id_config_field": "cloudflare_account_id",
        "setup_steps": [
            "Go to https://dash.cloudflare.com and sign up for a free account (if you don't have one).",
            "To find your Account ID: go to https://dash.cloudflare.com/workers-and-pages and look at the URL in your browser's address bar. It will look like: dash.cloudflare.com/YOUR-ACCOUNT-ID-HERE/workers-and-pages. Copy that long hex string.",
            "You can also find it on the Workers & Pages page in the right column under \"Account Details\".",
            "Go to https://dash.cloudflare.com/profile/api-tokens.",
            "Click \"Create Token\". Use the \"Custom token\" option.",
            "Give it a name like \"FrogPaper\". Under Permissions, add: Account > Workers AI > Edit.",
            "Click \"Continue to summary\" then \"Create Token\". Copy the token value.",
            "Paste both your Account ID and API Token into the fields above.",
            "Free tier: 10,000 neurons/day — plenty for wallpaper generation.",
        ],
    },
    "Replicate": {
        "display_name": "Replicate",
        "needs_key": True,
        "key_config_field": "replicate_token",
        "key_label": "Replicate API Token",
        "get_key_url": "https://replicate.com/account/api-tokens",
        "setup_steps": [
            "Go to https://replicate.com and create a free account.",
            "Go to https://replicate.com/account/api-tokens.",
            "Find your API token (or click \"Create token\" if none exists). Copy it.",
            "Paste the token in the field above.",
            "Replicate charges pay-per-use: FLUX.schnell is ~$0.003/image, FLUX.dev is ~$0.025/image.",
            "You can add a payment method and set spending limits at https://replicate.com/account/billing.",
            "Replicate has the largest model library and is the most reliable option.",
        ],
    },
    "Fal": {
        "display_name": "Fal.ai",
        "needs_key": True,
        "key_config_field": "fal_key",
        "key_label": "Fal.ai API Key",
        "get_key_url": "https://fal.ai/dashboard/keys",
        "setup_steps": [
            "Go to https://fal.ai and create a free account.",
            "Add prepaid credits at https://fal.ai/dashboard/billing (minimum $1 to start).",
            "Once logged in, go to https://fal.ai/dashboard/keys.",
            "Click \"Create new API key\" and copy the key.",
            "Paste the key in the field above.",
            "Fal.ai is the fastest option (~1-2 sec for FLUX.schnell). Pay per use from prepaid credits.",
            "Monitor usage at https://fal.ai/dashboard/usage.",
        ],
    },
    "Hugging": {
        "display_name": "Hugging Face",
        "needs_key": True,
        "key_config_field": "huggingface_token",
        "key_label": "Hugging Face Token",
        "get_key_url": "https://huggingface.co/settings/tokens",
        "setup_steps": [
            "Go to https://huggingface.co and create a free account (if you don't have one).",
            "Go to https://huggingface.co/settings/tokens.",
            "Click \"New token\". For free usage, a \"Read\" token with access to \"Make calls to serverless Inference API\" is sufficient.",
            "If you want to access gated models (like FLUX.1-dev), select \"Write\" access.",
            "Copy the token and paste it in the field above.",
            "Free accounts get $0.10 in monthly credits that reset. Paid accounts get more.",
            "Note: As of August 2025, the free Inference API (api-inference.huggingface.co) is experiencing DNS issues. If generation fails, try another provider temporarily.",
        ],
    },
}
