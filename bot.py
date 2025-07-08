import discord
from discord.ext import commands, tasks
import httpx
import aiofiles
import json
import os
from flask import Flask, request
import threading
import asyncio
import requests

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Flask app for Render health check and OAuth2 callback
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running!", 200

@app.route('/oauth/callback')
def oauth_callback():
    """Handle Discord OAuth2 callback."""
    code = request.args.get('code')
    guild_id = request.args.get('guild_id')
    permissions = request.args.get('permissions')
    if code:
        try:
            # Exchange code for access token
            data = {
                'client_id': os.getenv('CLIENT_ID'),
                'client_secret': os.getenv('CLIENT_SECRET'),
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': os.getenv('REDIRECT_URI', 'https://your-app-url.herokuapp.com/oauth/callback'),
                'scope': 'bot'
            }
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            response = requests.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
            response.raise_for_status()
            token_data = response.json()
            print(f"Token exchange successful: {token_data}")
            return f"Bot authorized successfully! Token: {token_data['access_token']}"
        except requests.exceptions.RequestException as e:
            print(f"Token exchange failed: {str(e)}, Response: {response.text if response else 'No response'}")
            return f"Token exchange failed: {response.text if response else str(e)}", 400
    error = request.args.get('error')
    if error:
        print(f"OAuth error: {error} - {request.args.get('error_description')}")
        return f"OAuth error: {error} - {request.args.get('error_description')}", 400
    print("No code provided in OAuth callback")
    return "Error: No code provided", 400

# ScoreSaber and BeatLeader API endpoints
SCORESABER_API = "https://scoresaber.com/api"
BEATLEADER_API = "https://api.beatleader.xyz"

async def fetch_player_info(platform, player_id):
    """Fetch player info from ScoreSaber or BeatLeader."""
    async with httpx.AsyncClient() as client:
        try:
            if platform.lower() == "scoresaber":
                url = f"{SCORESABER_API}/player/{player_id}/basic"
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                return {
                    "name": data["name"],
                    "rank": data["rank"],
                    "country": data["country"],
                    "pp": data["pp"],
                    "avatar": data["profilePicture"]
                }
            elif platform.lower() == "beatleader":
                url = f"{BEATLEADER_API}/player/{player_id}"
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                return {
                    "name": data["name"],
                    "rank": data["rank"],
                    "country": data["country"],
                    "pp": data["pp"],
                    "avatar": data["avatar"]
                }
            else:
                return None
        except httpx.HTTPStatusError as e:
            return f"HTTP error occurred: {str(e)}"
        except Exception as e:
            return f"Error fetching player info: {str(e)}"

async def update_ranked_playlist():
    """Fetch and update ScoreSaber ranked playlist."""
    async with httpx.AsyncClient() as client:
        try:
            url = f"{SCORESABER_API}/leaderboards?ranked=true&page=1&limit=50"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            playlist = {
                "playlistTitle": "ScoreSaber Ranked Maps",
                "playlistAuthor": "GrokBot",
                "playlistDescription": "Auto-updated top 50 ranked maps from ScoreSaber",
                "songs": []
            }

            for leaderboard in data["leaderboards"]:
                song = {
                    "songName": leaderboard["songName"],
                    "levelAuthorName": leaderboard["levelAuthorName"],
                    "hash": leaderboard["songHash"].upper(),
                    "difficulties": [
                        {
                            "characteristic": "Standard",
                            "name": leaderboard["difficulty"]["difficulty"].capitalize()
                        }
                    ]
                }
                playlist["songs"].append(song)

            async with aiofiles.open("playlist.json", "w") as f:
                await f.write(json.dumps(playlist, indent=2))

            return "Playlist updated successfully!"
        except httpx.HTTPStatusError as e:
            return f"HTTP error updating playlist: {str(e)}"
        except Exception as e:
            return f"Error updating playlist: {str(e)}"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guilds:")
    for guild in bot.guilds:
        print(f"- {guild.name} (ID: {guild.id})")
    
    if not update_playlist.is_running():
        update_playlist.start()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

@bot.command(name='ping')
async def ping(ctx):
    """Check if the bot is responsive"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"Pong! Latency: {latency}ms")

@bot.command()
async def search(ctx, platform: str, player_id: str):
    """Search for a player on ScoreSaber or BeatLeader"""
    if platform.lower() not in ["scoresaber", "beatleader"]:
        await ctx.send("Invalid platform. Use 'scoresaber' or 'beatleader'")
        return
    
    async with ctx.typing():
        result = await fetch_player_info(platform, player_id)
        
    if isinstance(result, dict):
        embed = discord.Embed(
            title=f"{result['name']}'s Profile ({platform.capitalize()})",
            color=discord.Color.blue()
        )
        embed.add_field(name="Global Rank", value=f"#{result['rank']:,}", inline=True)
        embed.add_field(name="Country", value=result["country"], inline=True)
        embed.add_field(name="PP", value=f"{result['pp']:,.2f}pp", inline=True)
        embed.set_thumbnail(url=result["avatar"])
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ {result}")

@bot.command()
async def playlist(ctx):
    """Get the latest ranked playlist"""
    if not os.path.exists("playlist.json"):
        await ctx.send("Playlist not found. Try updating it with `!update` first.")
        return
    
    await ctx.send(
        content="Here's the latest ScoreSaber ranked playlist!",
        file=discord.File("playlist.json")
    )

@bot.command()
async def update(ctx):
    """Update the ranked playlist"""
    message = await ctx.send("🔄 Updating playlist...")
    result = await update_ranked_playlist()
    await message.edit(content=result)

@tasks.loop(hours=24)
async def update_playlist():
    """Automatically update the playlist every 24 hours"""
    print("Performing scheduled playlist update...")
    result = await update_ranked_playlist()
    print(result)

@update_playlist.before_loop
async def before_update_playlist():
    """Wait until the bot is ready before starting the task"""
    await bot.wait_until_ready()

def run_flask():
    """Run Flask web server"""
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

def run_bot():
    """Run Discord bot with error handling"""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Error: DISCORD_TOKEN environment variable is missing!")
        return
    
    try:
        bot.run(token)
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
