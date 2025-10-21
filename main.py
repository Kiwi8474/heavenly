import discord
from discord.ext import commands
from dotenv import load_dotenv
import json
import os
import random
import asyncio
import time

# --- Hinweise/Erinnerungen ---

# Celesti = Währung für Voice & Chat Aktivität
# Solari = Währung für Glücksspiel
# Aetherium = Seltene Währung für besondere Anlässe und Fixpunkt für die Währungskurse
# Glimmer = Währung für D&D


# --- Setup oder so ---
load_dotenv() 
TOKEN = os.getenv('BOT_TOKEN')

intents = discord.Intents.all()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!m ", intents=intents, help_command=None)


# --- Konstanten ---

HEAVENLY_AREA_ID = 874706746483044382
BOT_ADMINS = [
    1208449439170039940 # Maxi
]
CURRENCIES_FILE_USE = ["celesti", "solari", "aetherium", "glimmer"]
CURRENCIES = ["celesti", "solari", "aetherium", "ätherium", "glimmer"]
CURRENCIES_DISPLAY = {
    "celesti": "Celesti",
    "solari": "Solari",
    "aetherium": "Aetherium", 
    "ätherium": "Aetherium",
    "glimmer": "Glimmer"
}
BASE_CURRENCY_NAME = "aetherium"
BASE_CURRENCY_VALUE = 1.0
VOLATILE_CURRENCIES = ["celesti", "solari", "glimmer"]
IDEAL_SUPPLY = 5_000_000
INFLATION_EXPONENT = 0.025
UPDATE_INTERVAL = 1 * 60 # Intervall für die Währungsupdates. 1 Minuten in Sekunden

# Voice Belohnungen
VOICE_REWARD_INTERVAL = 1 * 60
AETHERIUM_REWARD_PER_VOICE_INTERVAL = (1 / 60) / 10 # 0.1 Aetherium pro Stunde pro Person


# --- Dateien ---

files = [
    "pot", "user_currencies", "currency_courses",
    "currency_totals"
]


# --- Dictionaries ---

dicts = {
    "pot": {}, "user_currencies": {}, "currency_courses": {},
    "currency_totals": {}
}

voice_start_times = {}


# --- Hilfsfunktionen ---

def load_all_files():
    for file in files:
        with open(f"{file}.json", "r") as f:
            dicts[file] = json.load(f)

def save_all_files():
    for dic in dicts:
        with open(f"{dic}.json", "w") as f:
            json.dump(dicts[dic], f, indent=4)

def calculate_currencies(current_courses, currency_totals):
    new_courses = current_courses.copy()
    MAX_CHANGE_PERCENT = 0.20

    for currency in VOLATILE_CURRENCIES:
        current_value = new_courses[currency]

        current_supply = currency_totals[currency]

        if current_supply == 0:
            current_supply = IDEAL_SUPPLY

        supply_ratio = current_supply / IDEAL_SUPPLY
        inflation_factor = supply_ratio ** INFLATION_EXPONENT

        max_abs_change = current_value * MAX_CHANGE_PERCENT
        change_amount = random.uniform(-max_abs_change, max_abs_change)

        if inflation_factor < 0.001:
            inflation_factor = 0.001

        final_change = change_amount / inflation_factor
        new_value = current_value + final_change

        new_courses[currency] = round(max(0.01, new_value), 2)
    
    return new_courses

def update_currency_courses():
    dicts["currency_courses"] = calculate_currencies(dicts["currency_courses"], dicts["currency_totals"])
    save_all_files()


# --- Loops ---

async def currency_update_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        update_currency_courses()
        await asyncio.sleep(UPDATE_INTERVAL)

