import os
import json
import discord
import asyncio
from discord.ext import commands
from discord import ButtonStyle, Interaction
from discord.ui import Button, View, Modal, TextInput
from datetime import datetime, timedelta
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

Thread(target=start_fastapi).start()

# ========== DISCORD BOT SETUP ==========

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ID = 1115314183731421274
CHANNEL_ID = 1398174558468706454

user_data = {}
current_game = None
is_game_active = True
history = []

# ========== HELPER FUNCTIONS ==========

def format_balance(user_id):
    balance = user_data.get(user_id, {}).get("balance", 0)
    return f"{balance:,} xu"

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

# ========== MODAL FOR BET AMOUNT ==========

class BetModal(Modal):
    def __init__(self, side):
        super().__init__(title=f"Cược {side.title()}")
        self.side = side
        self.amount = TextInput(label="Nhập số tiền cược", placeholder="VD: 10000 hoặc all")
        self.add_item(self.amount)

    async def on_submit(self, interaction: Interaction):
        user_id = interaction.user.id
        ensure_user(user_id)

        amount_text = self.amount.value.lower().replace(",", "").replace(" ", "")
        if amount_text == "all":
            amount = user_data[user_id]["balance"]
        else:
            try:
                amount = int(amount_text)
            except:
                await interaction.response.send_message("Số tiền không hợp lệ.", ephemeral=True)
                return

        if amount <= 0 or amount > user_data[user_id]["balance"]:
            await interaction.response.send_message("Số dư không đủ.", ephemeral=True)
            return

        if not current_game:
            await interaction.response.send_message("Chưa có phiên cược nào.", ephemeral=True)
            return

        user_data[user_id]["balance"] -= amount
        current_game["bets"].append({"user_id": user_id, "amount": amount, "side": self.side})
        await interaction.response.send_message(f"Bạn đã cược {amount:,} xu vào **{self.side.upper()}**.", ephemeral=True)

# ========== VIEWS ==========

class BetView(View):
    def __init__(self, is_admin=False):
        super().__init__(timeout=None)
        self.add_item(Button(label="Cược Tài", style=ButtonStyle.green, custom_id="bet_tai"))
        self.add_item(Button(label="Cược Xỉu", style=ButtonStyle.red, custom_id="bet_xiu"))
        if is_admin:
            self.add_item(Button(label="Kết quả: Tài", style=ButtonStyle.primary, custom_id="result_tai"))
            self.add_item(Button(label="Kết quả: Xỉu", style=ButtonStyle.secondary, custom_id="result_xiu"))

# ========== BOT EVENTS ==========

@bot.event
async def on_ready():
    print(f"Bot {bot.user} is running...")

@bot.command()
async def taixiu(ctx):
    global current_game, is_game_active
    if not is_game_active:
        await ctx.send("Game đang tắt. Dùng .on để bật lại.")
        return

    current_game = {"bets": []}
    is_admin = ctx.author.id == ADMIN_ID

    embed = discord.Embed(title="🎲 BẮT ĐẦU PHIÊN MỚI", description="Bấm để cược", color=0x00ff00)
    embed.add_field(name="Cầu 8 phiên gần nhất", value=generate_history_display(), inline=False)
    embed.add_field(name="Tổng số người cược", value="0", inline=True)
    embed.add_field(name="Tổng xu Tài/Xỉu", value="0 / 0", inline=True)

    await ctx.send(embed=embed, view=BetView(is_admin))

@bot.event
async def on_interaction(interaction: Interaction):
    if not interaction.data or not interaction.data.get("custom_id"):
        return

    user_id = interaction.user.id
    ensure_user(user_id)

    cid = interaction.data["custom_id"]

    if cid in ["bet_tai", "bet_xiu"]:
        await interaction.response.send_modal(BetModal("tài" if cid == "bet_tai" else "xỉu"))

    elif cid.startswith("result_") and user_id == ADMIN_ID:
        side = "tài" if cid == "result_tai" else "xỉu"
        winners = []
        total_tax = 0
        result_str = f"🎉 Kết quả phiên: **{side.upper()}**\n"

        for bet in current_game["bets"]:
            uid = bet["user_id"]
            if bet["side"] == side:
                win = bet["amount"] * 2
                tax = int(win * 0.02)
                net = win - tax
                user_data[uid]["balance"] += net
                total_tax += tax
                winners.append((uid, net))

        update_history(side)

        for uid, won in winners:
            user = await bot.fetch_user(uid)
            await user.send(f"Bạn thắng {won:,} xu từ phiên vừa rồi!")

        current_game.clear()
        admin_user = await bot.fetch_user(ADMIN_ID)
        ensure_user(ADMIN_ID)
        user_data[ADMIN_ID]["balance"] += total_tax

        await interaction.response.send_message(result_str + f"Tổng thuế {total_tax:,} xu gửi vào ví admin.", ephemeral=True)

# ========== COMMANDS ==========

@bot.command()
async def stk(ctx):
    ensure_user(ctx.author.id)
    await ctx.send(f"💰 Số dư: {format_balance(ctx.author.id)}")

@bot.command()
async def daily(ctx):
    user_id = ctx.author.id
    ensure_user(user_id)
    now = datetime.utcnow()
    last = user_data[user_id].get("last_daily")

    if last and (now - last).days < 1:
        await ctx.send("Bạn đã nhận hôm nay rồi!")
    else:
        user_data[user_id]["balance"] += 5000
        user_data[user_id]["last_daily"] = now
        await ctx.send("🎁 Nhận 5000 xu thành công!")

@bot.command()
async def give(ctx, member: discord.Member, amount: int):
    giver = ctx.author.id
    receiver = member.id
    ensure_user(giver)
    ensure_user(receiver)

    if user_data[giver]["balance"] < amount:
        await ctx.send("Không đủ xu.")
        return

    user_data[giver]["balance"] -= amount
    user_data[receiver]["balance"] += amount
    await ctx.send(f"Đã chuyển {amount:,} xu cho {member.mention}.")

@bot.command()
async def addmoney(ctx, member: discord.Member, amount: int):
    if ctx.author.id != ADMIN_ID:
        return
    ensure_user(member.id)
    user_data[member.id]["balance"] += amount
    await ctx.send(f"Đã thêm {amount:,} xu cho {member.mention}.")

@bot.command()
async def off(ctx):
    global is_game_active
    if ctx.author.id == ADMIN_ID:
        is_game_active = False
        await ctx.send("🛑 Game đã bị tắt.")

@bot.command()
async def on(ctx):
    global is_game_active
    if ctx.author.id == ADMIN_ID:
        is_game_active = True
        await ctx.send("✅ Game đã được bật.")

# ========== RUN BOT ==========

bot.run(TOKEN)
