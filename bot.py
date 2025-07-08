import discord
from discord.ext import commands, tasks
import httpx
import aiofiles
import json
import os
from flask import Flask, request, redirect, url_for
import threading
import asyncio
import requests
from urllib.parse import urlencode, quote

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Flask app
app = Flask(__name__)

# Configuration - MUST SET THESE IN ENVIRONMENT VARIABLES
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://bot-ytz9.onrender.com/oauth/callback')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
REQUIRED_SCOPES = 'identify email connections guilds'  # Added more scopes for user data

# API endpoints
SCORESABER_API = "https://scoresaber.com/api"
BEATLEADER_API = "https://api.beatleader.xyz"
DISCORD_API = "https://discord.com/api/v10"

@app.route('/')
def health_check():
    return "Bot is running!", 200

@app.route('/login')
def login():
    """Redirect to Discord OAuth2 with proper scopes"""
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': REQUIRED_SCOPES,
        'prompt': 'consent'  # Ensures fresh permissions are granted
    }
    auth_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    return redirect(auth_url)

@app.route('/oauth/callback')
def oauth_callback():
    """Handle Discord OAuth2 callback with proper user data fetching"""
    # Verify we have an authorization code
    code = request.args.get('code')
    if not code:
        error = request.args.get('error', 'Unknown error')
        error_desc = request.args.get('error_description', 'No description provided')
        print(f"OAuth error: {error} - {error_desc}")
        return f"Authorization failed: {error_desc}", 400

    try:
        # Step 1: Exchange code for access token
        token_data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'scope': REQUIRED_SCOPES
        }
        
        token_headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        token_response = requests.post(
            'https://discord.com/api/oauth2/token',
            data=token_data,
            headers=token_headers
        )
        
        # Check for token exchange errors
        if token_response.status_code != 200:
            error_data = token_response.json()
            print(f"Token exchange failed: {token_response.status_code} - {error_data}")
            return f"Token exchange failed: {error_data.get('error', 'Unknown error')}", 400

        tokens = token_response.json()
        access_token = tokens['access_token']
        
        # Step 2: Fetch user data with the access token
        user_headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        # First get basic user info
        user_response = requests.get(f'{DISCORD_API}/users/@me', headers=user_headers)
        if user_response.status_code != 200:
            print(f"User data fetch failed: {user_response.status_code} - {user_response.text}")
            return "Failed to fetch basic user data", 400
            
        user_data = user_response.json()
        
        # Get additional user connections if needed
        connections_response = requests.get(f'{DISCORD_API}/users/@me/connections', headers=user_headers)
        connections = connections_response.json() if connections_response.status_code == 200 else []
        
        # Get user guilds if needed
        guilds_response = requests.get(f'{DISCORD_API}/users/@me/guilds', headers=user_headers)
        guilds = guilds_response.json() if guilds_response.status_code == 200 else []
        
        # Format successful response
        response_html = f"""
        <h2>Authorization Successful!</h2>
        <p><strong>User:</strong> {user_data.get('username', 'Unknown')}#{user_data.get('discriminator', '0000')}</p>
        <p><strong>Email:</strong> {user_data.get('email', 'Not provided')}</p>
        <p><strong>Verified:</strong> {user_data.get('verified', False)}</p>
        <p><strong>Connections:</strong> {len(connections)} linked accounts</p>
        <p><strong>Guilds:</strong> Member of {len(guilds)} servers</p>
        <p>You can now close this window.</p>
        """
        
        return response_html

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {str(e)}")
        return f"Error during authorization: {str(e)}", 500
    except KeyError as e:
        print(f"Missing expected data in response: {str(e)}")
        return "Invalid response from Discord API", 500
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return "An unexpected error occurred", 500

# [Rest of your bot commands and ScoreSaber/BeatLeader functions...]

def run_flask():
    """Run Flask web server with proper configuration"""
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)

def run_bot():
    """Run Discord bot with enhanced error handling"""
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable is missing!")
        return
    
    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginError as e:
        print(f"Login failed: {str(e)}")
    except discord.HTTPException as e:
        print(f"HTTP error: {str(e)}")
    except Exception as e:
        print(f"Failed to start bot: {str(e)}")

def main():
    """Main entry point with configuration validation"""
    required_vars = ['DISCORD_TOKEN', 'CLIENT_ID', 'CLIENT_SECRET', 'REDIRECT_URI']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        return
    
    print("Starting application with configuration:")
    print(f"- Client ID: {CLIENT_ID}")
    print(f"- Redirect URI: {REDIRECT_URI}")
    print(f"- Required scopes: {REQUIRED_SCOPES}")
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    run_bot()

if __name__ == "__main__":
    main()
