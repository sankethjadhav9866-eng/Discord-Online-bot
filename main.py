import discord
from discord.ext import commands
import json, random, os, asyncio
from datetime import datetime, timedelta

# --- CONFIG ---
PREFIX = "."
OWNER_IDS = ["1405836534812508210", "1342508316911210551"]
DAILY_REWARD = 5
DATA_FILE = "vortex_data.json"

# --- INIT ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# --- DATA STORAGE ---
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"balances": {}, "daily": {}, "games": {}, "proofs": {}}

def save():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_balance(user_id):
    return data["balances"].get(str(user_id), 0)

def add_balance(user_id, amount):
    data["balances"][str(user_id)] = get_balance(user_id) + amount
    save()

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# --- BALANCE COMMANDS ---
@bot.command()
async def balance(ctx):
    bal = get_balance(ctx.author.id)
    await ctx.send(f"💰 {ctx.author.mention}, your balance is **{bal} coins**.")

@bot.command()
async def daily(ctx):
    user_id = str(ctx.author.id)
    now = datetime.now()
    last_claim = data["daily"].get(user_id)
    if last_claim and now - datetime.fromisoformat(last_claim) < timedelta(days=1):
        await ctx.send("⏳ You already claimed your daily reward today!")
        return
    add_balance(user_id, DAILY_REWARD)
    data["daily"][user_id] = now.isoformat()
    save()
    await ctx.send(f"🎁 {ctx.author.mention}, you received **{DAILY_REWARD} coins** today!")

# --- OPGIVE COMMAND ---
@bot.command()
async def opgive(ctx, member: discord.Member, amount: int):
    if str(ctx.author.id) not in OWNER_IDS:
        await ctx.send("🚫 You can’t use this command!")
        return
    add_balance(member.id, amount)
    await ctx.send(f"💎 Gave **{amount} coins** to {member.mention}.")

# --- BLACKJACK GAME ---
@bot.command()
async def blackjack(ctx, bet: int):
    if bet < 1 or get_balance(ctx.author.id) < bet:
        await ctx.send("❌ Invalid bet or insufficient balance!")
        return

    add_balance(ctx.author.id, -bet)
    player_cards = [random.randint(1, 11), random.randint(1, 11)]
    dealer_cards = [random.randint(1, 11), random.randint(1, 11)]
    await ctx.send(f"🃏 Your cards: {player_cards} (Total: {sum(player_cards)})\nType `.hit` or `.stand`.")

    def check(m):
        return m.author == ctx.author and m.content.lower() in [".hit", ".stand"]

    while True:
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("⏰ Game timed out!")
            return

        if msg.content.lower() == ".hit":
            card = random.randint(1, 11)
            player_cards.append(card)
            total = sum(player_cards)
            await ctx.send(f"🃏 Drew {card}. Total now **{total}**.")
            if total > 21:
                await ctx.send(f"💀 You busted! Lost {bet} coins.")
                return
        else:
            player_total = sum(player_cards)
            dealer_total = sum(dealer_cards)
            while dealer_total < 17:
                dealer_cards.append(random.randint(1, 11))
                dealer_total = sum(dealer_cards)

            await ctx.send(f"Dealer’s total: **{dealer_total}**")

            if dealer_total > 21 or player_total > dealer_total:
                winnings = bet * 2
                add_balance(ctx.author.id, winnings)
                await ctx.send(f"🎉 You won **{winnings} coins!**")
            elif dealer_total == player_total:
                add_balance(ctx.author.id, bet)
                await ctx.send("🤝 It’s a tie! Your bet was returned.")
            else:
                await ctx.send(f"💀 Dealer won! Lost **{bet} coins.**")
            return

# --- MINES GAME ---
@bot.command()
async def mines(ctx, bet: int):
    if bet < 1 or get_balance(ctx.author.id) < bet:
        await ctx.send("❌ Invalid bet or insufficient coins!")
        return

    add_balance(ctx.author.id, -bet)
    safe = random.sample(range(1, 26), 5)
    data["games"][str(ctx.author.id)] = {"bet": bet, "safe": safe, "picked": [], "reward": 0}
    save()
    await ctx.send("💣 Mines started! Pick 1–25 with `.pick <number>` or cashout with `.cashout`.")

