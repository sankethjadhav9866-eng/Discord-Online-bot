
import os
import random
import json
import sqlite3
import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands

# ------------- CONFIG -------------
PREFIX = "."
OWNER_IDS = ["1405836534812508210", "1342508316911210551"]  # owner IDs as strings
DB_FILE = "vortex.db"
DAILY_REWARD = 5
TOKEN = os.getenv("TOKEN")  # <- set this in your host env, do NOT hardcode

# ------------- INTENTS & BOT -------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ------------- DATABASE -------------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS balances (user_id TEXT PRIMARY KEY, balance INTEGER)""")
c.execute("""CREATE TABLE IF NOT EXISTS daily (user_id TEXT PRIMARY KEY, last_claim TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS games (user_id TEXT PRIMARY KEY, type TEXT, data TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS deposits (user_id TEXT PRIMARY KEY, used INTEGER)""")
c.execute("""CREATE TABLE IF NOT EXISTS proofs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, amount INTEGER, attachments TEXT, ts TEXT)""")
conn.commit()

# ------------- DB HELPERS -------------
def get_balance_db(user_id):
    c.execute("SELECT balance FROM balances WHERE user_id = ?", (str(user_id),))
    row = c.fetchone()
    return row[0] if row else 0

def set_balance_db(user_id, amount):
    c.execute("INSERT OR REPLACE INTO balances (user_id, balance) VALUES (?,?)", (str(user_id), int(amount)))
    conn.commit()

def add_balance_db(user_id, amount):
    current = get_balance_db(user_id) or 0
    set_balance_db(user_id, current + int(amount))

def get_daily(user_id):
    c.execute("SELECT last_claim FROM daily WHERE user_id = ?", (str(user_id),))
    r = c.fetchone()
    return r[0] if r else None

def set_daily(user_id, iso_ts):
    c.execute("INSERT OR REPLACE INTO daily (user_id, last_claim) VALUES (?,?)", (str(user_id), iso_ts))
    conn.commit()

def set_game(user_id, gtype, data_dict):
    c.execute("INSERT OR REPLACE INTO games (user_id, type, data) VALUES (?, ?, ?)",
              (str(user_id), gtype, json.dumps(data_dict)))
    conn.commit()

def get_game(user_id):
    c.execute("SELECT type, data FROM games WHERE user_id = ?", (str(user_id),))
    r = c.fetchone()
    if not r:
        return None
    return {"type": r[0], "data": json.loads(r[1])}

def del_game(user_id):
    c.execute("DELETE FROM games WHERE user_id = ?", (str(user_id),))
    conn.commit()

def mark_deposit_used(user_id):
    c.execute("INSERT OR REPLACE INTO deposits (user_id, used) VALUES (?, 1)", (str(user_id),))
    conn.commit()

def get_deposits_list():
    c.execute("SELECT user_id FROM deposits WHERE used = 1")
    return [r[0] for r in c.fetchall()]

def log_proof(user_id, amount, attachments):
    ts = datetime.utcnow().isoformat()
    c.execute("INSERT INTO proofs (user_id, amount, attachments, ts) VALUES (?, ?, ?, ?)",
              (str(user_id), int(amount), json.dumps(attachments), ts))
    conn.commit()

# ------------- ANTI-DUPLICATE / RATE GUARD -------------
# per-user-per-command small debounce (seconds)
_last_invocations = {}  # key: (user_id, command_name) -> timestamp

def called_recently(user_id, cmd_name, cooldown_s=1.0):
    key = (str(user_id), cmd_name)
    now = asyncio.get_event_loop().time()
    last = _last_invocations.get(key)
    if last and (now - last) < cooldown_s:
        return True
    _last_invocations[key] = now
    return False

# ------------- EVENTS -------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("Make sure only ONE instance is running to avoid duplicate triggers.")

# ignore messages from bots (prevents loops)
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

# ------------- COMMANDS -------------
# BALANCE
@bot.command()
async def balance(ctx):
    if called_recently(ctx.author.id, "balance"): return
    bal = get_balance_db(ctx.author.id)
    await ctx.send(f"💰 {ctx.author.mention}, your balance is **{bal} coins**.")

# DAILY
@bot.command()
async def daily(ctx):
    if called_recently(ctx.author.id, "daily"): return
    uid = str(ctx.author.id)
    last = get_daily(uid)
    now = datetime.utcnow()
    if last:
        last_dt = datetime.fromisoformat(last)
        if now - last_dt < timedelta(days=1):
            return await ctx.send("⏳ You already claimed daily reward!")
    add_balance_db(uid, DAILY_REWARD)
    set_daily(uid, now.isoformat())
    await ctx.send(f"🎁 {ctx.author.mention} — you received **{DAILY_REWARD} coins**!")

