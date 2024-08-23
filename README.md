# Discord Music Bot 🎵

A powerful and easy-to-use Discord music bot that plays music from YouTube, with features like queue management, song search, and detailed now-playing embeds.

## Features

- 🎶 Play music from YouTube URLs or search by song name
- 📜 Queue management with the ability to skip, pause, resume, and stop songs
- 📜 Display the currently playing song with album art and duration
- 🚪 Automatically disconnects when the voice channel is empty
- 🗳️ Customizable command prefix and detailed command list

## Installation and Setup

Follow these instructions to set up and run the bot on your local machine.

### 1. **Clone the Repository**


### 2. **Create and Activate a Virtual Environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```
### 3. **Install the Required Python Packages**
```
pip install -r requirements.txt
```
### 4. **Set Up Your Environment Variables**
Create a .env file in the project directory to store your Discord bot token
``` 
DISCORD_BOT_TOKEN=your_discord_bot_token
```
### 5. **Run the Bot**
```
python3 resonance.py
```