@bot.command()
async def pick(ctx, number: int):
    user = str(ctx.author.id)
    game = data["games"].get(user)
    if not game:
        await ctx.send("❌ You aren’t in a game!")
        return
    if number in game["picked"]:
        await ctx.send("⚠️ Already picked!")
        return
    if number in game["safe"]:
        game["picked"].append(number)
        game["reward"] += 2
        save()
        await ctx.send(f"✅ Safe! +2 coins added. Total reward: **{game['reward']}** coins.")
    else:
        del data["games"][user]
        save()
        await ctx.send("💣 Boom! You lost the round.")

@bot.command()
async def cashout(ctx):
    user = str(ctx.author.id)
    game = data["games"].get(user)
    if not game:
        await ctx.send("❌ You have no active game!")
        return
    winnings = game["reward"]
    add_balance(user, winnings)
    del data["games"][user]
    save()
    await ctx.send(f"💰 You cashed out **{winnings} coins!**")

# --- DEPOSIT COMMAND ---
@bot.command()
async def deposit(ctx):
    msg = (
        "💸 **Deposit Options** 💸\n\n"
        "2 Robux → https://www.roblox.com/game-pass/1232154663/Ty\n"
        "5 Robux → https://www.roblox.com/game-pass/1499732227/Thank-you\n"
        "10 Robux → https://www.roblox.com/game-pass/1240990679/Thank-you, "
        "https://www.roblox.com/game-pass/1241552744/Thank-you\n"
        "20 Robux → https://www.roblox.com/game-pass/1243945119/Tysm\n"
        "40 Robux → https://www.roblox.com/game-pass/1234374789/Thank-you\n"
        "50 Robux → https://www.roblox.com/game-pass/1234072595/Thank-you\n"
        "100 Robux → https://www.roblox.com/game-pass/1232068254/Thank-you\n"
        "200 Robux → https://www.roblox.com/game-pass/1259027259/Thank-you\n"
        "300 Robux → https://www.roblox.com/game-pass/1259205084/Thank-you\n"
        "700 Robux → https://www.roblox.com/game-pass/1225880673/Tysm\n"
        "1000 Robux → https://www.roblox.com/game-pass/1239121933/Tysmm"
    )
    try:
        await ctx.author.send(msg)
        await ctx.send("📩 Check your DMs for deposit options!")
    except discord.Forbidden:
        await ctx.send("❌ I can’t DM you! Please enable DMs.")

# --- PURCHASE PROOF COMMANDS ---
@bot.command()
async def bought(ctx):
    await ctx.send("🧾 Please provide proof of purchase using `.boughtproof` and attach your screenshot!")

@bot.command()
async def boughtproof(ctx):
    if not ctx.message.attachments:
        await ctx.send("❌ You must attach a screenshot of your purchase!")
        return
    proof_url = ctx.message.attachments[0].url
    data["proofs"][str(ctx.author.id)] = proof_url
    save()
    await ctx.send(f"✅ Proof received from {ctx.author.mention}!")

# --- COINFLIP ---
@bot.command()
async def coinflip(ctx, bet: int):
    if bet < 1 or get_balance(ctx.author.id) < bet:
        await ctx.send("❌ Invalid bet or insufficient balance!")
        return

    add_balance(ctx.author.id, -bet)
    result = random.choice(["heads", "tails"])
    await ctx.send(f"🪙 Coin is flipping...")
    await asyncio.sleep(2)

    if random.choice([True, False]):
        winnings = bet * 2
        add_balance(ctx.author.id, winnings)
        await ctx.send(f"🎉 It landed on {result}! You won **{winnings} coins!**")
    else:
        await ctx.send(f"💀 It landed on {result}. You lost **{bet} coins.**")

# --- RUN BOT ---
bot.run(os.getenv("TOKEN"))
