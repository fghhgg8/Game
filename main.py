import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import asyncio
import random
from datetime import datetime, timedelta
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='.', intents=intents)

ADMIN_ID = 1115314183731421274
GAME_CHANNEL_ID = 1398174558468706454

user_balances = {}  # {user_id: balance}
user_bets = {}       # {user_id: {"side": "tai"/"xiu", "amount": int}}
betting_open = False
game_result = None
history = []
admin_forced_result = None

# ======================= HỖ TRỢ =========================

def get_balance(user_id):
    return user_balances.get(user_id, 10000)

def update_balance(user_id, amount):
    user_balances[user_id] = get_balance(user_id) + amount

def render_history():
    return " ".join(["🔴" if h == "tai" else "⚪" for h in history[-8:]])

# ======================= GAME =========================

@bot.command()
async def start(ctx):
    if ctx.author.id != ADMIN_ID:
        return
    await run_game_loop()

async def run_game_loop():
    global betting_open, user_bets, game_result

    channel = bot.get_channel(GAME_CHANNEL_ID)
    if not channel:
        print("Không tìm thấy kênh.")
        return

    while True:
        user_bets.clear()
        betting_open = True

        embed = discord.Embed(title="🎲 PHIÊN MỚI", description="Bạn có 30s để đặt cược!", color=0x00ffcc)
        embed.add_field(name="⭕ Cầu gần đây", value=render_history() or "Chưa có", inline=False)

        view = BettingView()
        await channel.send(embed=embed, view=view)

        await asyncio.sleep(30)
        betting_open = False

        await asyncio.sleep(2)

        # Kết quả
        if admin_forced_result:
            result = admin_forced_result
        else:
            result = random.choice(["tai", "xiu"])
        game_result = result
        history.append(result)
        if len(history) > 8:
            history.pop(0)

        winners = [uid for uid, v in user_bets.items() if v["side"] == result]
        losers = [uid for uid, v in user_bets.items() if v["side"] != result]

        for uid in winners:
            bet = user_bets[uid]["amount"]
            win = int(bet * 2 * 0.98)  # thuế 2%
            update_balance(uid, win)

        msg = f"KẾT QUẢ: **{result.upper()}**\n"
        msg += f"✅ {len(winners)} người thắng\n❌ {len(losers)} người thua"

        await channel.send(msg)
        await asyncio.sleep(5)

# =================== VIEW ====================

class BettingView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cược Tài", style=discord.ButtonStyle.success, custom_id="bet_tai")
    async def bet_tai(self, interaction: discord.Interaction, button: Button):
        await handle_bet(interaction, "tai")

    @discord.ui.button(label="Cược Xỉu", style=discord.ButtonStyle.danger, custom_id="bet_xiu")
    async def bet_xiu(self, interaction: discord.Interaction, button: Button):
        await handle_bet(interaction, "xiu")

async def handle_bet(interaction: discord.Interaction, side):
    global betting_open
    if not betting_open:
        await interaction.response.send_message("❌ Phiên đã kết thúc!", ephemeral=True)
        return

    user_id = interaction.user.id
    balance = get_balance(user_id)

    await interaction.response.send_message(
        f"💰 Nhập số tiền cược (số xu bạn đang có: {balance:,}):", ephemeral=True)

    def check(m):
        return m.author.id == user_id and m.channel == interaction.channel

    try:
        msg = await bot.wait_for("message", timeout=15, check=check)
        try:
            amount = int(str(msg.content).lower().replace("k", "000"))
        except:
            await interaction.followup.send("❌ Số tiền không hợp lệ.", ephemeral=True)
            return

        if amount <= 0 or amount > balance:
            await interaction.followup.send("❌ Bạn không đủ xu hoặc số tiền không hợp lệ.", ephemeral=True)
            return

        user_bets[user_id] = {"side": side, "amount": amount}
        update_balance(user_id, -amount)
        await interaction.followup.send(f"✅ Bạn đã cược {amount:,} xu vào **{side.upper()}**!", ephemeral=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("⏰ Hết thời gian nhập cược.", ephemeral=True)

# =================== TIỆN ÍCH ====================

@bot.command()
async def balance(ctx):
    bal = get_balance(ctx.author.id)
    await ctx.send(f"💰 Số dư của bạn là **{bal:,} xu**")

@bot.command()
async def force(ctx, result):
    global admin_forced_result
    if ctx.author.id != ADMIN_ID:
        return
    if result.lower() not in ["tai", "xiu"]:
        await ctx.send("Chỉ có thể ép 'tai' hoặc 'xiu'")
        return
    admin_forced_result = result.lower()
    await ctx.send(f"✅ Đã ép kết quả phiên sau là **{admin_forced_result.upper()}**")

@bot.command()
async def unforce(ctx):
    global admin_forced_result
    if ctx.author.id != ADMIN_ID:
        return
    admin_forced_result = None
    await ctx.send("❌ Đã hủy ép kết quả.")

# =================== CHẠY BOT ====================

bot.run(os.getenv("DISCORD_TOKEN"))
