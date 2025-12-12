import discord
from discord.ext import commands, tasks
from discord import app_commands
from cogs.utils import ensure_user_registered, connect_db, get_user_data, update_user_data
from datetime import datetime
import math

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bank_interest_and_loan_check.start()

    def cog_unload(self):
        self.bank_interest_and_loan_check.cancel()

    # 잔액 확인
    @app_commands.command(name='잔액', description='현재 소지금, 은행 잔고, 직업을 확인합니다.') 
    async def balance(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        user_id = interaction.user.id
        ensure_user_registered(user_id) 
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT money, bank_balance, current_job FROM users WHERE user_id = ?", (user_id,))
        data = cursor.fetchone()
        conn.close()

        if data:
            money, bank_balance, job = data
            
            embed = discord.Embed(title=f'🏦 {interaction.user.display_name} 님의 자산 현황', color=discord.Color.blue())
            embed.add_field(name="💰 현재 소지금", value=f"**{money:,}** 원", inline=False)
            embed.add_field(name="💼 은행 잔고", value=f"{bank_balance:,} 원", inline=False)
            embed.add_field(name="🏢 현재 직업", value=f"`{job}`", inline=True)
            embed.set_footer(text="소지금은 바로 사용할 수 있으며, 은행 잔고는 세금 혜택을 받습니다.")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("오류: 사용자 정보를 찾을 수 없습니다.")

    # 예금
    @app_commands.command(name='예금', description='소지금을 은행에 예금합니다.')
    @app_commands.describe(금액='예금할 금액을 입력하세요.')
    async def deposit(self, interaction: discord.Interaction, 금액: int):
        await interaction.response.defer(ephemeral=False)
        user_id = interaction.user.id
        ensure_user_registered(user_id) 
        user_data = get_user_data(user_id)
        
        money = user_data[1]
        bank_balance = user_data[2]
        
        if 금액 <= 0: return await interaction.followup.send("❌ 예금 금액은 1원 이상이어야 합니다.")
        if 금액 > money: return await interaction.followup.send(f"❌ 소지금이 부족합니다. 현재 소지금: {money:,}원")
            
        new_money = money - 금액
        new_bank_balance = bank_balance + 금액
        
        update_user_data(user_id, 'money', new_money)
        update_user_data(user_id, 'bank_balance', new_bank_balance)
        
        await interaction.followup.send(f"✅ **{금액:,}원**을 예금했습니다. 현재 은행 잔고: {new_bank_balance:,}원")

    # 출금
    @app_commands.command(name='출금', description='은행 잔고에서 소지금으로 출금합니다.')
    @app_commands.describe(금액='출금할 금액을 입력하세요.')
    async def withdraw(self, interaction: discord.Interaction, 금액: int):
        await interaction.response.defer(ephemeral=False)
        user_id = interaction.user.id
        ensure_user_registered(user_id) 
        user_data = get_user_data(user_id)
        
        money = user_data[1]
        bank_balance = user_data[2]
        
        if 금액 <= 0: return await interaction.followup.send("❌ 출금 금액은 1원 이상이어야 합니다.")
        if 금액 > bank_balance: return await interaction.followup.send(f"❌ 은행 잔고가 부족합니다. 현재 잔고: {bank_balance:,}원")
            
        new_money = money + 금액
        new_bank_balance = bank_balance - 금액
        
        update_user_data(user_id, 'money', new_money)
        update_user_data(user_id, 'bank_balance', new_bank_balance)
        
        await interaction.followup.send(f"✅ **{금액:,}원**을 출금했습니다. 현재 소지금: {new_money:,}원")

    # 대출
    @app_commands.command(name='대출', description='신용도에 따라 대출을 받습니다. (대출 한도: 신용도 * 10,000)')
    @app_commands.describe(금액='대출받을 금액을 입력하세요.')
    async def loan(self, interaction: discord.Interaction, 금액: int):
        await interaction.response.defer(ephemeral=False)
        user_id = interaction.user.id
        ensure_user_registered(user_id) 
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT bank_balance, credit_score FROM users WHERE user_id = ?", (user_id,))
        bank_balance, credit_score = cursor.fetchone()

        max_loan = credit_score * 10000 
        
        if 금액 <= 0 or 금액 % 1000 != 0: return await interaction.followup.send("❌ 대출 금액은 1,000원 단위로 입력해야 합니다.")
        if bank_balance < 0: return await interaction.followup.send(f"❌ 현재 미상환 대출금 {bank_balance:,}원이 있습니다. 상환 후 다시 시도하세요.")
        if 금액 > max_loan: return await interaction.followup.send(f"❌ 대출 한도 초과입니다. 최대 대출 한도는 **{max_loan:,}원**입니다.")
            
        new_bank_balance = bank_balance - 금액
        update_user_data(user_id, 'bank_balance', new_bank_balance)
        
        await interaction.followup.send(
            f"✅ **{금액:,}원** 대출 완료! 현재 대출금: {new_bank_balance:,}원 (12시간마다 이자율 적용)"
        )

    # 상환
    @app_commands.command(name='상환', description='대출금을 상환합니다.')
    @app_commands.describe(금액='상환할 금액을 입력하세요.')
    async def repayment(self, interaction: discord.Interaction, 금액: int):
        await interaction.response.defer(ephemeral=False)
        user_id = interaction.user.id
        ensure_user_registered(user_id) 
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT money, bank_balance FROM users WHERE user_id = ?", (user_id,))
        money, bank_balance = cursor.fetchone()
        
        loan_amount = -bank_balance
        
        if bank_balance >= 0: return await interaction.followup.send("❌ 현재 상환할 대출금이 없습니다.")
        if 금액 <= 0: return await interaction.followup.send("❌ 상환 금액은 1원 이상이어야 합니다.")
        if 금액 > money: return await interaction.followup.send(f"❌ 소지금이 부족합니다. 현재 소지금: {money:,}원")
            
        repay_amount = min(금액, loan_amount)
        
        new_money = money - repay_amount
        new_bank_balance = bank_balance + repay_amount
        
        update_user_data(user_id, 'money', new_money)
        update_user_data(user_id, 'bank_balance', new_bank_balance)
        
        remaining = max(0, -new_bank_balance)
        
        if remaining == 0:
            await interaction.followup.send(f"✅ 대출금 **{repay_amount:,}원**을 전액 상환했습니다! 이제 빚이 없습니다.")
        else:
            await interaction.followup.send(f"✅ 대출금 **{repay_amount:,}원**을 상환했습니다. 잔여 대출금: {remaining:,}원")


    # 자동 루프: 이자 및 대출금 처리 (12시간마다)
    @tasks.loop(hours=12) 
    async def bank_interest_and_loan_check(self):
        await self.bot.wait_until_ready()
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, bank_balance, credit_score FROM users")
        users = cursor.fetchall()
        
        for user_id, bank_balance, credit_score in users:
            
            # 1. 예금 이자 지급
            if bank_balance > 0:
                interest_rate = (credit_score / 100) * 0.01 
                interest = math.floor(bank_balance * interest_rate)
                
                new_bank_balance = bank_balance + interest
                update_user_data(user_id, 'bank_balance', new_bank_balance)
                
                if interest > 0:
                    try:
                        user = self.bot.get_user(user_id)
                        if user:
                            await user.send(f"💸 **[은행 이자 지급]** 12시간 동안의 예금 이자 **{interest:,}원**이 지급되었습니다. (잔고: {new_bank_balance:,}원)")
                    except: pass
            
            # 2. 대출 이자 징수
            elif bank_balance < 0:
                loan_amount = -bank_balance
                interest_rate = (100 - credit_score) / 100 * 0.015 + 0.015
                loan_interest = math.ceil(loan_amount * interest_rate)

                new_bank_balance = bank_balance - loan_interest
                update_user_data(user_id, 'bank_balance', new_bank_balance)
                
                try:
                    user = self.bot.get_user(user_id)
                    if user:
                        await user.send(f"🚨 **[대출 이자 징수]** 12시간 동안의 대출 이자 **{loan_interest:,}원**이 징수되었습니다. (현재 대출금: {-new_bank_balance:,}원)")
                except: pass
        
        conn.close()
        print(f"[{datetime.now().strftime('%H:%M')}] 은행 이자/대출 처리 완료.")

    @bank_interest_and_loan_check.before_loop
    async def before_bank_interest_and_loan_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Economy(bot))