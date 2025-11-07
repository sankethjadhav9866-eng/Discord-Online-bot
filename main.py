import discord
from discord.ext import commands
import json
import random
import os
import asyncio
from datetime import datetime, timedelta

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")  # 🔒 Use Koyeb environment variable
PREFIX = "."
OWNER_IDS = ["1342508316911210551", "1405836534812508210"]
DAILY_REWARD = 5
DATA_FILE = "vortex_data.json"
COOLDOWN = 5  # seconds

# --- INIT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# --- DATA STORAGE ---
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"balances": {}, "daily": {}, "games": {}}

def save():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_balance(user_id):
    return data["balances"].get(str(user_id), 0)

def add_balance(user_id, amount):
    data["balances"][str(user_id)] = get_balance(user_id) + amount
    save()

def is_on_cooldown(user_id):
    return data["games"].get(str(user_id), False)

def set_cooldown(user_id, status):
    data["games"][str(user_id)] = status
    save()

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# --- COMMANDS ---
@bot.command()
async def balance(ctx):
    bal = get_balance(ctx.author.id)
    await ctx.send(f"💰 {ctx.author.mention}, your balance is {bal} coins.")

@bot.command()
async def daily(ctx):
    user_id = str(ctx.author.id)
    now = datetime.now()
    last_claim = data["daily"].get(user_id)
    if last_claim:
        last_time = datetime.fromisoformat(last_claim)
        if now - last_time < timedelta(days=1):
            await ctx.send(f"⏳ You already claimed daily reward!")
            return
    add_balance(ctx.author.id, DAILY_REWARD)
    data["daily"][user_id] = now.isoformat()
    save()
    await ctx.send(f"🎁 {ctx.author.mention}, you received {DAILY_REWARD} coins for today!")

@bot.command()
async def tip(ctx, member: discord.Member, amount: int):
    if amount < 1:
        await ctx.send("❌ Minimum tip is 1 coin.")
        return
    if get_balance(ctx.author.id) < amount:
        await ctx.send("❌ You don't have enough coins!")
        return
    add_balance(ctx.author.id, -amount)
    add_balance(member.id, amount)
    await ctx.send(f"🤝 {ctx.author.mention} tipped {amount} coins to {member.mention}!")

@bot.command()
async def opgive(ctx, member: discord.Member, amount: int):
    if str(ctx.author.id) not in OWNER_IDS:
        await ctx.send("🚫 You can't use this command!")
        return
    add_balance(member.id, amount)
    await ctx.send(f"💎 Gave {amount} coins to {member.mention}.")

# --- Blackjack ---
@bot.command()
async def blackjack(ctx, bet: int):
    user_id = str(ctx.author.id)
    if is_on_cooldown(user_id):
        await ctx.send("⚠️ Finish your current game first!")
        return
    if bet < 1 or get_balance(ctx.author.id) < bet:
        await ctx.send("❌ Invalid bet!")
        return
    set_cooldown(user_id, True)
    add_balance(ctx.author.id, -bet)
    player_cards = [random.randint(1,11), random.randint(1,11)]
    dealer_cards = [random.randint(1,11), random.randint(1,11)]
    await ctx.send(f"🃏 Your cards: {player_cards} (Total: {sum(player_cards)})")
    await ctx.send(f"Dealer shows: {dealer_cards[0]} + ?")

    def check(m):
        return m.author == ctx.author and m.content.lower() in [".hit",".stand"]

    while True:
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("⏰ Time's up! Game ended.")
            set_cooldown(user_id, False)
            return

        if msg.content.lower() == ".hit":
            card = random.randint(1,11)
            player_cards.append(card)
            total = sum(player_cards)
            await ctx.send(f"🃏 You drew {card}. Total: {total}")
            if total > 21:
                await ctx.send(f"💀 You busted! Lost {bet} coins.")
                set_cooldown(user_id, False)
                return
        elif msg.content.lower() == ".stand":
            total = sum(player_cards)
            dealer_total = sum(dealer_cards)
            while dealer_total < 17:
                dealer_cards.append(random.randint(1,11))
                dealer_total = sum(dealer_cards)
            await ctx.send(f"🃏 Dealer total: {dealer_total}")
            if dealer_total > 21 or total > dealer_total:
                winnings = bet*2
                add_balance(ctx.author.id, winnings)
                await ctx.send(f"🎉 You won {winnings} coins!")
            elif total == dealer_total:
                add_balance(ctx.author.id, bet)
                await ctx.send("🤝 It's a tie! Bet returned.")
            else:
                await ctx.send(f"💀 Dealer won! Lost {bet} coins.")
            set_cooldown(user_id, False)
            return

# --- Mines ---
@bot.command()
async def mines(ctx, bet: int):
    user_id = str(ctx.author.id)
    if is_on_cooldown(user_id):
        await ctx.send("⚠️ Finish your current game first!")
        return
    if bet < 1 or get_balance(ctx.author.id) < bet:
        await ctx.send("❌ Invalid bet!")
        return
    set_cooldown(user_id, True)
    add_balance(ctx.author.id, -bet)
    safe_squares = random.sample(range(1,26), 5)
    picked = []
    multiplier = 1
    await ctx.send("💣 Mines started! Pick squares 1-25 using `.pick <number>` (cashout anytime with `.cashout`).")
    data["games"][user_id] = {"type":"mines","bet":bet,"safe":safe_squares,"picked":picked,"multiplier":multiplier}
    save()

@bot.command()
async def pick(ctx, number: int):
    user_id = str(ctx.author.id)
    game = data["games"].get(user_id)
    if not game or game["type"]!="mines":
        await ctx.send("❌ You are not in a mines game!")
        return
    if number in game["picked"]:
        await ctx.send("⚠️ Already picked!")
        return
    if number in game["safe"]:
        game["picked"].append(number)
        game["multiplier"] += 1
        save()
        await ctx.send(f"✅ Safe! Multiplier now {game['multiplier']}x")
    else:
        set_cooldown(ctx.author.id, False)
        del data["games"][user_id]
        save()
        await ctx.send(f"💣 Boom! You lost your bet.")

@bot.command()
async def cashout(ctx):
    user_id = str(ctx.author.id)
    game = data["games"].get(user_id)
    if not game or game["type"]!="mines":
        await ctx.send("❌ You are not in a mines game!")
        return
    winnings = game["bet"] * game["multiplier"]
    add_balance(ctx.author.id, winnings)
    set_cooldown(ctx.author.id, False)
    del data["games"][user_id]
    save()
    await ctx.send(f"💰 You cashed out {winnings} coins! Balance: {get_balance(ctx.author.id)}")

# --- RUN BOT ---
import os
bot.run(os.getenv("TOKEN"))
