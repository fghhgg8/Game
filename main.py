import os
import discord
import json
import asyncio
import random
from discord.ext import commands
from datetime import datetime, timedelta
from keep_alive import run

TOKEN = os.environ.get("DISCORD_TOKEN")
ADMIN_ID = 1115314183731421274

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='.', intents=intents)

if not os.path.exists("data.json"):
    with open("data.json", "w") as f:
        json.dump({}, f)

def load_data():
    with open("data.json", "r") as f:
        return json.load(f)

def save_data(data):
    with open("data.json", "w") as f:
        json.dump(data, f, indent=4)

@bot.event
async def on_ready():
    print(f"✅ Bot đã đăng nhập thành {bot.user.name}")
    bot.loop.create_task(xu_ly_tu_dong())

@bot.command()
async def taixiu(ctx):
    data = load_data()
    user_id = str(ctx.author.id)

    if user_id not in data:
        data[user_id] = {"coin": 10000}
        save_data(data)
        await ctx.send(f"Chào mừng bạn mới! Bạn đã nhận được 10.000 xu.")

    data["game"] = {
        "trang_thai": "cho_dat_cuoc",
        "cuoc": {},
        "ket_qua": None,
        "bat_dau": datetime.utcnow().isoformat(),
        "ep_ket_qua": None,
        "ep_no_hu": None
    }
    save_data(data)

    await ctx.send("🎲 Trò chơi Tài Xỉu đã bắt đầu!\nBạn có 60 giây để đặt cược bằng cách dùng `.cuoc tai 10000` hoặc `.cuoc xiu 10k`")

    # Gửi giao diện admin
    if ctx.author.id == ADMIN_ID:
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="🎯 Ra TÀI", style=discord.ButtonStyle.success, custom_id="tai"))
        view.add_item(discord.ui.Button(label="🎯 Ra XỈU", style=discord.ButtonStyle.primary, custom_id="xiu"))
        view.add_item(discord.ui.Button(label="💥 Chọn người nổ hũ", style=discord.ButtonStyle.danger, custom_id="nohu"))
        await ctx.send("👑 **Admin chọn kết quả**\nMặc định bot chọn: **TÀI**\nBạn có 40 giây để thay đổi bằng cách nhấn nút bên dưới.\n\nNếu không chọn gì, bot sẽ giữ kết quả mặc định.", view=view)

async def xu_ly_tu_dong():
    while True:
        await asyncio.sleep(5)
        data = load_data()

        if "game" in data and data["game"]["trang_thai"] == "cho_dat_cuoc":
            bat_dau = datetime.fromisoformat(data["game"]["bat_dau"])
            if datetime.utcnow() - bat_dau > timedelta(seconds=60):
                data["game"]["trang_thai"] = "ket_thuc"
                ep_kq = data["game"].get("ep_ket_qua")
                ket_qua = ep_kq if ep_kq in ["tai", "xiu"] else random.choice(["tai", "xiu"])
                data["game"]["ket_qua"] = ket_qua

                thong_bao = f"✅ Kết quả: **{ket_qua.upper()}**\n"
                for uid, thongtin in data["game"]["cuoc"].items():
                    tien = thongtin["tien"]
                    lua_chon = thongtin["lua_chon"]
                    if uid not in data: continue
                    if lua_chon == ket_qua:
                        data[uid]["coin"] += int(tien * 0.98)
                        thong_bao += f"<@{uid}> ✅ Thắng +{int(tien * 0.98)} xu\n"
                    else:
                        thong_bao += f"<@{uid}> ❌ Thua -{tien} xu\n"

                save_data(data)
                channel = discord.utils.get(bot.get_all_channels(), name="general")
                if channel:
                    await channel.send(thong_bao)

@bot.command()
async def cuoc(ctx, lua_chon: str, so_tien):
    data = load_data()
    user_id = str(ctx.author.id)
    so_tien = str(so_tien).lower().replace("k", "000")
    try:
        so_tien = int(so_tien)
    except:
        return await ctx.send("❌ Số tiền không hợp lệ!")

    if so_tien <= 0 or so_tien > data[user_id]["coin"]:
        return await ctx.send("❌ Số xu không đủ hoặc không hợp lệ!")

    if "game" not in data or data["game"]["trang_thai"] != "cho_dat_cuoc":
        return await ctx.send("❌ Hiện không có phiên cược nào.")

    lua_chon = lua_chon.lower()
    if lua_chon not in ["tai", "xiu"]:
        return await ctx.send("❌ Chỉ được chọn `tai` hoặc `xiu`.")

    data[user_id]["coin"] -= so_tien
    data["game"]["cuoc"][user_id] = {"lua_chon": lua_chon, "tien": so_tien}
    save_data(data)
    await ctx.send(f"✅ <@{user_id}> đã cược **{so_tien} xu** vào **{lua_chon.upper()}**")

@bot.command()
async def daily(ctx):
    data = load_data()
    user_id = str(ctx.author.id)
    if user_id not in data:
        data[user_id] = {"coin": 10000}
        await ctx.send("🎉 Bạn là người chơi mới! Đã nhận 10.000 xu.")
    else:
        data[user_id]["coin"] += 2000
        await ctx.send("🎁 Bạn đã nhận 2.000 xu hôm nay!")

    save_data(data)

# Xử lý nút admin chọn
@bot.event
async def on_interaction(interaction):
    if interaction.user.id != ADMIN_ID:
        return

    data = load_data()
    if "game" not in data or data["game"]["trang_thai"] != "cho_dat_cuoc":
        return await interaction.response.send_message("❌ Không có phiên cược nào đang diễn ra!", ephemeral=True)

    if interaction.data["custom_id"] == "tai":
        data["game"]["ep_ket_qua"] = "tai"
        await interaction.response.send_message("✅ Đã ép kết quả ra **TÀI**", ephemeral=True)
    elif interaction.data["custom_id"] == "xiu":
        data["game"]["ep_ket_qua"] = "xiu"
        await interaction.response.send_message("✅ Đã ép kết quả ra **XỈU**", ephemeral=True)
    elif interaction.data["custom_id"] == "nohu":
        await interaction.response.send_message("💥 Tính năng chọn người nổ hũ sẽ được cập nhật sau!", ephemeral=True)

    save_data(data)

# Khởi động server giữ bot online (Render ping)
run()

# Khởi chạy bot
bot.run(TOKEN)