# TIP
@bot.command()
async def tip(ctx, member: discord.Member, amount: int):
    if called_recently(ctx.author.id, "tip"): return
    if amount < 1:
        return await ctx.send("❌ Minimum tip is 1 coin.")
    sender = str(ctx.author.id)
    if get_balance_db(sender) < amount:
        return await ctx.send("❌ You don't have enough coins!")
    add_balance_db(sender, -amount)
    add_balance_db(member.id, amount)
    await ctx.send(f"🤝 {ctx.author.mention} tipped {member.mention} **{amount} coins**!")

# OPGIVE (owner only)
@bot.command(name="opgive")
async def opgive(ctx, member: discord.Member, amount: int):
    if called_recently(ctx.author.id, "opgive"): return
    if str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send("🚫 You don't have permission to use this command.")
    if amount <= 0:
        return await ctx.send("❌ Amount must be positive.")
    # single add, safe via DB
    add_balance_db(member.id, amount)
    await ctx.send(f"💎 Gave {member.mention} **{amount} coins**.")

# BLACKJACK (.hit / .stand via messages)
@bot.command()
async def blackjack(ctx, bet: int):
    if called_recently(ctx.author.id, "blackjack"): return
    uid = str(ctx.author.id)
    if bet < 1 or get_balance_db(uid) < bet:
        return await ctx.send("❌ Invalid bet or insufficient balance.")
    add_balance_db(uid, -bet)
    player = [random.randint(1,11), random.randint(1,11)]
    dealer = [random.randint(1,11), random.randint(1,11)]

    def total(hand):
        t = sum(hand)
        while t > 21 and 11 in hand:
            hand[hand.index(11)] = 1
            t = sum(hand)
        return t

    await ctx.send(f"🃏 Your cards: {player} (Total: {total(player)})\nDealer shows: {dealer[0]} + ?\nType `.hit` to draw or `.stand` to stop.")

    def check(m):
        return m.author == ctx.author and m.content.lower() in [".hit", ".stand"]

    while True:
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            add_balance_db(uid, bet)  # refund on timeout
            return await ctx.send("⏰ Time's up — game cancelled, bet refunded.")
        if msg.content.lower() == ".hit":
            card = random.randint(1,11)
            player.append(card)
            t = total(player)
            if t > 21:
                return await ctx.send(f"🃏 You drew {card}. Total {t}. 💥 Busted! You lost {bet} coins.")
            else:
                await ctx.send(f"🃏 You drew {card}. Total now {t}. Type `.hit` or `.stand`.")
        else:
            pt = total(player)
            dt = total(dealer)
            while dt < 17:
                dealer.append(random.randint(1,11))
                dt = total(dealer)
            await ctx.send(f"Dealer: {dealer} (Total: {dt})")
            if dt > 21 or pt > dt:
                winnings = bet * 2
                add_balance_db(uid, winnings)
                await ctx.send(f"🎉 You won {winnings} coins!")
            elif pt == dt:
                add_balance_db(uid, bet)
                await ctx.send("🤝 It's a tie — bet returned.")
            else:
                await ctx.send(f"💀 Dealer won — you lost {bet} coins.")
            return

# MINES
@bot.command()
async def mines(ctx, bet: int):
    if called_recently(ctx.author.id, "mines"): return
    uid = str(ctx.author.id)
    if bet < 1 or get_balance_db(uid) < bet:
        return await ctx.send("❌ Invalid bet or insufficient balance.")
    add_balance_db(uid, -bet)
    safe = random.sample(range(1,26), 5)
    game = {"bet": bet, "safe": safe, "picked": [], "safe_picks": 0}
    set_game(uid, "mines", game)
    await ctx.send("💣 Mines started! Pick squares 1–25 using `.pick <number>`. Cashout with `.cashout`. Each safe pick gives +2 coins instantly.")

@bot.command()
async def pick(ctx, number: int):
    if called_recently(ctx.author.id, "pick"): return
    uid = str(ctx.author.id)
    g = get_game(uid)
    if not g or g["type"] != "mines":
        return await ctx.send("❌ You're not in a mines game.")
    game = g["data"]
    if number in game["picked"]:
        return await ctx.send("⚠️ Already picked that number.")
    if number in game["safe"]:
        game["picked"].append(number)
        game["safe_picks"] += 1
        add_balance_db(uid, 2)
        set_game(uid, "mines", game)
        await ctx.send(f"✅ Safe! +2 coins. Safe picks: {game['safe_picks']}.")
    else:
        del_game(uid)
        await ctx.send("💣 Boom! You hit a mine and lost your bet.")

@bot.command()
async def cashout(ctx):
    if called_recently(ctx.author.id, "cashout"): return
    uid = str(ctx.author.id)
    g = get_game(uid)
    if not g or g["type"] != "mines":
        return await ctx.send("❌ You have no active mines game.")
    game = g["data"]
    winnings = game["bet"] + (2 * game["safe_picks"])
    add_balance_db(uid, winnings)
    del_game(uid)
    await ctx.send(f"💰 You cashed out {winnings} coins! Balance: {get_balance_db(uid)}")

