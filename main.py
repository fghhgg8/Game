import os  
import discord  
import json  
import asyncio  
import random  
from discord.ext import commands  
from datetime import datetime, timedelta  
  
TOKEN = os.getenv("TOKEN")  # ✅ Lấy token từ biến môi trường  
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
        await interaction.response.send_message(f"✅ Đã chọn người chơi {selected_id} để nổ hũ x{self.jackpot_targets[selected_id]}", ephemeral=True)
