import discord
from discord.ext import commands, tasks
import httpx
import aiofiles
import json
import os
from flask import Flask, request, redirect
import threading
import asyncio
import requests
from urllib.parse import urlencode

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Flask app
app = Flask(__name__)

# Configuration
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://bot-ytz9.onrender.com/oauth/callback')
BOT_TOKEN = os.getenv('DISCORD_TOKEN')
REQUIRED_SCOPES = 'identify bot applications.commands'

# API endpoints
SCORESABER_API = "https://scoresaber.com/api"
BEATLEADER_API = "https://api.beatleader.xyz"
DISCORD_API = "https://discord.com/api/v10"
OAUTH_URL = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&permissions=8&redirect_uri={REDIRECT_URI}&response_type=code&scope={REQUIRED_SCOPES}"

@app.route('/')
def health_check():
    return "Bot is running!", 200

@app.route('/login')
def login():
    """Redirect to Discord OAuth2"""
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': REQUIRED_SCOPES,
        'permissions': '8'
    }
    return redirect(f"https://discord.com/api/oauth2/authorize?{urlencode(params)}")

@app.route('/oauth/callback')
def oauth_callback():
    """Handle Discord OAuth2 callback"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        error_desc = request.args.get('error_description', 'No description provided')
        print(f"OAuth error: {error} - {error_desc}")
        return f"Authorization failed: {error_desc}", 400
    
    if not code:
        return "Error: No authorization code provided", 400

    try:
        # Prepare token request data
        data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'scope': REQUIRED_SCOPES
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        # Exchange code for tokens
        response = requests.post(
            'https://discord.com/api/oauth2/token',
            data=data,
            headers=headers
        )
        
        # Check for errors in response
        if response.status_code != 200:
            error_data = response.json()
            print(f"Token exchange failed: {response.status_code} - {error_data}")
            return f"Token exchange failed: {error_data.get('error_description', 'Unknown error')}", 400

        token_data = response.json()
        access_token = token_data['access_token']
        refresh_token = token_data.get('refresh_token')
        
        # Use the access token to fetch user data
        user_headers = {
            'Authorization': f'Bearer {access_token}'
        }
        user_response = requests.get(f'{DISCORD_API}/users/@me', headers=user_headers)
        
        if user_response.status_code != 200:
            return "Failed to fetch user data", 400
            
        user_data = user_response.json()
        
        return f"""
            Authorization successful!<br>
            User: {user_data['username']}#{user_data['discriminator']}<br>
            Access Token: {access_token[:10]}...<br>
            Refresh Token: {refresh_token[:10] + '...' if refresh_token else 'None'}
        """
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {str(e)}")
        return f"Error during authorization: {str(e)}", 500
    except KeyError as e:
        print(f"Missing expected data in response: {str(e)}")
        return "Invalid response from Discord API", 500
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return "An unexpected error occurred", 500

# ... [Rest of your existing bot commands and functions remain the same] ...

def run_flask():
    """Run Flask web server"""
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

def run_bot():
    """Run Discord bot with error handling"""
    if not BOT_TOKEN:
        print("Error: DISCORD_TOKEN environment variable is missing!")
        return
    
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginError:
        print("Error: Invalid Discord token provided")
    except Exception as e:
        print(f"Failed to start bot: {e}")

def main():
    """Main entry point"""
    required_vars = ['DISCORD_TOKEN', 'CLIENT_ID', 'CLIENT_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        return
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    run_bot()

if __name__ == "__main__":
    main()
