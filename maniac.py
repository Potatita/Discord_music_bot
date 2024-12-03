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
        """Reproduce una canción o la agrega a la cola preprocesando su información."""
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

            # Preprocesar la canción (extraer información)
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))

            # Obtener la duración en formato mm:ss
            duration = f"{int(data['duration'] // 60)}:{int(data['duration'] % 60):02d}"

            # Almacenar la información preprocesada en la cola
            song_info = {
                "title": data.get("title", "Título desconocido"),
                "url": data["url"],
                "webpage_url": data["webpage_url"],
                "duration": duration
            }

            if ctx.guild.id not in queues:
                queues[ctx.guild.id] = []
            queues[ctx.guild.id].append(song_info)

            # Verificar si el bot ya está reproduciendo algo
            if voice_client.is_playing():
                await ctx.send(f"Agregado a la cola: {song_info['title']} - ⏱ {song_info['duration']}")
            else:
                # Iniciar la reproducción si no hay nada sonando
                await play_next(ctx)

        except Exception as e:
            await ctx.send(f"Error en el comando play: {e}")

    async def play_next(ctx):
        """Función para reproducir la siguiente canción en la cola."""
        try:
            if ctx.guild.id in queues and queues[ctx.guild.id]:
                # Obtener la siguiente canción en la cola
                song_info = queues[ctx.guild.id].pop(0)

                # Crear el reproductor de audio
                player = discord.FFmpegOpusAudio(song_info["url"], **ffmpeg_options)

                # Reproducir la canción
                voice_clients[ctx.guild.id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))

                await ctx.send(f"Reproduciendo: {song_info['title']} - {song_info['webpage_url']}")
            else:
                # Si no hay más canciones, desconectar
                await ctx.send("La cola está vacía. Desconectando...")
                await voice_clients[ctx.guild.id].disconnect()
                del voice_clients[ctx.guild.id]
        except Exception as e:
            await ctx.send(f"Error al reproducir la siguiente canción: {e}")

    @client.command(name="clear_queue")
    async def clear_queue(ctx):
        """Limpia toda la cola de reproducción."""
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
            await ctx.send("Queue cleared!")
        else:
            await ctx.send("There is no queue to clear")

    @client.command(name="pause")
    async def pause(ctx):
        """Pausa la canción actual."""
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
        """Detiene la reproducción y desconecta al bot del canal de voz."""
        try:
            voice_clients[ctx.guild.id].stop()
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
        except Exception as e:
            print(e)

    @client.command(name="queue")
    async def queue(ctx):
        """Muestra la lista de canciones encoladas con sus nombres y duración."""
        try:
            if ctx.guild.id not in queues or not queues[ctx.guild.id]:
                await ctx.send("La cola está vacía.")
                return
            
            queue_message = "**Canciones en la cola:**\n"
            for idx, song in enumerate(queues[ctx.guild.id], start=1):
                queue_message += f"{idx}. **{song['title']}** - ⏱ {song['duration']}\n"
            
            await ctx.send(queue_message)
        except Exception as e:
            await ctx.send(f"Error al mostrar la cola: {e}")

        
    @client.command(name="skip")
    async def skip(ctx):
        """Salta a la siguiente canción en la cola."""
        if ctx.guild.id in voice_clients and voice_clients[ctx.guild.id].is_playing():
            voice_clients[ctx.guild.id].stop()  # Detener la canción actual
            await ctx.send("Saltando a la siguiente canción...")
        else:
            await ctx.send("No hay ninguna canción reproduciéndose.")
    
    @client.command(name="ayuda")
    async def help(ctx):
        """Muestra dinámicamente una lista de comandos disponibles y sus descripciones."""
        help_message = "**Lista de Comandos Disponibles:**\n\n"
        
        # Iterar sobre todos los comandos registrados
        for command in client.commands:
            # Agregar el nombre y el `help` (docstring) de cada comando al mensaje
            help_message += f"**?{command.name}**\n  - {command.help if command.help else 'Sin descripción.'}\n\n"
        
        await ctx.send(help_message)



    client.run(TOKEN)