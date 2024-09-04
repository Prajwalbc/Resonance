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

# Server-specific state storage
server_states = {}

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
    for guild_id, state in list(server_states.items()):
        vc = state.get('vc')
        if vc and vc.is_connected():
            # Leave if no one is in the voice channel
            if len(vc.channel.members) == 1:  # Only the bot is left
                await vc.disconnect()
                await state['text_channel'].send(embed=discord.Embed(
                    title="Disconnected",
                    description="No one is left in the voice channel. Disconnecting...",
                    color=discord.Color.purple()
                ))
                del server_states[guild_id]

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    check_inactivity.start()

def get_server_state(ctx):
    guild_id = ctx.guild.id
    if guild_id not in server_states:
        server_states[guild_id] = {
            'music_queue': [],
            'current_song': None,
            'vc': None,
            'is_looping': False,
            'text_channel': ctx.channel
        }
    return server_states[guild_id]

@bot.command(name='play', aliases=['p'], help='Plays a song from a YouTube URL or search term.')
async def play(ctx, *, url: str):
    state = get_server_state(ctx)
    state['is_looping'] = False  # Reset looping when a new song is played

    try:
        voice_channel = ctx.author.voice.channel
        
        if not state['vc'] or not state['vc'].is_connected():
            state['vc'] = await voice_channel.connect()

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
        state['music_queue'].append((url2, title, thumbnail, duration))
        
        if not state['vc'].is_playing():
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
    state = get_server_state(ctx)
    vc = state['vc']

    try:
        if len(state['music_queue']) > 0:
            state['current_song'] = state['music_queue'].pop(0)
            
            # Play the song
            vc.play(discord.FFmpegPCMAudio(state['current_song'][0]), after=lambda e: bot.loop.create_task(handle_next_song(ctx)))
            duration_str = time.strftime('%H:%M:%S', time.gmtime(state['current_song'][3]))

            embed = discord.Embed(
                title="Now Playing",
                description=f"**{state['current_song'][1]}**",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=state['current_song'][2])
            embed.add_field(name="Duration", value=duration_str)
            embed.set_footer(text="Use the commands to control playback.")

            await ctx.send(embed=embed)
                
        else:
            state['current_song'] = None
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An error occurred while playing the music: {str(e)}",
            color=discord.Color.red()
        ))
        raise e

async def handle_next_song(ctx):
    state = get_server_state(ctx)
    vc = state['vc']

    try:
        # Wait for the current song to finish
        if vc and vc.is_playing():
            while vc.is_playing():
                await asyncio.sleep(1)

        # Add a 2-second delay before playing the next song
        await asyncio.sleep(2)

        if state['is_looping'] and state['current_song']:
            # Replay the current song if looping is enabled
            state['music_queue'].insert(0, state['current_song'])  # Insert the current song back to the front of the queue
            await play_music(ctx)
        elif len(state['music_queue']) > 0:
            await play_music(ctx)
        else:
            state['current_song'] = None
            await ctx.send(embed=discord.Embed(
                title="Queue Empty",
                description="The music queue is empty. Add more songs to keep the party going!",
                color=discord.Color.orange()
            ))

    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="Error",
            description=f"An error occurred while transitioning to the next song: {str(e)}",
            color=discord.Color.red()
        ))

@bot.command(name='loop', help='Toggles loop for the current song.')
async def loop(ctx):
    state = get_server_state(ctx)
    state['is_looping'] = not state['is_looping']
    status = "enabled" if state['is_looping'] else "disabled"
    await ctx.send(embed=discord.Embed(
        title="Loop Toggled",
        description=f"Looping has been **{status}**.",
        color=discord.Color.purple()
    ))

@bot.command(name='stop', help='Stops the current song and clears the queue.')
async def stop(ctx):
    state = get_server_state(ctx)
    vc = state['vc']
    try:
        if vc and vc.is_playing():
            vc.stop()
            state['music_queue'].clear()  # Clear the queue
            state['is_looping'] = False  # Reset looping state
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
    state = get_server_state(ctx)
    vc = state['vc']
    try:
        if vc and vc.is_playing():
            vc.stop()  # Stop the current song, which triggers handle_next_song to play the next song
            await ctx.send(embed=discord.Embed(
                title="Song Skipped",
                description="The current song has been skipped.",
                color=discord.Color.blue()
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="No Music Playing",
                description="There is no music currently playing to skip.",
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
    state = get_server_state(ctx)
    vc = state['vc']
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
    state = get_server_state(ctx)
    vc = state['vc']
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
    state = get_server_state(ctx)
    vc = state['vc']
    try:
        if vc and vc.is_playing() and state['current_song']:
            now_playing = f"**Now Playing:**\n**{state['current_song'][1]}**\n"
        else:
            now_playing = "**No song is currently playing.**\n"
        
        if state['music_queue']:
            queue_str = "\n".join([f"{i+1}. **{song[1]}**" for i, song in enumerate(state['music_queue'])])
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
    state = get_server_state(ctx)
    vc = state['vc']
    try:
        if vc and vc.is_connected():
            await vc.disconnect()
            await ctx.send(embed=discord.Embed(
                title="Disconnected",
                description="The bot has disconnected from the voice channel.",
                color=discord.Color.purple()
            ))
            del server_states[ctx.guild.id]  # Clean up server state
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