async def reward_voice_loop():
    await bot.wait_until_ready()

    heavenly_area = bot.get_guild(HEAVENLY_AREA_ID)

    while not bot.is_closed():
        await asyncio.sleep(VOICE_REWARD_INTERVAL)

        celesti_to_aetherium = dicts["currency_courses"]["celesti"]
        if celesti_to_aetherium < 0.01: celesti_to_aetherium = 0.01

        for member in heavenly_area.members:
            if member.voice and member.voice.channel and not member.bot:

                # wenn der user stumm/taub ist, überspringen
                if member.voice.self_mute or member.voice.self_deaf:
                    continue

                celesti_reward_float = AETHERIUM_REWARD_PER_VOICE_INTERVAL / celesti_to_aetherium
                celesti_reward = round(celesti_reward_float, 2)

                if celesti_reward < 0.01:
                    continue

                user_id = str(member.id)

                if user_id not in dicts["user_currencies"]:
                    dicts["user_currencies"][user_id] = {}
                    for user_currency in CURRENCIES_FILE_USE:
                        dicts["user_currencies"][user_id][user_currency] = 0

                
                current_celesti = dicts["user_currencies"][user_id]["celesti"]
                dicts["user_currencies"][user_id]["celesti"] = round(current_celesti + celesti_reward, 2)
                
                current_totals = dicts["currency_totals"]["celesti"]
                dicts["currency_totals"]["celesti"] = round(current_totals + celesti_reward, 2)

                save_all_files()


# --- Events ---

@bot.event
async def on_ready():
    print(f"Eingeloggt als {bot.user} (ID: {bot.user.id})")
    load_all_files()
    bot.loop.create_task(currency_update_loop())
    bot.loop.create_task(reward_voice_loop())
    print("Bot ist einsatzbereit")
    print("-----")


# --- Commands ---

# Adminbefehle

@bot.command(name="say", description="Lässt den Bot etwas sagen.")
@commands.check(lambda ctx: ctx.author.id in BOT_ADMINS)
async def say(ctx, *, msg: str):
    await bot.get_channel(1393932918451081267).send(msg)

@bot.command(name="shutdown", description="Schaltet den Bot aus.")
@commands.check(lambda ctx: ctx.author.id in BOT_ADMINS)
async def shutdown(ctx):
    save_all_files()
    await bot.close()

@bot.command(name="fill", description="Füllt den Pot.")
@commands.check(lambda ctx: ctx.author.id in BOT_ADMINS)
async def fill(ctx, amnt: int):
    if amnt is None:
        await ctx.send("Du musst eine Anzahl angeben.")
        return

    dicts["pot"]["solari"] += amnt
    dicts["currency_totals"]["solari"] += amnt

    await ctx.send(f"Der Pot wurde mit {amnt} Solari gefüllt und beträgt nun {dicts["pot"]["solari"]}.")

    save_all_files()

@bot.command(name="give", description="Gibt einem User eine Währung.")
@commands.check(lambda ctx: ctx.author.id in BOT_ADMINS)
async def give(ctx, user: discord.Member, crncy: str, amnt: int):
    currency = crncy.lower()

    if user is None:
        await ctx.send("Du musst einen User angeben.")
        return

    if currency is None:
        await ctx.send("Du musst eine Währung angeben.")
        return
    
    if amnt is None:
        await ctx.send("Du musst eine Anzahl angeben.")
        return

    if currency not in CURRENCIES:
        await ctx.send("Diese Währung gibt es nicht.")
        return
    
    user_id = str(user.id)

    if user_id not in dicts["user_currencies"]:
        dicts["user_currencies"][user_id] = {}
        for user_currency in CURRENCIES_FILE_USE:
            dicts["user_currencies"][user_id][user_currency] = 0

    dicts["user_currencies"][user_id][currency] += amnt
    dicts["currency_totals"][currency] += amnt
    save_all_files()
    await ctx.send(f"{user.display_name} hat {amnt} {CURRENCIES_DISPLAY[currency]} erhalten und hat nun {dicts["user_currencies"][user_id][currency]} {CURRENCIES_DISPLAY[currency]}.")

