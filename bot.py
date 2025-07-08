import discord
from discord.ext import commands, tasks
import httpx
import aiofiles
import json
import os
from flask import Flask
import threading
import asyncio

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Flask app for Render health check
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running!", 200

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
                    "rank": data["globalRank"],
                    "country": data["country"],
                    "pp": data["pp"],
                    "avatar": data["avatar"]
                }
            else:
                return None
        except Exception as e:
            return f"Error fetching player info: {str(e)}"

async def update_ranked_playlist():
    """Fetch and update ScoreSaber ranked playlist."""
    async with httpx.AsyncClient() as client:
        try:
            # Fetch top 50 ranked maps (adjustable)
            url = f"{SCORESABER_API}/leaderboards?ranked=true&page=1&limit=50"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            # Create playlist in Beat Saber playlist format
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
                            "name": leaderboard["difficulty"]["difficulty"]
                        }
                    ]
                }
                playlist["songs"].append(song)

            # Save playlist to file
            async with aiofiles.open("playlist.json", "w") as f:
                await f.write(json.dumps(playlist, indent=2))

            return "Playlist updated successfully!"
        except Exception as e:
            return f"Error updating playlist: {str(e)}"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    update_playlist.start()  # Start the playlist update task

@bot.command()
async def search(ctx, platform, player_id):
    """Search for a player on ScoreSaber or BeatLeader."""
    result = await fetch_player_info(platform, player_id)
    if isinstance(result, dict):
        embed = discord.Embed(title=f"{result['name']}'s Profile ({platform})", color=0x00ff00)
        embed.add_field(name="Global Rank", value=result["rank"], inline=True)
        embed.add_field(name="Country", value=result["country"], inline=True)
        embed.add_field(name="PP", value=f"{result['pp']}pp", inline=True)
        embed.set_thumbnail(url=result["avatar"])
        await ctx.send(embed=embed)
    else:
        await ctx.send(result)

@bot.command()
async def playlist(ctx):
    """Share the latest ranked playlist."""
    if os.path.exists("playlist.json"):
        await ctx.send("Here's the latest ScoreSaber ranked playlist!", file=discord.File("playlist.json"))
    else:
        await ctx.send("Playlist not found. Try updating it with !update.")

@bot.command()
async def update(ctx):
    """Manually update the ranked playlist."""
    result = await update_ranked_playlist()
    await ctx.send(result)

@tasks.loop(hours=24)
async def update_playlist():
    """Auto-update the ranked playlist every 24 hours."""
    print("Updating ranked playlist...")
    result = await update_ranked_playlist()
    print(result)

def run_discord_bot():
    """Run the Discord bot in an async loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot.run(os.getenv("DISCORD_TOKEN"))

def main():
    """Start Flask server and Discord bot in separate threads."""
    # Start Discord bot in a separate thread
    bot_thread = threading.Thread(target=run_discord_bot)
    bot_thread.start()

    # Start Flask server (bound to 0.0.0.0 for Render)
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
