from datetime import datetime
from zoneinfo import ZoneInfo
import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

pontos_ativos = {}

# Configuração dos IDs dos Canais
ID_CANAL_PONTO = 1559414525160063037  # Canal onde os comandos são aceitos
ID_CANAL_LOGS = 1569485496781111306  # Canal onde o relatório detalhado é enviado

# Fuso horário oficial do Brasil (Brasília)
FUSO_BR = ZoneInfo("America/Sao_Paulo")


@bot.event
async def on_ready():
  print(f"Bot {bot.user.name} está online e pronto para uso!")


@bot.command(name="entrada")
async def registrar_entrada(ctx):
  if ctx.channel.id != ID_CANAL_PONTO:
    await ctx.send(
        f"⚠️ {ctx.author.mention}, esse canal não é de bate ponto! Envie o"
        f" comando novamente no canal certo (<#{ID_CANAL_PONTO}>)!"
    )
    return

  user_id = ctx.author.id
  # Pega a data e hora ajustada para o fuso do Brasil
  agora_dt = datetime.now(FUSO_BR)
  agora_str = agora_dt.strftime("%d/%m/%Y às %H:%M:%S")

  if user_id in pontos_ativos:
    await ctx.send(
        f"⚠️ {ctx.author.mention}, você já bateu ponto de entrada em"
        f" {pontos_ativos[user_id]['str']}!"
    )
  else:
    pontos_ativos[user_id] = {"str": agora_str, "dt": agora_dt}
    await ctx.send(
        f"✅ **Entrada registrada** para {ctx.author.mention} em `{agora_str}`."
    )


@bot.command(name="saida")
async def registrar_saida(ctx):
  if ctx.channel.id != ID_CANAL_PONTO:
    await ctx.send(
        f"⚠️ {ctx.author.mention}, esse canal não é de bate ponto! Envie o"
        f" comando novamente no canal certo (<#{ID_CANAL_PONTO}>)!"
    )
    return

  user_id = ctx.author.id
  # Pega a data e hora da saída ajustada para o fuso do Brasil
  saida_dt = datetime.now(FUSO_BR)
  saida_str = saida_dt.strftime("%d/%m/%Y às %H:%M:%S")

  if user_id not in pontos_ativos:
    await ctx.send(
        f"⚠️ {ctx.author.mention}, você não tem uma entrada aberta para"
        " encerrar."
    )
  else:
    dados_entrada = pontos_ativos.pop(user_id)
    entrada_str = dados_entrada["str"]
    entrada_dt = dados_entrada["dt"]

    # Calcula a diferença de tempo
    diferenca = saida_dt - entrada_dt
    total_segundos = int(diferenca.total_seconds())

    horas = total_segundos // 3600
    minutos = (total_segundos % 3600) // 60

    tempo_trabalhado = f"{horas} hora(s) e {minutos} minuto(s)"

    # Resposta no chat normal
    await ctx.send(
        f"🛑 **Saída registrada** para {ctx.author.mention}.\n🕒 Entrada:"
        f" `{entrada_str}`\n🕒 Saída: `{saida_str}`\n⏱️ Tempo total:"
        f" `{tempo_trabalhado}`"
    )

    # Envia o relatório detalhado no canal de logs configurado
    canal_logs = bot.get_channel(ID_CANAL_LOGS)
    if canal_logs:
      embed = discord.Embed(
          title="📊 Relatório de Ponto - Turno Encerrado",
          color=discord.Color.blue(),
      )
      embed.add_field(
          name="Colaborador", value=ctx.author.mention, inline=False
      )
      embed.add_field(name="Entrada", value=entrada_str, inline=True)
      embed.add_field(name="Saída", value=saida_str, inline=True)
      embed.add_field(
          name="Tempo Trabalhado", value=tempo_trabalhado, inline=False
      )
      await canal_logs.send(embed=embed)


# Inicializa o bot usando a variável de ambiente segura do Railway
bot.run(os.getenv("DISCORD_TOKEN"))
