import os
import json
import discord
import asyncio
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import random

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents)

DATA_FILE = "users.json"
GAME_CHANNEL_ID = 1234567890  # Thay bằng ID kênh game thật
ADMIN_ID = 1115314183731421274
BET_DURATION = 60  # thời gian mỗi phiên

users = {}
current_game = {"active": False}
bet_history = []

# ================== LOAD / SAVE ==================

def load_users():
    global users
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            users = json.load(f)

def save_users():
    with open(DATA_FILE, 'w') as f:
        json.dump(users, f)

# ================== GAME LOGIC ==================

def get_result():
    return random.choice(["tài", "xỉu"])

def get_cau_display():
    cau = bet_history[-8:]
    return "Cầu: " + " ".join("⚫" if res == "tài" else "⚪" for res in cau)

async def payout():
    total_tai = sum(u['bet'] for u in current_game['bets'] if u['choice'] == 'tài')
    total_xiu = sum(u['bet'] for u in current_game['bets'] if u['choice'] == 'xỉu')

    result = current_game.get("result") or get_result()
    current_game["result"] = result
    bet_history.append(result)
    bet_history[:] = bet_history[-20:]

    winners = []
    losers = []
    tax_total = 0

    for bet in current_game['bets']:
        uid = bet['user']
        bet_amount = bet['bet']
        if uid not in users:
            continue
        if bet['choice'] == result:
            profit = int(bet_amount * 0.98)
            users[uid]["balance"] += bet_amount + profit
            tax_total += bet_amount - profit
            winners.append((uid, profit))
        else:
            losers.append(uid)

    if str(ADMIN_ID) in users:
        users[str(ADMIN_ID)]["balance"] += tax_total

    save_users()

    return result, winners, losers

# ================== COMMANDS ==================

@bot.event
async def on_ready():
    print(f"Bot đã đăng nhập với tên {bot.user}")
    load_users()

@bot.command()
async def game(ctx):
    if ctx.author.id != ADMIN_ID:
        return

    if current_game["active"]:
        await ctx.send("Phiên đang diễn ra.")
        return

    current_game.update({"active": True, "bets": [], "result": None})
    await send_game_message(ctx)

    await asyncio.sleep(BET_DURATION)

    if not current_game.get("result"):
        current_game["result"] = get_result()

    result, winners, losers = await payout()

    desc = f"Kết quả: **{result.upper()}** 🎲\n"
    desc += f"Thắng: {', '.join([f'<@{uid}> (+{amt})' for uid, amt in winners])}\n"
    desc += f"Thua: {', '.join([f'<@{uid}>' for uid in losers])}" if losers else ""

    embed = discord.Embed(title="✅ Kết thúc phiên", description=desc, color=0x00ff00)
    embed.set_footer(text=get_cau_display())

    await ctx.send(embed=embed)
    current_game["active"] = False

@bot.command()
async def tai(ctx):
    await handle_bet(ctx, "tài")

@bot.command()
async def xiu(ctx):
    await handle_bet(ctx, "xỉu")

async def handle_bet(ctx, choice):
    user_id = str(ctx.author.id)
    if not current_game.get("active"):
        await ctx.send("Chưa có phiên nào diễn ra. Admin hãy dùng `.game` để bắt đầu.")
        return

    if user_id not in users:
        users[user_id] = {"balance": 10000}

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    await ctx.send(f"{ctx.author.mention}, nhập số tiền cược ({choice.upper()}):")

    try:
        msg = await bot.wait_for("message", timeout=20, check=check)
        bet_amount = int(msg.content.replace("k", "000").lower())
        if bet_amount > users[user_id]["balance"]:
            await ctx.send("❌ Không đủ xu.")
            return

        users[user_id]["balance"] -= bet_amount
        current_game["bets"].append({"user": user_id, "choice": choice, "bet": bet_amount})
        save_users()
        await ctx.send(f"✅ {ctx.author.mention} đã cược {bet_amount} vào **{choice.upper()}**.")
    except asyncio.TimeoutError:
        await ctx.send("⏰ Hết thời gian nhập số tiền.")

async def send_game_message(ctx):
    total_tai = sum(b['bet'] for b in current_game["bets"] if b["choice"] == "tài")
    total_xiu = sum(b['bet'] for b in current_game["bets"] if b["choice"] == "xỉu")
    count_tai = sum(1 for b in current_game["bets"] if b["choice"] == "tài")
    count_xiu = sum(1 for b in current_game["bets"] if b["choice"] == "xỉu")

    embed = discord.Embed(
        title="🎲 Mini game Tài Xỉu",
        description=(
            f"Chọn cược bằng `.tai` hoặc `.xiu`\n"
            f"⏱️ Thời gian cược: {BET_DURATION} giây\n\n"
            f"**Số người cược Tài:** {count_tai} | 💰 Tổng: {total_tai}\n"
            f"**Số người cược Xỉu:** {count_xiu} | 💰 Tổng: {total_xiu}\n"
        ),
        color=0x00ffff,
    )
    embed.set_footer(text=get_cau_display())
    await ctx.send(embed=embed)

@bot.command()
async def stk(ctx):
    user_id = str(ctx.author.id)
    if user_id not in users:
        users[user_id] = {"balance": 10000}
    await ctx.send(f"💰 {ctx.author.mention} Số dư: {users[user_id]['balance']} xu")

@bot.command()
async def daily(ctx):
    user_id = str(ctx.author.id)
    if user_id not in users:
        users[user_id] = {"balance": 10000, "last_daily": "2000-01-01"}
    now = datetime.now()
    last_claim = users[user_id].get("last_daily", "2000-01-01")
    last_time = datetime.strptime(last_claim, "%Y-%m-%d")

    if now.date() > last_time.date():
        users[user_id]["balance"] += 5000
        users[user_id]["last_daily"] = now.strftime("%Y-%m-%d")
        save_users()
        await ctx.send(f"✅ {ctx.author.mention} đã nhận 5.000 xu mỗi ngày.")
    else:
        await ctx.send(f"⏳ {ctx.author.mention} bạn đã nhận hôm nay rồi, quay lại ngày mai.")

@bot.command()
async def addmoney(ctx, member: discord.Member, amount: int):
    if ctx.author.id != ADMIN_ID:
        return
    uid = str(member.id)
    if uid not in users:
        users[uid] = {"balance": 10000}
    users[uid]["balance"] += amount
    save_users()
    await ctx.send(f"✅ Đã cộng {amount} xu cho {member.mention}")

@bot.command()
async def give(ctx, member: discord.Member, amount: int):
    uid_sender = str(ctx.author.id)
    uid_recv = str(member.id)
    if uid_sender not in users or users[uid_sender]["balance"] < amount:
        await ctx.send("❌ Không đủ xu để chuyển.")
        return
    if uid_recv not in users:
        users[uid_recv] = {"balance": 10000}
    users[uid_sender]["balance"] -= amount
    users[uid_recv]["balance"] += amount
    save_users()
    await ctx.send(f"✅ {ctx.author.mention} đã chuyển {amount} xu cho {member.mention}.")

@bot.command()
async def off(ctx):
    if ctx.author.id != ADMIN_ID:
        return
    current_game["active"] = False
    await ctx.send("🛑 Game đã bị tắt bởi admin.")

# ================== START BOT ==================

TOKEN = os.environ.get("TOKEN")
bot.run(TOKEN)
