from datetime import datetime, timedelta, timezone
import os
import discord
from discord.ext import commands, tasks

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

pontos_ativos = {}

# Configuração dos IDs dos Canais
ID_CANAL_PONTO = 1559414525160063037
ID_CANAL_LOGS = 1569485496781111306

# Fuso horário do Brasil (-3 horas em relação ao UTC)
FUSO_BR = timezone(timedelta(hours=-3))


class CheckInView(discord.ui.View):

  def __init__(self, user_id):
    super().__init__(timeout=300)
    self.user_id = user_id
    self.respondido = False

  @discord.ui.button(
      label="Estou Trabalhando! ✅", style=discord.ButtonStyle.green
  )
  async def confirmar(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if interaction.user.id != self.user_id:
      await interaction.response.send_message(
          "⚠️ Este botão não é para ti!", ephemeral=True
      )
      return

    self.respondido = True
    if self.user_id in pontos_ativos:
      pontos_ativos[self.user_id]["ultimo_checkin"] = datetime.now(FUSO_BR)
      pontos_ativos[self.user_id]["aviso_pendente"] = False

    await interaction.response.edit_message(
        content=(
            "✅ **Check-in confirmado com sucesso!** Ponto continua a correr"
            " normalmente."
        ),
        view=None,
    )
    self.stop()

  async def on_timeout(self):
    if not self.respondido and self.user_id in pontos_ativos:
      dados = pontos_ativos.pop(self.user_id)
      entrada_dt = dados["dt"]
      entrada_str = dados["str"]

      saida_dt = datetime.now(FUSO_BR)
      saida_str = saida_dt.strftime("%d/%m/%Y às %H:%M:%S")

      diferenca = saida_dt - entrada_dt
      total_segundos = int(diferenca.total_seconds())
      horas = total_segundos // 3600
      minutos = (total_segundos % 3600) // 60
      tempo_trabalhado = f"{horas} hora(s) e {minutos} minuto(s)"

      user = bot.get_user(self.user_id)
      mention = user.mention if user else f"<@id:{self.user_id}>"

      canal_logs = bot.get_channel(ID_CANAL_LOGS)
      if canal_logs:
        embed = discord.Embed(
            title="⚠️ Ponto Encerrado por Inatividade (Check-in Perdido)",
            color=discord.Color.red(),
        )
        embed.add_field(name="Colaborador", value=mention, inline=False)
        embed.add_field(name="Entrada", value=entrada_str, inline=True)
        embed.add_field(
            name="Saída (Automática)", value=saida_str, inline=True
        )
        embed.add_field(
            name="Tempo Trabalhado", value=tempo_trabalhado, inline=False
        )
        await canal_logs.send(embed=embed)


class PainelConfigView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="📊 Ver Pontos Ativos",
      style=discord.ButtonStyle.primary,
      custom_id="btn_listar_pontos",
  )
  async def listar_pontos(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not pontos_ativos:
      await interaction.response.send_message(
          "📂 De momento, **não há nenhum ponto ativo** no servidor.",
          ephemeral=True,
      )
      return

    descricao = ""
    agora = datetime.now(FUSO_BR)
    for uid, dados in pontos_ativos.items():
      tempo_decorrido = agora - dados["dt"]
      hrs = int(tempo_decorrido.total_seconds() // 3600)
      mins = int((tempo_decorrido.total_seconds() % 3600) // 60)
      descricao += f"• <@{uid}> — Entrou em `{dados['str']}` (Trabalhando há {hrs}h {mins}m)\n"

    embed = discord.Embed(
        title="👥 Lista de Colaboradores em Serviço",
        description=descricao,
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

  @discord.ui.button(
      label="🧪 Testar Check-in (30m)",
      style=discord.ButtonStyle.secondary,
      custom_id="btn_testar_checkin",
  )
  async def testar_checkin(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if interaction.user.id not in pontos_ativos:
      await interaction.response.send_message(
          "⚠️ Precisas de ter um ponto ativo (`!entrada`) para testar o"
          " check-in!",
          ephemeral=True,
      )
      return

    pontos_ativos[interaction.user.id]["ultimo_checkin"] = datetime.now(
        FUSO_BR
    ) - timedelta(minutes=31)
    pontos_ativos[interaction.user.id]["aviso_pendente"] = False

    await interaction.response.send_message(
        "🧪 **Simulação acionada!** Vê a tua DM ou o canal de ponto para"
        " responder ao botão.",
        ephemeral=True,
    )

  @discord.ui.button(
      label="⚙️ Estado do Sistema",
      style=discord.ButtonStyle.success,
      custom_id="btn_status_sistema",
  )
  async def status_sistema(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    embed = discord.Embed(
        title="⚙️ Painel de Informações - Bot Ponto",
        color=discord.Color.green(),
    )
    embed.add_field(
        name="Canal de Ponto Configurado",
        value=f"<#{ID_CANAL_PONTO}>",
        inline=False,
    )
    embed.add_field(
        name="Canal de Logs Configurado",
        value=f"<#{ID_CANAL_LOGS}>",
        inline=False,
    )
    embed.add_field(
        name="Fuso Horário", value="Horário de Brasília (UTC-3)", inline=True
    )
    embed.add_field(
        name="Intervalo de Check-in", value="30 minutos", inline=True
    )
    embed.add_field(
        name="Total de Funcionários Ativos",
        value=str(len(pontos_ativos)),
        inline=True,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tasks.loop(minutes=1)
async def verificar_inativos():
  agora = datetime.now(FUSO_BR)
  for user_id, dados in list(pontos_ativos.items()):
    ultimo_chk = dados.get("ultimo_checkin", dados["dt"])
    if agora - ultimo_chk >= timedelta(minutes=30):
      if not dados.get("aviso_pendente", False):
        pontos_ativos[user_id]["aviso_pendente"] = True
        user = bot.get_user(user_id)
        if user:
          try:
            view = CheckInView(user_id)
            await user.send(
                "⏰ **[Sistema de Ponto]** Você está em serviço há 30 minutos"
                " sem interagir. Por favor, clique no botão abaixo em até **5"
                " minutos**:",
                view=view,
            )
          except Exception:
            canal = bot.get_channel(ID_CANAL_PONTO)
            if canal:
              view = CheckInView(user_id)
              await canal.send(
                  f"⏰ <@{user_id}>, verificação de segurança pendente! Clique no"
                  " botão abaixo em até **5 minutos**:",
                  view=view,
              )


@bot.event
async def on_ready():
  print(f"Bot {bot.user.name} está online e pronto para uso!")
  if not verificar_inativos.is_running():
    verificar_inativos.start()


@bot.command(name="entrada")
async def registrar_entrada(ctx):
  if ctx.channel.id != ID_CANAL_PONTO:
    await ctx.send(
        f"⚠️ {ctx.author.mention}, esse canal não é de bate ponto! Envie o"
        f" comando no canal certo (<#{ID_CANAL_PONTO}>)!"
    )
    return

  user_id = ctx.author.id
  agora_dt = datetime.now(FUSO_BR)
  agora_str = agora_dt.strftime("%d/%m/%Y às %H:%M:%S")

  if user_id in pontos_ativos:
    await ctx.send(
        f"⚠️ {ctx.author.mention}, você já tem um ponto aberto em"
        f" `{pontos_ativos[user_id]['str']}`!"
    )
  else:
    pontos_ativos[user_id] = {
        "str": agora_str,
        "dt": agora_dt,
        "ultimo_checkin": agora_dt,
        "aviso_pendente": False,
    }
    await ctx.send(
        f"✅ **Entrada registrada** para {ctx.author.mention} em `{agora_str}`."
    )


@bot.command(name="saida")
async def registrar_saida(ctx):
  if ctx.channel.id != ID_CANAL_PONTO:
    await ctx.send(
        f"⚠️ {ctx.author.mention}, esse canal não é de bate ponto! Envie o"
        f" comando no canal certo (<#{ID_CANAL_PONTO}>)!"
    )
    return

  user_id = ctx.author.id
  saida_dt = datetime.now(FUSO_BR)
  saida_str = saida_dt.strftime("%d/%m/%Y às %H:%M:%S")

  if user_id not in pontos_ativos:
    await ctx.send(
        f"⚠️ {ctx.author.mention}, você não tem nenhuma entrada aberta para"
        " encerrar."
    )
  else:
    dados_entrada = pontos_ativos.pop(user_id)
    entrada_str = dados_entrada["str"]
    entrada_dt = dados_entrada["dt"]

    diferenca = saida_dt - entrada_dt
    total_segundos = int(diferenca.total_seconds())
    horas = total_segundos // 3600
    minutos = (total_segundos % 3600) // 60
    tempo_trabalhado = f"{horas} hora(s) e {minutos} minuto(s)"

    await ctx.send(
        f"🛑 **Saída registrada** para {ctx.author.mention}.\n🕒 Entrada:"
        f" `{entrada_str}`\n🕒 Saída: `{saida_str}`\n⏱️ Tempo total:"
        f" `{tempo_trabalhado}`"
    )

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


@bot.command(name="painel")
async def abrir_painel(ctx):
  """Envia o painel interativo sem exigir cargos de admin para teste."""
  print(f"[LOG] Comando !painel executado por {ctx.author} no canal {ctx.channel}")
  embed = discord.Embed(
      title="🎛️ Painel de Controlo - Sistema de Ponto",
      description=(
          "Usa os botões abaixo para gerir, testar ou visualizar o estado atual"
          " do bot de ponto:"
      ),
      color=discord.Color.dark_theme(),
  )
  embed.add_field(
      name="Opções disponíveis:",
      value=(
          "• **Ver Pontos Ativos:** Mostra quem está em serviço no momento.\n•"
          " **Testar Check-in:** Simula o aviso de 30 minutos para ti.\n•"
          " **Estado do Sistema:** Mostra canais e configurações ativas."
      ),
      inline=False,
  )

  view = PainelConfigView()
  await ctx.send(embed=embed, view=view)


bot.run(os.getenv("DISCORD_TOKEN"))