# DIESEN BEFEHL NICHT NUTZEN! ER VERÄNDERT NICHT DIE TOTALS!
# warum ist er dann drinne? keine ahnung.
@bot.command(name="reset", description="Setzt eine Währung eines Users zurück.")
@commands.check(lambda ctx: ctx.author.id in BOT_ADMINS)
async def give(ctx, user: discord.Member, crncy: str):
    currency = crncy.lower()

    if user is None:
        await ctx.send("Du musst einen User angeben.")
        return

    if crncy is None:
        await ctx.send("Du musst eine Währung angeben.")
        return

    if currency != "all" and currency not in CURRENCIES:
        await ctx.send("Diese Währung gibt es nicht.")
        return

    user_id = str(user.id)
    
    if user_id not in dicts["user_currencies"]:
        dicts["user_currencies"][user_id] = {}
        for user_currency in CURRENCIES_FILE_USE:
            dicts["user_currencies"][user_id][user_currency] = 0
    
    text = ""
    if currency == "all":
        for user_currency in dicts["user_currencies"][user_id]:
            dicts["user_currencies"][user_id][user_currency] = 0
        text += f"Alle Währungen von {user.display_name} wurden auf 0 gesetzt."
    else:
        dicts["user_currencies"][user_id][currency] = 0
        text += f"{CURRENCIES_DISPLAY[currency]} von {user.display_name} wurde auf 0 gesetzt."
    
    save_all_files()
    await ctx.send(text)


# Userbefehle

@bot.command(name="ping", description="Zeigt den Bot-Ping an.")
async def ping(ctx):
    await ctx.send(f"{round(bot.latency * 1000)} ms")

@bot.command(name="pot", description="Zeigt den aktuellen Pot.", aliases=["p"])
async def pot(ctx):
    await ctx.send(f"Der aktuelle Pot liegt bei {dicts["pot"]["solari"]}")

@bot.command(name="balance", description="Zeigt alle Währungen eines Users an.", aliases=["bal"])
async def balance(ctx, user: discord.Member=None):
    if user is None:
        user = ctx.author

    user_id = str(user.id)

    if user_id not in dicts["user_currencies"]:
        dicts["user_currencies"][user_id] = {}
        for user_currency in CURRENCIES_FILE_USE:
            dicts["user_currencies"][user_id][user_currency] = 0
    
    text = f"Währungen von {user.display_name}\n"

    for user_currency in dicts["user_currencies"][user_id]:
        text += f"{dicts["user_currencies"][user_id][user_currency]:.2f} {CURRENCIES_DISPLAY[user_currency]}\n"

    await ctx.send(text)

@bot.command(name="help", description="Sendet eine DM mit allen Befehlen.", aliases=["h", "hilfe", "cmds"])
async def bot_help(ctx):
    cmds = ""
    cmds += "## Userbefehle\n"
    cmds += "`ping` : Zeigt den Bot-Ping an.\n"
    cmds += "`pot / p` : Zeigt den aktuellen Pot.\n"
    cmds += "`balance / bal` : Zeigt alle Währungen eines Users an.\n"
    cmds += "`help / hilfe / h / cmds` : Sendet eine DM mit allen Befehlen.\n"
    cmds += "`transfer` : Überträgt eine Währung von deinem Konto auf das eines anderen Users.\n"

    cmds += "\n## Adminbefehle\n"
    cmds += "`say` : Lässt den Bot etwas sagen.\n"
    cmds += "`shutdown` : Schaltet den Bot aus.\n"
    cmds += "`fill` : Füllt den Pot.\n"
    cmds += "`give` : Gibt einem User eine Währung.\n"
    cmds += "`reset` : Setzt eine Währung eines Users zurück.\n"

    cmds += "\n## Glücksspielbefehle\n"
    cmds += "`coinflip / cf` : Spielt eine Runde Coinflip\n"

    await ctx.author.send(cmds)

