import discord
from discord.ext import commands
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
import urllib.parse, urllib.request, re

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')
    intents = discord.Intents.default()
    intents.message_content = True
    client = commands.Bot(command_prefix="?", intents=intents)

    queues = {}
    voice_clients = {}
    youtube_base_url = 'https://www.youtube.com/'
    youtube_results_url = youtube_base_url + 'results?'
    youtube_watch_url = youtube_base_url + 'watch?v='
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {  
                        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=1"',
                        'options': '-vn -af loudnorm=I=-16:TP=-1.5:LRA=11'
                     }

    @client.event
    async def on_ready():
        print(f'{client.user} esta corriendo')

    @client.command(name="play")
    async def play(ctx, *, link):
        try:
            # Conectar al canal de voz del usuario si no está conectado
            if ctx.guild.id not in voice_clients or not voice_clients[ctx.guild.id].is_connected():
                voice_client = await ctx.author.voice.channel.connect()
                voice_clients[ctx.guild.id] = voice_client
            else:
                voice_client = voice_clients[ctx.guild.id]

            # Manejar búsqueda si el enlace no es un URL completo
            if youtube_base_url not in link:
                query_string = urllib.parse.urlencode({'search_query': link})
                content = urllib.request.urlopen(youtube_results_url + query_string)
                search_results = re.findall(r'/watch\?v=(.{11})', content.read().decode())
                link = youtube_watch_url + search_results[0]

            # Agregar la canción a la cola
            if ctx.guild.id not in queues:
                queues[ctx.guild.id] = []
            queues[ctx.guild.id].append(link)

            # Si ya está reproduciendo, solo agregar a la cola y enviar mensaje
            if voice_client.is_playing():
                await ctx.send(f"Agregado a la cola: {link}")
            else:
                # Iniciar la reproducción si no hay nada sonando
                await play_next(ctx)

        except Exception as e:
            await ctx.send(f"Error en el comando play: {e}")


    async def play_next(ctx):
        """Función para reproducir la siguiente canción en la cola."""
        try:
            if ctx.guild.id in queues and queues[ctx.guild.id]:
                # Obtener el siguiente enlace en la cola
                link = queues[ctx.guild.id].pop(0)

                # Descargar información del video con yt_dlp
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))
                song = data['url']

                # Crear el reproductor de audio
                player = discord.FFmpegOpusAudio(song, **ffmpeg_options)

                # Reproducir la canción
                voice_clients[ctx.guild.id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))

                await ctx.send(f"Reproduciendo: {data['title']}")
            else:
                # Si no hay más canciones, desconectar
                await ctx.send("La cola está vacía. Desconectando...")
                await voice_clients[ctx.guild.id].disconnect()
                del voice_clients[ctx.guild.id]
        except Exception as e:
            await ctx.send(f"Error al reproducir la siguiente canción: {e}")

    @client.command(name="clear_queue")
    async def clear_queue(ctx):
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
            await ctx.send("Queue cleared!")
        else:
            await ctx.send("There is no queue to clear")

    @client.command(name="pause")
    async def pause(ctx):
        try:
            voice_clients[ctx.guild.id].pause()
        except Exception as e:
            print(e)

    @client.command(name="resume")
    async def resume(ctx):
        try:
            voice_clients[ctx.guild.id].resume()
        except Exception as e:
            print(e)

    @client.command(name="stop")
    async def stop(ctx):
        try:
            voice_clients[ctx.guild.id].stop()
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
        except Exception as e:
            print(e)

    @client.command(name="list")
    async def list(ctx):
        try:
            for q in queues[ctx.guild.id]:
                await ctx.send(q) 
        except Exception as e:
            print(e)
        
    @client.command(name="skip")
    async def skip(ctx):
        if ctx.guild.id in voice_clients and voice_clients[ctx.guild.id].is_playing():
            voice_clients[ctx.guild.id].stop()  # Detener la canción actual
            await ctx.send("Saltando a la siguiente canción...")
        else:
            await ctx.send("No hay ninguna canción reproduciéndose.")


    client.run(TOKEN)