# bot.py

import os
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
from discord import ButtonStyle, Interaction
from datetime import datetime
import random
import uvicorn
from fastapi import FastAPI
from threading import Thread

# ========== FASTAPI KEEP ALIVE ==========

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Bot is running"}

def start_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ========== DISCORD SETUP ==========

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ID = 1115314183731421274

user_data = {}
current_game = None
is_game_active = True
history = []
game_message = None
forced_result = None
jackpot_amount = 0

# ========== HELPER ==========

def format_balance(user_id):
    return f"{user_data.get(user_id, {}).get('balance', 0):,} xu"

def ensure_user(user_id):
    if user_id not in user_data:
        user_data[user_id] = {"balance": 10000, "last_daily": None}

def update_history(result):
    history.append(result)
    if len(history) > 8:
        history.pop(0)

def generate_history_display():
    icons = {"tài": "⚫", "xỉu": "⚪"}
    return "".join([icons.get(x, "❔") for x in history])

# ========== MODAL CƯỢC ==========

class BetModal(Modal):
    def __init__(self, side, user_id):
        super().__init__(title=f"Cược {side.title()}")
        self.side = side
        self.user_id = user_id
        balance = format_balance(user_id)
        self.amount = TextInput(
            label=f"Nhập số tiền cược (Số dư: {balance})",
            placeholder="VD: 10000 hoặc all"
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: Interaction):
        global current_game
        ensure_user(self.user_id)

        try:
            text = self.amount.value.lower().replace(",", "").strip()
            amount = user_data[self.user_id]["balance"] if text == "all" else int(text)
        except:
            return await interaction.response.send_message("❌ Số tiền không hợp lệ.", ephemeral=True)

        if amount <= 0 or amount > user_data[self.user_id]["balance"]:
            return await interaction.response.send_message("❌ Số dư không đủ.", ephemeral=True)

        if not current_game:
            return await interaction.response.send_message("❌ Chưa có phiên cược nào.", ephemeral=True)

        user_data[self.user_id]["balance"] -= amount
        current_game["bets"].append({"user_id": self.user_id, "amount": amount, "side": self.side})

        await interaction.response.send_message(
            f"✅ Bạn đã cược {amount:,} xu vào **{self.side.upper()}**.",
            ephemeral=True
        )

# ========== VIEW CƯỢC ==========

class BetView(View):
    def __init__(self, is_admin=False):
        super().__init__(timeout=None)
        self.add_item(Button(label="Cược Tài", style=ButtonStyle.green, custom_id="bet_tai"))
        self.add_item(Button(label="Cược Xỉu", style=ButtonStyle.red, custom_id="bet_xiu"))
        if is_admin:
            self.add_item(Button(label="Ép Tài", style=ButtonStyle.blurple, custom_id="admin_force_tai"))
            self.add_item(Button(label="Ép Xỉu", style=ButtonStyle.blurple, custom_id="admin_force_xiu"))
            self.add_item(Button(label="+ Jackpot", style=ButtonStyle.gray, custom_id="admin_add_jackpot"))
            self.add_item(Button(label="💥 Nổ Jackpot", style=ButtonStyle.green, custom_id="admin_trigger_jackpot"))

# ========== GỬI BẢNG GAME ==========

async def send_or_update_game(ctx):
    global current_game, game_message
    current_game = {"bets": []}

    bets = current_game["bets"]
    total_tai = sum(b["amount"] for b in bets if b["side"] == "tài")
    total_xiu = sum(b["amount"] for b in bets if b["side"] == "xỉu")
    bettors = len(set(b["user_id"] for b in bets))

    embed = discord.Embed(title="🎲 BẢNG GAME TÀI/XỈU", color=0x00ff00)
    embed.add_field(name="Cầu 8 phiên gần nhất", value=generate_history_display(), inline=False)
    embed.add_field(name="Tổng số người cược", value=str(bettors), inline=True)
    embed.add_field(name="Tổng xu Tài/Xỉu", value=f"{total_tai:,} / {total_xiu:,}", inline=True)

    is_admin = ctx.author.id == ADMIN_ID
    view = BetView(is_admin=is_admin)

    if game_message:
        await game_message.edit(embed=embed, view=view)
    else:
        game_message = await ctx.send(embed=embed, view=view)

# ========== VÒNG LẶP PHIÊN ==========

