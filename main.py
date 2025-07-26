import os
import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Button
from datetime import datetime
import random
import json

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='.', intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ID = 1115314183731421274
THUE = 0.02
TIEN_MOI = 10000
TIEN_DAILY = 5000
LICH_SU_CAU = []
CUOC_HIEN_TAI = {}
CHO_PHEP_DAT_CUOC = False
DANG_CHO_KET_QUA = False
GAME_DANG_CHAY = False
VI_ADMIN = 0

# ======================= DATABASE =========================

if not os.path.exists("data"):
    os.mkdir("data")
USERS_FILE = "data/users.json"
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)

def load_users():
    with open(USERS_FILE) as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def get_balance(user_id):
    users = load_users()
    if str(user_id) not in users:
        users[str(user_id)] = {"balance": TIEN_MOI, "last_daily": ""}
        save_users(users)
    return users[str(user_id)]["balance"]

def update_balance(user_id, amount):
    users = load_users()
    if str(user_id) not in users:
        users[str(user_id)] = {"balance": TIEN_MOI, "last_daily": ""}
    users[str(user_id)]["balance"] += amount
    save_users(users)

def set_last_daily(user_id):
    users = load_users()
    if str(user_id) not in users:
        users[str(user_id)] = {"balance": TIEN_MOI, "last_daily": ""}
    users[str(user_id)]["last_daily"] = datetime.now().strftime("%Y-%m-%d")
    save_users(users)

def can_claim_daily(user_id):
    users = load_users()
    last = users.get(str(user_id), {}).get("last_daily", "")
    return last != datetime.now().strftime("%Y-%m-%d")

# ======================= LỆNH =============================

@bot.command()
async def game(ctx):
    global GAME_DANG_CHAY
    if GAME_DANG_CHAY:
        await ctx.send("Game đang chạy rồi.")
        return
    GAME_DANG_CHAY = True
    await start_game_loop(ctx.channel)

@bot.command()
async def off(ctx):
    global GAME_DANG_CHAY
    if ctx.author.id != ADMIN_ID:
        return
    GAME_DANG_CHAY = False
    await ctx.send("❌ Game đã tắt.")

@bot.command()
async def stk(ctx):
    balance = get_balance(ctx.author.id)
    await ctx.send(f"Số dư của bạn là **{balance:,} xu**")

@bot.command()
async def give(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send("Số tiền không hợp lệ.")
        return
    if get_balance(ctx.author.id) < amount:
        await ctx.send("Bạn không đủ tiền.")
        return
    update_balance(ctx.author.id, -amount)
    update_balance(member.id, amount)
    await ctx.send(f"✉️ Đã chuyển {amount:,} xu cho {member.mention}")

@bot.command()
async def addmoney(ctx, member: discord.Member, amount: int):
    if ctx.author.id != ADMIN_ID:
        return
    update_balance(member.id, amount)
    await ctx.send(f"✨ Đã cộng {amount:,} xu cho {member.mention}")

@bot.command()
async def daily(ctx):
    if not can_claim_daily(ctx.author.id):
        await ctx.send("⏰ Bạn đã nhận daily hôm nay rồi.")
        return
    update_balance(ctx.author.id, TIEN_DAILY)
    set_last_daily(ctx.author.id)
    await ctx.send(f"✨ Bạn đã nhận {TIEN_DAILY:,} xu daily hôm nay.")

# ======================= GAME LOOP =========================

async def start_game_loop(channel):
    global CHO_PHEP_DAT_CUOC, CUOC_HIEN_TAI, DANG_CHO_KET_QUA, LICH_SU_CAU, VI_ADMIN

    while GAME_DANG_CHAY:
        CUOC_HIEN_TAI = {"tai": {}, "xiu": {}}
        CHO_PHEP_DAT_CUOC = True
        DANG_CHO_KET_QUA = False

        embed = discord.Embed(
            title="🎲 BẮT ĐẦU PHIÊN MỚI",
            description="⏳ Bạn có 60 giây để cược!",
            color=0x00ffff
        )
        tai_count = sum(CUOC_HIEN_TAI['tai'].values())
        xiu_count = sum(CUOC_HIEN_TAI['xiu'].values())
        embed.add_field(name="⭕ Cầu gần đây", value=render_cau(), inline=False)
        embed.add_field(name="🔴 Tài", value=f"{tai_count:,} xu (0 người)", inline=True)
        embed.add_field(name="⚪ Xỉu", value=f"{xiu_count:,} xu (0 người)", inline=True)

        view = ViewDatCuoc()
        await channel.send(embed=embed, view=view)

        await asyncio.sleep(60)

        CHO_PHEP_DAT_CUOC = False
        DANG_CHO_KET_QUA = True
        await asyncio.sleep(2)

        result = random.choice(["tai", "xiu"])
        LICH_SU_CAU.append(result)
        if len(LICH_SU_CAU) > 8:
            LICH_SU_CAU.pop(0)

        winners = CUOC_HIEN_TAI[result]
        for uid, amount in winners.items():
            win = amount * 2 * (1 - THUE)
            update_balance(uid, win)
            VI_ADMIN += int(amount * 2 * THUE)

        await channel.send(f"✨ Kết quả: **{result.upper()}**! {len(winners)} người thắng.")

        await asyncio.sleep(5)

# ====================== VIEW ĐẶT CƯỢC ========================

class ViewDatCuoc(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cược Tài", style=discord.ButtonStyle.red)
    async def cuoc_tai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_cuoc(interaction, "tai")

    @discord.ui.button(label="Cược Xỉu", style=discord.ButtonStyle.grey)
    async def cuoc_xiu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_cuoc(interaction, "xiu")

    async def handle_cuoc(self, interaction, side):
        if not CHO_PHEP_DAT_CUOC:
            await interaction.response.send_message("❌ Phiên đã đóng cược.", ephemeral=True)
            return
        modal = ModalNhapTien(side)
        await interaction.response.send_modal(modal)

class ModalNhapTien(Modal, title="Nhập số tiền muốn cược"):
    def __init__(self, side):
        super().__init__()
        self.side = side
        self.so_tien = TextInput(label="Số xu muốn cược", placeholder="VD: 1000")
        self.add_item(self.so_tien)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(str(self.so_tien.value).lower().replace("k", "000"))
        except:
            await interaction.response.send_message("❌ Số tiền không hợp lệ.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ Số tiền không hợp lệ.", ephemeral=True)
            return
        if get_balance(interaction.user.id) < amount:
            await interaction.response.send_message("❌ Bạn không đủ xu.", ephemeral=True)
            return
        CUOC_HIEN_TAI[self.side][interaction.user.id] = CUOC_HIEN_TAI[self.side].get(interaction.user.id, 0) + amount
        update_balance(interaction.user.id, -amount)
        await interaction.response.send_message(f"✅ Bạn đã cược **{amount:,} xu** vào **{self.side.upper()}**!", ephemeral=True)

# ======================= CẦU =========================

def render_cau():
    symbols = []
    for kq in LICH_SU_CAU:
        if kq == "tai":
            symbols.append("🔴")
        else:
            symbols.append("⚪")
    return " ".join(symbols)

bot.run(TOKEN)