@bot.command(name="transfer", description="Überträgt eine Währung von deinem Konto auf das eines anderen Users.")
async def transfer(ctx, user: discord.Member, crncy: str, amnt: int):
    currency = crncy.lower()
    amnt = float(amnt)

    if user is None:
        await ctx.send("Du musst einen User angeben.")
        return

    if crncy is None:
        await ctx.send("Du musst eine Währung angeben.")
        return
    
    if amnt is None:
        await ctx.send("Du musst eine Anzahl angeben.")
        return

    if currency not in CURRENCIES:
        await ctx.send("Diese Währung gibt es nicht.")
        return
    
    if amnt <= 1.0:
        await ctx.send("Der Mindestbetrag liegt bei 1.")
        return

    source_user_id = str(ctx.author.id)
    target_user_id = str(user.id)

    if source_user_id not in dicts["user_currencies"]:
        dicts["user_currencies"][source_user_id] = {}
        for user_currency in CURRENCIES_FILE_USE:
            dicts["user_currencies"][source_user_id][user_currency] = 0

    if target_user_id not in dicts["user_currencies"]:
        dicts["user_currencies"][target_user_id] = {}
        for user_currency in CURRENCIES_FILE_USE:
            dicts["user_currencies"][target_user_id][user_currency] = 0

    if amnt > dicts["user_currencies"][source_user_id][currency]:
        await ctx.send(f"Du hast ungenügend {CURRENCIES_DISPLAY[currency]}.")
        return


    total_debit = round(amnt, 2) # Überweisung

    tax_amount_float = amnt * 0.1
    tax_amount = round(tax_amount_float, 2) # Geldvernichtungssteuer

    amount_received = round(amnt - tax_amount, 2) # Betrag an den Empfänger

    # Transaktion
    dicts["user_currencies"][source_user_id][currency] -= total_debit
    dicts["user_currencies"][target_user_id][currency] += amount_received

    # Geld vernichten (muhahahahaha!)
    dicts["currency_totals"][currency] -= tax_amount

    await ctx.send(
        f"{ctx.author.display_name} hat {total_debit:.2f} {CURRENCIES_DISPLAY[currency]} gesendet.\n"
        f"{user.display_name} hat {amount_received:.2f} {CURRENCIES_DISPLAY[currency]} erhalten.\n"
        f"{tax_amount:.2f} {CURRENCIES_DISPLAY[currency]} wurden aufgrund der Geldvernichtungssteuer versteuert."
    )

    save_all_files()


# Glücksspielbefehle

@bot.command(name="coinflip", description="Spielt eine Runde Coinflip.", aliases=["cf"])
async def coinflip(ctx, bet: int, choice: str):
    if bet is None:
        await ctx.send("Du musst einen Einsatz angeben.")
        return
    
    if choice is None:
        await ctx.send("Du musst eine Wahl treffen.")

    user_choice = choice.lower()
    user_id = str(ctx.author.id)

    if user_id not in dicts["user_currencies"]:
        dicts["user_currencies"][user_id] = {}
        for user_currency in CURRENCIES_FILE_USE:
            dicts["user_currencies"][user_id][user_currency] = 0
    
    if bet > dicts["user_currencies"][user_id]["solari"]:
        await ctx.send("Du hast ungenügend Solari.")
        return

    choices = ["kopf", "zahl"]
    random_choice = random.choice(choices)

    if random_choice == user_choice:
        dicts["user_currencies"][user_id]["solari"] += bet
        dicts["pot"]["solari"] -= bet
        await ctx.send(f"Du hast {user_choice.title()} gewählt und gewonnen.\nDu erhältst {bet} Solari.")
    else:
        dicts["user_currencies"][user_id]["solari"] -= bet
        dicts["pot"]["solari"] += bet
        await ctx.send(f"Du hast {user_choice.title()} gewählt und verloren.\nDu verlierst {bet} Solari")

    save_all_files()


# --- Bot Start ---
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Bot Token fehlt")