@tasks.loop(seconds=60)
async def start_round():
    global current_game, forced_result, jackpot_amount
    if not is_game_active or not game_message:
        return

    side = forced_result if forced_result else random.choice(["tài", "xỉu"])
    forced_result = None
    winners = []
    tax_total = 0

    for bet in current_game["bets"]:
        if bet["side"] == side:
            win = bet["amount"] * 2
            tax = int(win * 0.02)
            net = win - tax
            ensure_user(bet["user_id"])
            user_data[bet["user_id"]]["balance"] += net
            tax_total += tax
            winners.append((bet["user_id"], net))

    update_history(side)
    ensure_user(ADMIN_ID)
    user_data[ADMIN_ID]["balance"] += tax_total

    if winners:
        lines = [f"<@{uid}> thắng {won:,} xu!" for uid, won in winners]
        await game_message.channel.send(f"🎉 Kết quả phiên: **{side.upper()}**\n" + "\n".join(lines))
    else:
        await game_message.channel.send(f"📣 Kết quả phiên: **{side.upper()}**. Không ai thắng!")

    await send_or_update_game(game_message.channel)

# ========== SỰ KIỆN ==========

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} is running...")
    start_round.start()

@bot.command()
async def game(ctx):
    global is_game_active, game_message
    if not is_game_active:
        return await ctx.send("🛑 Game đang tắt. Dùng `.on` để bật lại.")
    if game_message:
        return await ctx.send("⚠️ Bảng game đã có rồi!")
    await send_or_update_game(ctx)

@bot.event
async def on_interaction(interaction: Interaction):
    global current_game, forced_result, jackpot_amount
    if not interaction.data or not interaction.data.get("custom_id"):
        return

    cid = interaction.data["custom_id"]

    if cid.startswith("bet_"):
        side = "tài" if cid == "bet_tai" else "xỉu"
        await interaction.response.send_modal(BetModal(side, interaction.user.id))

    elif interaction.user.id == ADMIN_ID:
        if cid == "admin_force_tai":
            forced_result = "tài"
            await interaction.response.send_message("✅ Đã ép kết quả TÀI cho phiên này.", ephemeral=True)
        elif cid == "admin_force_xiu":
            forced_result = "xỉu"
            await interaction.response.send_message("✅ Đã ép kết quả XỈU cho phiên này.", ephemeral=True)
        elif cid == "admin_add_jackpot":
            jackpot_amount += 10000
            await interaction.response.send_message(f"💰 Đã thêm 10.000 vào jackpot. Tổng: {jackpot_amount:,} xu", ephemeral=True)
        elif cid == "admin_trigger_jackpot":
            await game_message.channel.send(f"💥 JACKPOT NỔ! Admin nhận {jackpot_amount:,} xu!")
            ensure_user(ADMIN_ID)
            user_data[ADMIN_ID]["balance"] += jackpot_amount
            jackpot_amount = 0
            await interaction.response.send_message("💥 Jackpot đã được kích hoạt!", ephemeral=True)

# ========== LỆNH KHÁC ==========

@bot.command()
async def stk(ctx):
    ensure_user(ctx.author.id)
    await ctx.send(f"💰 Số dư của bạn: {format_balance(ctx.author.id)}")

@bot.command()
async def daily(ctx):
    user_id = ctx.author.id
    ensure_user(user_id)
    now = datetime.utcnow()
    last = user_data[user_id]["last_daily"]
    if last and (now - last).days < 1:
        await ctx.send("📆 Bạn đã nhận quà hôm nay rồi!")
    else:
        user_data[user_id]["balance"] += 5000
        user_data[user_id]["last_daily"] = now
        await ctx.send("🎁 Nhận thành công 5000 xu!")

@bot.command()
async def give(ctx, member: discord.Member, amount: int):
    giver = ctx.author.id
    receiver = member.id
    ensure_user(giver)
    ensure_user(receiver)

    if user_data[giver]["balance"] < amount:
        return await ctx.send("❌ Bạn không đủ xu để chuyển.")

    user_data[giver]["balance"] -= amount
    user_data[receiver]["balance"] += amount
    await ctx.send(f"✅ Đã chuyển {amount:,} xu cho {member.mention}.")

@bot.command()
async def addmoney(ctx, member: discord.Member, amount: int):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send("Bạn không có quyền.")
    ensure_user(member.id)
    user_data[member.id]["balance"] += amount
    await ctx.send(f"💸 Đã thêm {amount:,} xu cho {member.mention}.")

@bot.command()
async def on(ctx):
    global is_game_active
    if ctx.author.id == ADMIN_ID:
        is_game_active = True
        await ctx.send("✅ Game đã bật.")

@bot.command()
async def off(ctx):
    global is_game_active
    if ctx.author.id == ADMIN_ID:
        is_game_active = False
        await ctx.send("🛑 Game đã tắt.")

# ========== CHẠY ==========

if __name__ == "__main__":
    Thread(target=start_fastapi).start()
    bot.run(TOKEN)
