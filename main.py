import discord
from discord.ext import commands
import json, random, os, asyncio
from datetime import datetime, timedelta

# === CONFIG ===
PREFIX = "."
OWNER_IDS = ["1342508316911210551", "1405836534812508210"]
DAILY_REWARD = 5
DATA_FILE = "vortex_data.json"

# === INIT ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# === DATA LOAD ===
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"balances": {}, "daily": {}, "games": {}}

def save():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_balance(uid):
    return data["balances"].get(str(uid), 0)

def add_balance(uid, amount):
    data["balances"][str(uid)] = get_balance(uid) + amount
    save()

# === EVENTS ===
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# === COMMANDS ===
@bot.command()
async def balance(ctx):
    await ctx.send(f"💰 {ctx.author.mention}, your balance is {get_balance(ctx.author.id)} coins.")

@bot.command()
async def daily(ctx):
    uid = str(ctx.author.id)
    now = datetime.now()
    last = data["daily"].get(uid)
    if last:
        last_time = datetime.fromisoformat(last)
        if now - last_time < timedelta(days=1):
            await ctx.send("⏳ You already claimed daily reward!")
            return
    add_balance(uid, DAILY_REWARD)
    data["daily"][uid] = now.isoformat()
    save()
    await ctx.send(f"🎁 {ctx.author.mention}, you received {DAILY_REWARD} coins!")

@bot.command()
async def tip(ctx, member: discord.Member, amount: int):
    if amount < 1:
        return await ctx.send("❌ Minimum tip is 1 coin.")
    if get_balance(ctx.author.id) < amount:
        return await ctx.send("❌ You don't have enough coins!")
    add_balance(ctx.author.id, -amount)
    add_balance(member.id, amount)
    await ctx.send(f"🤝 {ctx.author.mention} tipped {amount} coins to {member.mention}!")

@bot.command()
async def opgive(ctx, member: discord.Member, amount: int):
    if str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send("🚫 You can’t use this command.")
    add_balance(member.id, amount)
    await ctx.send(f"💎 Gave {amount} coins to {member.mention}.")

# === BLACKJACK ===
@bot.command()
async def blackjack(ctx, bet: int):
    uid = str(ctx.author.id)
    if get_balance(uid) < bet or bet < 1:
        return await ctx.send("❌ Invalid bet!")
    add_balance(uid, -bet)
    player = [random.randint(1,11), random.randint(1,11)]
    dealer = [random.randint(1,11), random.randint(1,11)]
    await ctx.send(f"🃏 Your cards: {player} (Total: {sum(player)})")
    await ctx.send(f"Dealer shows: {dealer[0]} + ?")
    await ctx.send("Type `.hit` to draw or `.stand` to stay!")

    def check(m):
        return m.author == ctx.author and m.content.lower() in [".hit", ".stand"]

    while True:
        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send("⏰ Time's up! Game ended.")
            return

        if msg.content.lower() == ".hit":
            card = random.randint(1,11)
            player.append(card)
            total = sum(player)
            await ctx.send(f"🃏 You drew {card}. Total: {total}")
            if total > 21:
                await ctx.send(f"💀 Busted! Lost {bet} coins.")
                return
        elif msg.content.lower() == ".stand":
            total = sum(player)
            dealer_total = sum(dealer)
            while dealer_total < 17:
                dealer.append(random.randint(1,11))
                dealer_total = sum(dealer)
            await ctx.send(f"Dealer total: {dealer_total}")
            if dealer_total > 21 or total > dealer_total:
                win = bet*2
                add_balance(uid, win)
                await ctx.send(f"🎉 You won {win} coins!")
            elif total == dealer_total:
                add_balance(uid, bet)
                await ctx.send("🤝 Tie! Bet returned.")
            else:
                await ctx.send("💀 Dealer wins!")
            return

# === MINES ===
@bot.command()
async def mines(ctx, bet: int):
    uid = str(ctx.author.id)
    if get_balance(uid) < bet or bet < 1:
        return await ctx.send("❌ Invalid bet!")
    add_balance(uid, -bet)
    safe = random.sample(range(1,26), 5)
    data["games"][uid] = {"bet": bet, "safe": safe, "picked": [], "multiplier": 1}
    save()
    await ctx.send("💣 Mines started! Pick squares 1–25 using `.pick <number>`. Cashout anytime with `.cashout`.")

@bot.command()
async def pick(ctx, num: int):
    uid = str(ctx.author.id)
    g = data["games"].get(uid)
    if not g: return await ctx.send("❌ Not in a mines game!")
    if num in g["picked"]: return await ctx.send("⚠️ Already picked!")
    if num in g["safe"]:
        g["picked"].append(num)
        g["multiplier"] += 1
        add_balance(uid, 2)
        save()
        await ctx.send(f"✅ Safe! +2 coins. Multiplier: {g['multiplier']}x")
    else:
        del data["games"][uid]
        save()
        await ctx.send("💣 Boom! You lost your bet.")

@bot.command()
async def cashout(ctx):
    uid = str(ctx.author.id)
    g = data["games"].get(uid)
    if not g: return await ctx.send("❌ Not in a mines game!")
    win = g["bet"] * g["multiplier"]
    add_balance(uid, win)
    del data["games"][uid]
    save()
    await ctx.send(f"💰 You cashed out {win} coins!")

# === DEPOSIT ===
@bot.command()
async def deposit(ctx):
    try:
        await ctx.author.send(
            "**Robux Deposit Options:**\n"
            "2 Robux – https://www.roblox.com/game-pass/1232154663/Ty\n"
            "5 Robux – https://www.roblox.com/game-pass/1499732227/Thank-you\n"
            "10 Robux – https://www.roblox.com/game-pass/1240990679/Thank-you , https://www.roblox.com/game-pass/1241552744/Thank-you\n"
            "20 Robux – https://www.roblox.com/game-pass/1243945119/Tysm , https://www.roblox.com/game-pass/1243945119/Tysm\n"
            "40 Robux – https://www.roblox.com/game-pass/1234374789/Thank-you\n"
            "50 Robux – https://www.roblox.com/game-pass/1234072595/Thank-you\n"
            "100 Robux – https://www.roblox.com/game-pass/1232068254/Thank-you\n"
            "200 Robux – https://www.roblox.com/game-pass/1259027259/Thank-you\n"
            "300 Robux – https://www.roblox.com/game-pass/1259205084/Thank-you\n"
            "700 Robux – https://www.roblox.com/game-pass/1225880673/Tysm\n"
            "1000 Robux – https://www.roblox.com/game-pass/1239121933/Tysmm"
        )
        await ctx.send("📩 Check your DMs for deposit options!")
    except discord.Forbidden:
        await ctx.send("❌ I can’t DM you! Enable DMs from server members.")

# === RUN BOT ===
import os
bot.run(os.getenv("TOKEN"))
