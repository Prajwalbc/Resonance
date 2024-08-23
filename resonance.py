import discord
from discord.ext import commands, tasks
import yt_dlp as youtube_dl
import asyncio
from dotenv import load_dotenv
import os
import time

# Load the .env file
load_dotenv()

# Get the token from the .env file
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Intents setup (You need this for managing voice state)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

# Create bot with more descriptive command prefix
bot = commands.Bot(command_prefix='-', intents=intents, help_command=None)

# Global variables to store queue, voice client, and other states
music_queue = []
current_song = None
vc = None
last_play_time = 0

# YouTube downloader options
ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

# Task to check for inactivity and leave if no one is in the voice channel
@tasks.loop(seconds=60)
async def check_inactivity():
    global vc

    if vc and vc.is_connected():
        # Leave if no one is in the voice channel
        if len(vc.channel.members) == 1:  # Only the bot is left
            await vc.disconnect()
            await vc.guild.text_channels[0].send(embed=discord.Embed(
                title="Disconnected",
                description="No one is left in the voice channel. Disconnecting...",
                color=discord.Color.purple()
            ))

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    check_inactivity.start()

@bot.command(name='play', aliases=['p'], help='Plays a song from a YouTube URL or search term.')
async def play(ctx, *, url: str):
    global vc, last_play_time
    try:
        voice_channel = ctx.author.voice.channel
        
        if not vc or not vc.is_connected():
            vc = await voice_channel.connect()

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                # Check if the URL is a playlist
                if "playlist" in url or "&list=" in url:
                    await ctx.send(embed=discord.Embed(
                        title="Playlist Detected",
                        description="Playlists are not supported. Please provide a single YouTube video URL or search by song name.",
                        color=discord.Color.red()
                    ))
                    return
                elif "youtube.com" in url or "youtu.be" in url:
                    info = ydl.extract_info(url, download=False)
                else:
                    info = ydl.extract_info(f"ytsearch:{url}", download=False)['entries'][0]
                
            except youtube_dl.DownloadError:
                await ctx.send(embed=discord.Embed(
                    title="Invalid Link",
                    description="The provided link is not valid or cannot be processed. Please provide a valid YouTube URL.",
                    color=discord.Color.red()
                ))
                return
            except IndexError:
                await ctx.send(embed=discord.Embed(
                    title="Song Not Found",
                    description="No results found for your search. Please try with a different search term.",
                    color=discord.Color.orange()
                ))
                return
            except Exception as e:
                await ctx.send(embed=discord.Embed(
                    title="Error",
                    description=f"An error occurred: {str(e)}",
                    color=discord.Color.red()
                ))
                return

        url2 = info['url']
        title = info['title']
        thumbnail = info['thumbnail']  # Album art
        duration = info['duration']  # Duration in seconds
        music_queue.append((url2, title, thumbnail, duration))
        
        if not vc.is_playing():
            await play_music(ctx)
        else:
            await ctx.send(embed=discord.Embed(
                title="Added to Queue",
                description=f"**{title}** has been added to the queue.",
                color=discord.Color.blue()
            ))
    except AttributeError:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description="You need to be in a voice channel to use this command.",
            color=discord.Color.red()
        ))
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An unexpected error occurred: {str(e)}",
            color=discord.Color.red()
        ))
        raise e

async def play_music(ctx):
    global current_song, vc, last_play_time
    
    try:
        if len(music_queue) > 0:
            current_song = music_queue.pop(0)
            vc.play(discord.FFmpegPCMAudio(current_song[0]), after=lambda e: asyncio.run_coroutine_threadsafe(play_music(ctx), bot.loop))
            last_play_time = time.time()  # Update the last play time

            duration_str = time.strftime('%H:%M:%S', time.gmtime(current_song[3]))

            embed = discord.Embed(
                title="Now Playing",
                description=f"**{current_song[1]}**",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=current_song[2])
            embed.add_field(name="Duration", value=duration_str)
            embed.set_footer(text="Use the commands to control playback.")

            await ctx.send(embed=embed)
                
        else:
            current_song = None
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An error occurred while playing the music: {str(e)}",
            color=discord.Color.red()
        ))
        raise e

@bot.command(name='stop', help='Stops the current song and clears the queue.')
async def stop(ctx):
    global vc, music_queue
    try:
        if vc and vc.is_playing():
            vc.stop()
            music_queue.clear()  # Clear the queue
            await ctx.send(embed=discord.Embed(
                title="Music Stopped",
                description="The music has been stopped and the queue has been cleared.",
                color=discord.Color.orange()
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="No Music Playing",
                description="There is no music currently playing.",
                color=discord.Color.orange()
            ))
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        ))
        raise e

@bot.command(name='skip', help='Skips the current song.')
async def skip(ctx):
    global vc
    try:
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send(embed=discord.Embed(
                title="Song Skipped",
                description="The current song has been skipped.",
                color=discord.Color.blue()
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="No Music Playing",
                description="There is no music currently playing.",
                color=discord.Color.orange()
            ))
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        ))
        raise e

@bot.command(name='pause', help='Pauses the current song.')
async def pause(ctx):
    global vc
    try:
        if vc and vc.is_playing():
            vc.pause()
            await ctx.send(embed=discord.Embed(
                title="Music Paused",
                description="The music has been paused.",
                color=discord.Color.yellow()
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="No Music Playing",
                description="There is no music currently playing.",
                color=discord.Color.orange()
            ))
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        ))
        raise e

@bot.command(name='resume', help='Resumes the paused song.')
async def resume(ctx):
    global vc
    try:
        if vc and vc.is_paused():
            vc.resume()
            await ctx.send(embed=discord.Embed(
                title="Music Resumed",
                description="The music has resumed playing.",
                color=discord.Color.green()
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="No Music Paused",
                description="There is no music currently paused.",
                color=discord.Color.orange()
            ))
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        ))
        raise e

@bot.command(name='queue', aliases=['q'], help='Shows the music queue and the currently playing song.')
async def queue(ctx):
    try:
        if vc and vc.is_playing() and current_song:
            now_playing = f"**Now Playing:**\n**{current_song[1]}**\n"
        else:
            now_playing = "**No song is currently playing.**\n"
        
        if music_queue:
            queue_str = "\n".join([f"{i+1}. **{song[1]}**" for i, song in enumerate(music_queue)])
            description = f"{now_playing}\n**Queue:**\n{queue_str}"
        else:
            description = f"{now_playing}\nThe queue is currently empty."
        
        await ctx.send(embed=discord.Embed(
            title="Music Queue",
            description=description,
            color=discord.Color.blue()
        ))
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        ))
        raise e

@bot.command(name='leave', aliases=['l'], help='Leaves the voice channel.')
async def leave(ctx):
    global vc
    try:
        if vc and vc.is_connected():
            await vc.disconnect()
            await ctx.send(embed=discord.Embed(
                title="Disconnected",
                description="The bot has disconnected from the voice channel.",
                color=discord.Color.purple()
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="Not Connected",
                description="The bot is not connected to any voice channel.",
                color=discord.Color.orange()
            ))
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        ))
        raise e

@bot.command(name='help', help='Displays this help message.')
async def help_cmd(ctx):
    try:
        # Generate the help message dynamically based on the available commands
        help_text = "\n".join([f"-{command.name} ({', '.join(command.aliases)}): {command.help}" for command in bot.commands])
        await ctx.send(embed=discord.Embed(
            title="Command List",
            description=help_text,
            color=discord.Color.blue()
        ))
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red()
        ))
        raise e

# Running the bot
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"Failed to start the bot: {str(e)}")
