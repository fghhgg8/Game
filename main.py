import os
import discord
import json
import asyncio
import random
from discord.ext import commands
from datetime import datetime, timedelta

TOKEN = "MTM4OTU4OTM0ODQ0MTI2MDEzMw.G3QYKZ.qxNgD9UHLY7Q2cH44kS9HfePmCksYyPvrhnun4"
ADMIN_ID = 1115314183731421274

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents)

# ====== DỮ LIỆU ======
if not os.path.exists("data.json"):
    with open("data.json", "w") as f:
        json.dump({"users": {}, "history": []}, f)

def load_data():
    with open("data.json", "r") as f:
        return json.load(f)

def save_data(data):
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

# ====== VÍ TIỀN ======
def get_balance(user_id):
    data = load_data()
    users = data["users"]
    if user_id not in users:
        users[user_id] = {"balance": 10000, "last_daily": None}
        save_data(data)
    return users[user_id]["balance"]

def add_balance(user_id, amount):
    data = load_data()
    users = data["users"]
    if user_id not in users:
        users[user_id] = {"balance": 10000, "last_daily": None}
    users[user_id]["balance"] += amount
    save_data(data)

def subtract_balance(user_id, amount):
    data = load_data()
    users = data["users"]
    if user_id not in users:
        return False
    if users[user_id]["balance"] >= amount:
        users[user_id]["balance"] -= amount
        save_data(data)
        return True
    return False

def can_claim_daily(user_id):
    data = load_data()
    users = data["users"]
    if user_id not in users:
        return True
    last = users[user_id].get("last_daily")
    if not last:
        return True
    last_time = datetime.fromisoformat(last)
    return datetime.now() - last_time >= timedelta(days=1)

def claim_daily(user_id):
    data = load_data()
    users = data["users"]
    users[user_id]["last_daily"] = datetime.now().isoformat()
    save_data(data)

def transfer(sender_id, receiver_id, amount):
    if subtract_balance(sender_id, amount):
        add_balance(receiver_id, amount)
        return True
    return False

# ====== GAME STATE ======
games = {}