# DEPOSIT & PROOF FLOW
@bot.command()
async def deposit(ctx):
    if called_recently(ctx.author.id, "deposit"): return
    dm_text = (
        "**💸 Robux Deposit Options**\n\n"
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
        "1000 Robux – https://www.roblox.com/game-pass/1239121933/Tysmm\n\n"
        "After buying, run `.bought <amount>` in server and then attach proof with `.boughtproof`."
    )
    try:
        await ctx.author.send(dm_text)
        await ctx.send("📩 Check your DMs — deposit links sent!")
        mark_deposit_used(ctx.author.id)
    except discord.Forbidden:
        await ctx.send("❌ I can't DM you — enable DMs and try again.")

@bot.command()
async def bought(ctx, amount: int):
    if called_recently(ctx.author.id, "bought"): return
    ts = datetime.utcnow().isoformat()
    c.execute("INSERT INTO proofs (user_id, amount, attachments, ts) VALUES (?, ?, ?, ?)",
              (str(ctx.author.id), int(amount), json.dumps([]), ts))
    conn.commit()
    await ctx.send("ℹ️ Please provide proof of your purchase using `.boughtproof` and attach your screenshot(s).")

@bot.command()
async def boughtproof(ctx):
    if called_recently(ctx.author.id, "boughtproof"): return
    # find last pending proof
    c.execute("SELECT id, amount FROM proofs WHERE user_id = ? AND attachments = ? ORDER BY id DESC LIMIT 1",
              (str(ctx.author.id), json.dumps([])))
    row = c.fetchone()
    if not row:
        return await ctx.send("❌ No pending purchase found. First run `.bought <amount>`.")
    proof_id, amount = row
    if not ctx.message.attachments:
        return await ctx.send("❌ Please attach screenshot(s) with `.boughtproof`.")
    attachments = [a.url for a in ctx.message.attachments]
    c.execute("UPDATE proofs SET attachments = ? WHERE id = ?", (json.dumps(attachments), proof_id))
    conn.commit()
    log_proof(ctx.author.id, amount, attachments)
    # notify owners
    for owner in OWNER_IDS:
        try:
            user = await bot.fetch_user(int(owner))
            embed = discord.Embed(title="Purchase Proof Received", color=0x00FF00, timestamp=datetime.utcnow())
            embed.add_field(name="User", value=f"{ctx.author} ({ctx.author.id})", inline=False)
            embed.add_field(name="Amount", value=str(amount), inline=False)
            embed.add_field(name="Time (UTC)", value=datetime.utcnow().isoformat(), inline=False)
            await user.send(embed=embed)
            for url in attachments:
                await user.send(url)
        except discord.Forbidden:
            pass
    await ctx.send("✅ Proof submitted — owners have been notified.")

@bot.command()
async def depositslist(ctx):
    if str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send("🚫 You don't have permission to view deposits.")
    deposits = get_deposits_list()
    if not deposits:
        return await ctx.send("📂 No deposits recorded.")
    lines = [f"<@{uid}>" for uid in deposits]
    await ctx.send("💰 Users who used `.deposit`:\n" + "\n".join(lines))

# COINFLIP (main + shortcuts)
async def do_coinflip(ctx, bet: int, guess: str):
    uid = str(ctx.author.id)
    if bet < 1 or get_balance_db(uid) < bet:
        return await ctx.send("❌ Invalid bet or insufficient balance.")
    add_balance_db(uid, -bet)
    result = random.choice(["heads", "tails"])
    await ctx.send("🪙 Flipping the coin...")
    await asyncio.sleep(1.2)
    await ctx.send(f"Result: **{result}**")
    if guess.lower() == result:
        winnings = bet * 2
        add_balance_db(uid, winnings)
        await ctx.send(f"🎉 You won **{winnings} coins!**")
    else:
        await ctx.send(f"💀 You lost **{bet} coins.**")

@bot.command()
async def coinflip(ctx, bet: int, guess: str):
    if called_recently(ctx.author.id, "coinflip"): return
    if guess.lower() not in ["heads", "tails"]:
        return await ctx.send("❌ Guess must be `heads` or `tails`.")
    await do_coinflip(ctx, bet, guess)

# ------------- RUN -------------
if TOKEN is None:
    print("⚠️ TOKEN environment variable is not set. Set TOKEN before running.")
else:
    bot.run(TOKEN)
async def heads(ctx, bet: int):
    if called_recently(ctx.author.id, "heads"): return
    await do_coinflip(ctx, bet, "heads")

@bot.command()
async def tails(ctx, bet: int):
    if called_recently(ctx.author.id, "tails"): return
    await do_coinflip(ctx, bet, "tails")

# ------------- RUN -------------
    bot.run(TOKEN)
