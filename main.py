import discord
from discord.ext import commands
import random
import asyncio
import sqlite3
import os

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)

# --- DATABASE SETUP ---
conn = sqlite3.connect("coins.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER)")
conn.commit()

# --- OWNER IDs ---
OWNER_IDS = [1342508316911210551, 1405836534812508210]

# --- HELPER FUNCTIONS ---
def get_balance(user_id):
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    return row[0] if row else 0

def update_balance(user_id, amount):
    bal = get_balance(user_id)
    new_bal = bal + amount
    c.execute("INSERT OR REPLACE INTO users (user_id, balance) VALUES (?, ?)", (user_id, new_bal))
    conn.commit()

# --- COMMANDS ---

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
async def balance(ctx):
    bal = get_balance(ctx.author.id)
    await ctx.send(f"💰 {ctx.author.mention}, you have **{bal} coins**!")

@bot.command()
async def daily(ctx):
    update_balance(ctx.author.id, 100)
    await ctx.send(f"🎁 {ctx.author.mention}, you claimed **100 coins** daily!")

@bot.command()
async def tip(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("❌ Amount must be positive.")
        return
    bal = get_balance(ctx.author.id)
    if bal < amount:
        await ctx.send("❌ Not enough coins.")
        return
    update_balance(ctx.author.id, -amount)
    update_balance(member.id, amount)
    await ctx.send(f"🤝 {ctx.author.mention} tipped {member.mention} **{amount} coins**!")

@bot.command()
async def opgive(ctx, member: discord.Member, amount: int):
    if ctx.author.id not in OWNER_IDS:
        await ctx.send("❌ You can’t use this command.")
        return
    update_balance(member.id, amount)
    await ctx.send(f"🪙 Gave {member.mention} **{amount} coins** successfully.")

@bot.command()
async def blackjack(ctx, bet: int):
    bal = get_balance(ctx.author.id)
    if bal < bet:
        await ctx.send("❌ Not enough coins.")
        return

    player_total = random.randint(15, 21)
    dealer_total = random.randint(17, 23)

    msg = await ctx.send(f"🃏 **Blackjack!**\nYour total: {player_total}\nDealer total: ???\nType `.hit` or `.stand`.")

    def check(m):
        return m.author == ctx.author and m.content.lower() in [".hit", ".stand"]

    try:
        response = await bot.wait_for("message", check=check, timeout=30)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Time’s up! You stood automatically.")
        response = None

    if not response or response.content.lower() == ".stand":
        dealer_total = random.randint(17, 23)
    elif response.content.lower() == ".hit":
        player_total += random.randint(1, 10)

    if player_total > 21:
        update_balance(ctx.author.id, -bet)
        result = f"💥 You busted with {player_total}! Lost {bet} coins."
    elif dealer_total > 21 or player_total > dealer_total:
        update_balance(ctx.author.id, bet)
        result = f"🏆 You won! Dealer had {dealer_total}. You gained {bet} coins."
    elif player_total == dealer_total:
        result = f"🤝 Draw! Dealer had {dealer_total}. Your coins stay the same."
    else:
        update_balance(ctx.author.id, -bet)
        result = f"😢 Dealer wins with {dealer_total}. You lost {bet} coins."

    await ctx.send(result)

@bot.command()
async def coinflip(ctx, bet: int):
    bal = get_balance(ctx.author.id)
    if bal < bet:
        await ctx.send("❌ Not enough coins.")
        return

    await ctx.send("🪙 Type `.heads` or `.tails` to flip the coin!")

    def check(m):
        return m.author == ctx.author and m.content.lower() in [".heads", ".tails"]

    try:
        choice_msg = await bot.wait_for("message", check=check, timeout=20)
    except asyncio.TimeoutError:
        await ctx.send("⏰ You didn’t choose in time.")
        return

    user_choice = choice_msg.content.lower().replace(".", "")
    result = random.choice(["heads", "tails"])

    if user_choice == result:
        update_balance(ctx.author.id, bet)
        await ctx.send(f"🎯 It landed on **{result}**! You won {bet} coins.")
    else:
        update_balance(ctx.author.id, -bet)
        await ctx.send(f"😢 It landed on **{result}**. You lost {bet} coins.")

@bot.command()
async def deposite(ctx):
    links = (
        "**Deposit Options:**\n"
        "2 Robux → https://www.roblox.com/game-pass/1232154663/Ty\n"
        "5 Robux → https://www.roblox.com/game-pass/1499732227/Thank-you\n"
        "10 Robux → https://www.roblox.com/game-pass/1240990679/Thank-you , "
        "https://www.roblox.com/game-pass/1241552744/Thank-you\n"
        "20 Robux → https://www.roblox.com/game-pass/1243945119/Tysm , "
        "https://www.roblox.com/game-pass/1243945119/Tysm\n"
        "40 Robux → https://www.roblox.com/game-pass/1234374789/Thank-you\n"
        "50 Robux → https://www.roblox.com/game-pass/1234072595/Thank-you\n"
        "100 Robux → https://www.roblox.com/game-pass/1232068254/Thank-you\n"
        "200 Robux → https://www.roblox.com/game-pass/1259027259/Thank-you\n"
        "300 Robux → https://www.roblox.com/game-pass/1259205084/Thank-you\n"
        "700 Robux → https://www.roblox.com/game-pass/1225880673/Tysm\n"
        "1000 Robux → https://www.roblox.com/game-pass/1239121933/Tysmm\n"
    )
    await ctx.author.send(links)
    await ctx.send("📩 Check your DMs for deposite options!")

# --- RUN BOT ---
bot.run(TOKEN)
