# main.py
import discord
from discord.ext import commands
import os, random, json, sqlite3, asyncio
from datetime import datetime, timedelta

# --- CONFIG ---
PREFIX = "."
OWNER_IDS = ["1405836534812508210", "1342508316911210551"]  # owners
DAILY_REWARD = 5
DB_FILE = "vortex.db"
TOKEN = os.getenv("TOKEN")

# --- INTENTS & BOT ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# --- DATABASE SETUP ---
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS balances (user_id TEXT PRIMARY KEY, balance INTEGER)""")
c.execute("""CREATE TABLE IF NOT EXISTS daily (user_id TEXT PRIMARY KEY, last_claim TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS games (user_id TEXT PRIMARY KEY, type TEXT, data TEXT)""")
c.execute("""CREATE TABLE IF NOT EXISTS deposits (user_id TEXT PRIMARY KEY, used INTEGER)""")
c.execute("""CREATE TABLE IF NOT EXISTS proofs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, amount INTEGER, attachments TEXT, ts TEXT)""")
conn.commit()

# --- DB HELPERS ---
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
              (str(user_id), amount, json.dumps(attachments), ts))
    conn.commit()

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# --- COMMANDS ---

@bot.command()
async def balance(ctx):
    bal = get_balance_db(ctx.author.id)
    await ctx.send(f"💰 {ctx.author.mention}, your balance is **{bal} coins**.")

@bot.command()
async def daily(ctx):
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

@bot.command()
async def tip(ctx, member: discord.Member, amount: int):
    if amount < 1:
        return await ctx.send("❌ Minimum tip is 1 coin.")
    sender = str(ctx.author.id)
    if get_balance_db(sender) < amount:
        return await ctx.send("❌ You don't have enough coins!")
    add_balance_db(sender, -amount)
    add_balance_db(member.id, amount)
    await ctx.send(f"🤝 {ctx.author.mention} tipped {member.mention} **{amount} coins**!")

@bot.command()
async def opgive(ctx, member: discord.Member, amount: int):
    if str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send("🚫 You don't have permission to use this command.")
    add_balance_db(member.id, amount)
    await ctx.send(f"💎 Gave {member.mention} **{amount} coins**.")

# --- BLACKJACK ---
@bot.command()
async def blackjack(ctx, bet: int):
    uid = str(ctx.author.id)
    if bet < 1 or get_balance_db(uid) < bet:
        return await ctx.send("❌ Invalid bet or insufficient balance.")
    add_balance_db(uid, -bet)
    player = [random.randint(1,11), random.randint(1,11)]
    dealer = [random.randint(1,11), random.randint(1,11)]

    async def total(hand):
        t = sum(hand)
        # adjust for aces (11 -> 1)
        while t > 21 and 11 in hand:
            hand[hand.index(11)] = 1
            t = sum(hand)
        return t

    await ctx.send(f"🃏 Your cards: {player} (Total: {await total(player)})\nDealer shows: {dealer[0]} + ?\nType `.hit` or `.stand`.")

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
            t = await total(player)
            if t > 21:
                return await ctx.send(f"🃏 You drew {card}. Total {t}. 💥 Busted! You lost {bet} coins.")
            else:
                await ctx.send(f"🃏 You drew {card}. Total now {t}. Type `.hit` or `.stand`.")
        else:  # stand
            pt = await total(player)
            dt = await total(dealer)
            while dt < 17:
                dealer.append(random.randint(1,11))
                dt = await total(dealer)
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

# --- MINES ---
@bot.command()
async def mines(ctx, bet: int):
    uid = str(ctx.author.id)
    if bet < 1 or get_balance_db(uid) < bet:
        return await ctx.send("❌ Invalid bet or insufficient balance.")
    add_balance_db(uid, -bet)
    safe = random.sample(range(1,26), 5)
    game = {"bet": bet, "safe": safe, "picked": [], "safe_picks": 0}
    set_game(uid, "mines", game)
    await ctx.send("💣 Mines started! Pick squares 1–25 using `.pick <number>`. Cashout anytime with `.cashout`. Each safe pick gives +2 coins immediately.")

@bot.command()
async def pick(ctx, number: int):
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
        add_balance_db(uid, 2)  # +2 coins instantly
        set_game(uid, "mines", game)
        await ctx.send(f"✅ Safe! +2 coins. Safe picks: {game['safe_picks']}.")
    else:
        del_game(uid)
        await ctx.send("💣 Boom! You hit a mine and lost your bet.")

@bot.command()
async def cashout(ctx):
    uid = str(ctx.author.id)
    g = get_game(uid)
    if not g or g["type"] != "mines":
        return await ctx.send("❌ You have no active mines game.")
    game = g["data"]
    winnings = game["bet"] + (2 * game["safe_picks"])  # original bet is not returned earlier; we gave +2 per safe pick already
    add_balance_db(uid, winnings)
    del_game(uid)
    await ctx.send(f"💰 You cashed out {winnings} coins! Current balance: {get_balance_db(uid)}")

# --- DEPOSIT & PROOF FLOW ---
@bot.command()
async def deposit(ctx):
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
    # create pending proof entry (attachments empty for now)
    ts = datetime.utcnow().isoformat()
    c.execute("INSERT INTO proofs (user_id, amount, attachments, ts) VALUES (?, ?, ?, ?)",
              (str(ctx.author.id), int(amount), json.dumps([]), ts))
    conn.commit()
    await ctx.send("ℹ️ Please provide proof of your purchase using `.boughtproof` and attach your screenshot(s).")

@bot.command()
async def boughtproof(ctx):
    # look for most recent pending proof for this user with empty attachments
    c.execute("SELECT id, amount FROM proofs WHERE user_id = ? AND attachments = ? ORDER BY id DESC LIMIT 1", (str(ctx.author.id), json.dumps([])))
    row = c.fetchone()
    if not row:
        return await ctx.send("❌ No pending purchase found. First run `.bought <amount>`.")
    proof_id, amount = row
    if not ctx.message.attachments:
        return await ctx.send("❌ Please attach your screenshot(s) with `.boughtproof`.")
    attachments = [a.url for a in ctx.message.attachments]
    c.execute("UPDATE proofs SET attachments = ? WHERE id = ?", (json.dumps(attachments), proof_id))
    conn.commit()
    # notify owners with embed + attachments
    for owner in OWNER_IDS:
        try:
            user = await bot.fetch_user(int(owner))
            embed = discord.Embed(title="Purchase Proof Received", color=0x00FF00)
            embed.add_field(name="User", value=f"{ctx.author} ({ctx.author.id})", inline=False)
            embed.add_field(name="Amount", value=str(amount), inline=False)
            embed.add_field(name="Time (UTC)", value=datetime.utcnow().isoformat(), inline=False)
            embed.set_footer(text="Use .opgive <user> <amount> to reward after verification")
            await user.send(embed=embed)
            for url in attachments:
                await user.send(url)
        except discord.Forbidden:
            # owner can't be DM'd — skip
            pass
    await ctx.send("✅ Proof submitted! Owners have been notified.")

@bot.command()
async def depositslist(ctx):
    if str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send("🚫 You don't have permission to view deposits.")
    deposits = get_deposits_list()
    if not deposits:
        return await ctx.send("📂 No deposits recorded.")
    lines = [f"<@{uid}>" for uid in deposits]
    chunked = "\n".join(lines)
    await ctx.send(f"💰 Users who used `.deposit`:\n{chunked}")

# --- COINFLIP (supports .coinflip <bet> <heads/tails> and shortcuts) ---
async def do_coinflip(ctx, bet, guess):
    uid = str(ctx.author.id)
    if bet < 1 or get_balance_db(uid) < bet:
        return await ctx.send("❌ Invalid bet or insufficient balance.")
    # take bet
    add_balance_db(uid, -bet)
    result = random.choice(["heads", "tails"])
    await ctx.send("🪙 Flipping the coin...")
    await asyncio.sleep(1.5)
    await ctx.send(f"Result: **{result}**")
    if guess.lower() == result:
        winnings = bet * 2
        add_balance_db(uid, winnings)
        await ctx.send(f"🎉 You guessed correctly and won **{winnings} coins!**")
    else:
        await ctx.send(f"💀 You guessed wrong — you lost **{bet} coins.**")

@bot.command()
async def coinflip(ctx, bet: int, guess: str):
    if guess.lower() not in ["heads", "tails"]:
        return await ctx.send("❌ Guess must be `heads` or `tails`.")
    await do_coinflip(ctx, bet, guess)

@bot.command()
async def heads(ctx, bet: int):
    await do_coinflip(ctx, bet, "heads")

@bot.command()
async def tails(ctx, bet: int):
    await do_coinflip(ctx, bet, "tails")

# --- RUN ---
if TOKEN is None:
    print("⚠️ TOKEN not set. Set TOKEN environment variable in your host.")
else:
    bot.run(TOKEN)