class GameView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.bets = {}
        self.hits = {}
        self.result = None
        self.result_forced = None
        self.jackpot_targets = {}
        self.message = None

    def parse_amount(self, content, user_id):
        content = content.lower()
        balance = get_balance(user_id)
        if content == "all":
            return balance
        if content.endswith("k"):
            try:
                return int(content[:-1]) * 1000
            except:
                return None
        try:
            return int(content)
        except:
            return None

    @discord.ui.button(label="Tài", style=discord.ButtonStyle.secondary, custom_id="tai")
    async def bet_tai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_bet(interaction, "tai")

    @discord.ui.button(label="Xỉu", style=discord.ButtonStyle.primary, custom_id="xiu")
    async def bet_xiu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_bet(interaction, "xiu")

    async def place_bet(self, interaction, side):
        user = interaction.user
        if user.id not in self.bets:
            self.bets[user.id] = {"side": side, "amount": 0}
        await interaction.response.send_message("💰 Nhập số tiền cược (VD: `10000`, `10k`, `all`):", ephemeral=True)

        def check(m):
            return m.author.id == user.id and m.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
            amount = self.parse_amount(msg.content.strip(), str(user.id))
            if amount is None or amount <= 0:
                await interaction.followup.send("❌ Số tiền không hợp lệ.", ephemeral=True)
                return
            if subtract_balance(str(user.id), amount):
                self.bets[user.id] = {"side": side, "amount": amount}
                await interaction.followup.send(f"✅ Đã cược {amount:,} xu vào **{side.upper()}**", ephemeral=True)
            else:
                await interaction.followup.send("❌ Không đủ xu.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Hết thời gian nhập tiền cược.", ephemeral=True)

    @discord.ui.select(placeholder="🎯 Chọn người nổ hũ (tuỳ chọn cho admin)", min_values=0, max_values=1)
    async def select_jackpot(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != ADMIN_ID:
            await interaction.response.send_message("❌ Không có quyền.", ephemeral=True)
            return
        selected_id = int(select.values[0])
        self.jackpot_targets[selected_id] = random.choice([2, 5, 10, 20, 88])
        await interaction.response.send_message(f"💥 Đã chọn <@{selected_id}> nổ hũ x{self.jackpot_targets[selected_id]}!", ephemeral=True)

    @discord.ui.button(label="Ra Tài", style=discord.ButtonStyle.success)
    async def force_tai(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == ADMIN_ID:
            self.result_forced = "tai"
            await interaction.response.send_message("✅ Đã chọn kết quả: **Tài**", ephemeral=True)

    @discord.ui.button(label="Ra Xỉu", style=discord.ButtonStyle.danger)
    async def force_xiu(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == ADMIN_ID:
            self.result_forced = "xiu"
            await interaction.response.send_message("✅ Đã chọn kết quả: **Xỉu**", ephemeral=True)

    async def on_timeout(self):
        tai_sum = sum(random.randint(1, 6) for _ in range(3))
        result = "tai" if tai_sum >= 11 else "xiu"
        if self.result_forced:
            result = self.result_forced
        self.result = result

        winners = []
        losers = []
        data = load_data()
        for user_id, info in self.bets.items():
            uid = str(user_id)
            side, amount = info["side"], info["amount"]
            if side == result:
                rate = self.jackpot_targets.get(user_id, 1)
                payout = int(amount * rate * 0.98)
                add_balance(uid, payout)
                winners.append((user_id, amount, rate, payout))
            else:
                losers.append((user_id, amount))

        data["history"].append(result)
        data["history"] = data["history"][-20:]
        save_data(data)

        desc = f"🎲 KẾT QUẢ: **{tai_sum}** → **{result.upper()}**\n\n"
        if winners:
            desc += "**🏆 Người chiến thắng:**\n"
            for uid, amt, rate, out in winners:
                user = await self.ctx.guild.fetch_member(uid)
                jack = f" (x{rate})" if rate > 1 else ""
                desc += f"- {user.mention}{jack}: cược {amt:,} → nhận {out:,} xu\n"
        else:
            desc += "😢 Không ai thắng cả.\n"

        await self.message.edit(content=desc, view=None)

# ====== LỆNH ======
@bot.command()
async def stk(ctx):
    bal = get_balance(str(ctx.author.id))
    await ctx.send(f"💰 Số dư của bạn: {bal:,} xu")

@bot.command()
async def daily(ctx):
    uid = str(ctx.author.id)
    if can_claim_daily(uid):
        claim_daily(uid)
        add_balance(uid, 2000)
        await ctx.send("🎁 Bạn đã nhận 2.000 xu hôm nay!")
    else:
        await ctx.send("❌ Bạn đã nhận hôm nay rồi!")

@bot.command()
async def nap(ctx, member: discord.Member, amount: int):
    if ctx.author.id != ADMIN_ID:
        return
    add_balance(str(member.id), amount)
    await ctx.send(f"✅ Đã nạp {amount:,} xu cho {member.mention}")

@bot.command()
async def thu(ctx, member: discord.Member, amount: int):
    if ctx.author.id != ADMIN_ID:
        return
    subtract_balance(str(member.id), amount)
    await ctx.send(f"✅ Đã thu {amount:,} xu từ {member.mention}")

@bot.command()
async def chuyen(ctx, member: discord.Member, amount: int):
    if member.id == ctx.author.id:
        return await ctx.send("❌ Không thể chuyển cho chính mình.")
    if transfer(str(ctx.author.id), str(member.id), amount):
        await ctx.send(f"🔁 Đã chuyển {amount:,} xu cho {member.mention}")
    else:
        await ctx.send("❌ Không đủ xu.")

@bot.command()
async def taixiu(ctx):
    view = GameView(ctx)
    select = discord.ui.Select(placeholder="🎯 Chọn người nổ hũ", options=[
        discord.SelectOption(label=member.display_name, value=str(member.id))
        for member in ctx.guild.members if not member.bot
    ])
    view.children.insert(2, select)  # Thêm trước nút force
    msg = await ctx.send("🎰 Bắt đầu phiên tài xỉu! Nhấn nút để cược:", view=view)
    view.message = msg

bot.run(TOKEN)
