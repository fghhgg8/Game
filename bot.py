# bot.py
import os
import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from discord import ButtonStyle, Interaction
from datetime import datetime
import random

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN") or "TOKEN_DISCORD_CỦA_BẠN"
ADMIN_ID = 1115314183731421274

user_data = {}
current_game = None
is_game_active = True
history = []

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

class BetModal(Modal):
    def __init__(self, side):
        super().__init__(title=f"Cược {side.title()}")
        self.side = side
        self.amount = TextInput(label="Nhập số tiền cược", placeholder="VD: 10000 hoặc all")
        self.add_item(self.amount)

    async def on_submit(self, interaction: Interaction):
        global current_game
        user_id = interaction.user.id
        ensure_user(user_id)

        try:
            text = self.amount.value.lower().replace(",", "").strip()
            amount = user_data[user_id]["balance"] if text == "all" else int(text)
        except:
            return await interaction.response.send_message("❌ Số tiền không hợp lệ.", ephemeral=True)

        if amount <= 0 or amount > user_data[user_id]["balance"]:
            return await interaction.response.send_message("❌ Số dư không đủ.", ephemeral=True)

        if not current_game:
            return await interaction.response.send_message("❌ Chưa có phiên cược nào.", ephemeral=True)

        user_data[user_id]["balance"] -= amount
        current_game["bets"].append({
            "user_id": user_id,
            "amount": amount,
            "side": self.side
        })

        await interaction.response.send_message(
            f"✅ Bạn đã cược {amount:,} xu vào **{self.side.upper()}**.",
            ephemeral=True
        )

class BetView(View):
    def __init__(self, is_admin=False):
        super().__init__(timeout=None)
        self.add_item(Button(label="Cược Tài", style=ButtonStyle.green, custom_id="bet_tai"))
        self.add_item(Button(label="Cược Xỉu", style=ButtonStyle.red, custom_id="bet_xiu"))
        if is_admin:
            self.add_item(Button(label="Kết quả: Tài", style=ButtonStyle.blurple, custom_id="result_tai"))
            self.add_item(Button(label="Kết quả: Xỉu", style=ButtonStyle.gray, custom_id="result_xiu"))

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} is running...")

@bot.command()
async def taixiu(ctx):
    global current_game, is_game_active
    if not is_game_active:
        return await ctx.send("🛑 Game đang tắt. Dùng `.on` để bật lại.")

    current_game = {"bets": []}
    is_admin = ctx.author.id == ADMIN_ID

    embed = discord.Embed(
        title="🎲 BẮT ĐẦU PHIÊN MỚI",
        description="Bấm để cược:",
        color=0x00ff00
    )
    embed.add_field(name="Cầu 8 phiên gần nhất", value=generate_history_display(), inline=False)
    embed.add_field(name="Tổng số người cược", value="0", inline=True)
    embed.add_field(name="Tổng xu Tài/Xỉu", value="0 / 0", inline=True)

    await ctx.send(embed=embed, view=BetView(is_admin))

@bot.event
async def on_interaction(interaction: Interaction):
    global current_game
    if not interaction.data or not interaction.data.get("custom_id"):
        return

    user_id = interaction.user.id
    ensure_user(user_id)
    cid = interaction.data["custom_id"]

    if cid == "bet_tai":
        await interaction.response.send_modal(BetModal("tài"))
    elif cid == "bet_xiu":
        await interaction.response.send_modal(BetModal("xỉu"))

    elif cid.startswith("result_") and user_id == ADMIN_ID:
        side = "tài" if cid == "result_tai" else "xỉu"
        winners = []
        tax_total = 0

        if not current_game:
            return await interaction.response.send_message("Không có phiên cược nào.", ephemeral=True)

        for bet in current_game["bets"]:
            if bet["side"] == side:
                win = bet["amount"] * 2
                tax = int(win * 0.02)
                net = win - tax
                user_data[bet["user_id"]]["balance"] += net
                tax_total += tax
                winners.append((bet["user_id"], net))

        update_history(side)
        current_game = None
        ensure_user(ADMIN_ID)
        user_data[ADMIN_ID]["balance"] += tax_total

        for uid, won in winners:
            user = await bot.fetch_user(uid)
            try:
                await user.send(f"🎉 Bạn thắng {won:,} xu từ phiên Tài/Xỉu!")
            except:
                pass

        await interaction.response.send_message(
            f"Kết quả phiên: **{side.upper()}**\n"
            f"Đã cộng thưởng cho người thắng.\n"
            f"Tổng thuế: {tax_total:,} xu đã vào ví admin.",
            ephemeral=True
        )

# Các lệnh như stk, daily, give, addmoney, on/off... giữ nguyên
# (bạn copy lại phần đó từ file trước)

# Cuối cùng, chạy bot
bot.run(TOKEN)
