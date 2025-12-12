import discord
from discord.ext import commands, tasks
from discord import app_commands
from cogs.utils import ensure_user_registered, get_user_data, update_user_data, connect_db
from datetime import datetime
import random

class Survival(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stat_decay_check.start() 

    def cog_unload(self):
        self.stat_decay_check.cancel()
        
    @app_commands.command(name='상태', description='체력, 배고픔, 신용도 등 상세 스탯을 확인합니다.')
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        user_id = interaction.user.id
        ensure_user_registered(user_id) 
        user_data = get_user_data(user_id)
        
        if user_data:
            health = user_data[5]
            hunger = user_data[6]
            credit_score = user_data[7]
            job = user_data[3]
            
            embed = discord.Embed(title=f'👤 {interaction.user.display_name} 님의 상세 정보', color=discord.Color.red())
            
            embed.add_field(name="❤️ 체력", value=f"{health}/100", inline=True)
            embed.add_field(name="🍖 배고픔", value=f"{hunger}/100", inline=True)
            embed.add_field(name="📈 신용도", value=f"{credit_score}", inline=True)
            embed.add_field(name="🏢 직업", value=f"`{job}`", inline=False)
            
            if credit_score >= 80: comment = "신용 우수. 대출 이자율이 매우 낮습니다."
            elif credit_score >= 40: comment = "신용 양호. 기본적인 경제 활동에 지장이 없습니다."
            else: comment = "🚨 신용도가 낮음! 대출 제한 및 벌금 페널티 위험."
                
            embed.set_footer(text=f"신용 정보: {comment}")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("DB 정보를 가져오는 데 오류가 발생했습니다.")
            
    @tasks.loop(hours=1) 
    async def stat_decay_check(self):
        await self.bot.wait_until_ready()
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, money, health, hunger FROM users")
        users = cursor.fetchall()
        
        for user_id, money, health, hunger in users:
            
            new_hunger = max(0, hunger - random.randint(3, 7))
            
            if new_hunger <= 0 and health > 0:
                new_health = max(0, health - random.randint(5, 10))
                
                if new_health == 0:
                    penalty_money = int(money * 0.05)
                    final_money = max(0, money - penalty_money)
                    
                    update_user_data(user_id, 'money', final_money)
                    update_user_data(user_id, 'health', 50) 
                    
                    try:
                        user = self.bot.get_user(user_id)
                        if user:
                            await user.send(f"🚑 **[기절! 병원행]** 체력 부족으로 기절했습니다. 치료비 **{penalty_money:,}원**이 차감되었고, 체력 50으로 회복되었습니다.")
                    except:
                        pass
                
                else:
                    update_user_data(user_id, 'health', new_health)

            update_user_data(user_id, 'hunger', new_hunger)
            
        conn.close()
        
    @stat_decay_check.before_loop
    async def before_stat_decay_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Survival(bot))