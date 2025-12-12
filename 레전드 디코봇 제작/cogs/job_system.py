import discord
from discord.ext import commands, tasks
from discord import app_commands
from cogs.utils import ensure_user_registered, get_user_data, update_user_data, connect_db
from datetime import datetime, timedelta
import random

class JobSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.job_payouts = {
            '사무직': (500, 1000),
            '예술직': (600, 1200),
            '운송직': (700, 1400),
            '시민': (300, 500),
            '법조인': (0, 0),
            '의료인': (0, 0)
        }
        self.change_job_cost = 5000 
        self.daily_duty_check.start() 

    def cog_unload(self):
        self.daily_duty_check.cancel()

    # 노동
    @app_commands.command(name='노동', description='현재 직업에 따라 일일 노동을 수행하여 보상을 받습니다.')
    async def work(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        user_id = interaction.user.id
        ensure_user_registered(user_id) 
        user_data = get_user_data(user_id)
        
        # DB 컬럼 순서
        user_id, money, _, current_job, last_work_date, _, hunger, _, _, _ = user_data

        today = datetime.now().date()
        
        if hunger <= 20: return await interaction.followup.send("❌ 배고픔 수치가 너무 낮습니다 (20 미만). 음식을 먹어야 노동할 수 있습니다.")
        
        if last_work_date:
            last_work_date_obj = datetime.strptime(last_work_date, '%Y-%m-%d').date()
            if last_work_date_obj == today:
                return await interaction.followup.send("⏳ 오늘은 이미 노동을 마쳤습니다. 내일 다시 시도해주세요.")

        if current_job in self.job_payouts:
            min_pay, max_pay = self.job_payouts[current_job]
            earnings = random.randint(min_pay, max_pay)
            
            new_money = money + earnings
            new_hunger = max(0, hunger - 15)
            
            update_user_data(user_id, 'money', new_money)
            update_user_data(user_id, 'last_work_date', str(today))
            update_user_data(user_id, 'hunger', new_hunger)

            await interaction.followup.send(f"✅ {current_job} 노동을 완료했습니다! **{earnings:,} 원**을 벌었습니다. (배고픔 -15)")
        else:
            await interaction.followup.send(f"현재 직업 '{current_job}'은 노동 기능이 없습니다. (전문직은 `/전문직활동` 등 별도 명령어 필요)")
        
    # 시험
    @app_commands.command(name='시험', description='특정 전문직의 시험을 봅니다. (신용도 60 이상 필요)')
    @app_commands.describe(직업='시험을 볼 전문직의 종류를 선택하세요.')
    @app_commands.choices(직업=[
        app_commands.Choice(name='법조인 (법률)', value='법조인'),
        app_commands.Choice(name='의료인 (의학)', value='의료인'),
    ])
    async def exam(self, interaction: discord.Interaction, 직업: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=False)
        user_id = interaction.user.id
        ensure_user_registered(user_id) 
        user_data = get_user_data(user_id)
        
        credit_score = user_data[7]
        current_job = user_data[3]
        target_job = 직업.value

        if current_job != '시민': return await interaction.followup.send(f"❌ 현재 이미 직업(`{current_job}`)이 있습니다. 이직하려면 `/이직` 명령어를 사용해야 합니다.")
        if credit_score < 60: return await interaction.followup.send(f"❌ 신용도가 60 미만입니다. ({credit_score}). 시험 응시 최소 신용도는 60입니다.")

        pass_chance = random.randint(1, 100)

        if pass_chance <= 70:
            update_user_data(user_id, 'current_job', target_job)
            await interaction.followup.send(
                f"🎉 **축하합니다!** {target_job} 시험에 합격했습니다!\n"
                f"이제 당신의 직업은 `{target_job}`입니다. `/상태`를 확인하세요."
            )
        else:
            new_credit_score = max(50, credit_score - 5)
            update_user_data(user_id, 'credit_score', new_credit_score)
            
            await interaction.followup.send(
                f"😢 **불합격**입니다. 실력이 부족합니다.\n"
                f"불합격 페널티로 신용도가 5 하락했습니다. (현재 신용도: {new_credit_score})"
            )

    # 이직
    @app_commands.command(name='이직', description=f'현재 직업을 버리고 새로운 직업을 선택합니다. 비용: {5000:,}원')
    @app_commands.describe(직업='이직할 직업을 선택하세요.')
    @app_commands.choices(직업=[
        app_commands.Choice(name='사무직 (월급)', value='사무직'),
        app_commands.Choice(name='운송직 (배달)', value='운송직'),
        app_commands.Choice(name='예술직 (창작)', value='예술직'),
        app_commands.Choice(name='시민 (무직)', value='시민'),
    ])
    async def change_job(self, interaction: discord.Interaction, 직업: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=False)
        user_id = interaction.user.id
        ensure_user_registered(user_id) 
        user_data = get_user_data(user_id)
        
        money = user_data[1]
        current_job = user_data[3]
        target_job = 직업.value
        cost = self.change_job_cost

        if current_job == target_job: return await interaction.followup.send(f"❌ 이미 `{target_job}`입니다.")
        
        if current_job in ['법조인', '의료인'] and target_job in ['사무직', '운송직', '예술직', '시민']:
            cost = 0

        if money < cost: return await interaction.followup.send(f"❌ 이직 비용 **{cost:,}원**이 부족합니다. 현재 소지금: {money:,}원")

        new_money = money - cost
        update_user_data(user_id, 'money', new_money)
        update_user_data(user_id, 'current_job', target_job)
        update_user_data(user_id, 'last_work_date', None)
        
        cost_message = f"이직 비용 {cost:,}원이 차감되었으며, " if cost > 0 else ""
        
        await interaction.followup.send(
            f"✅ 이직 완료! {cost_message}당신의 직업이 `{current_job}`에서 **{target_job}**으로 변경되었습니다.\n"
            f"새로운 직업으로 노동을 시작하세요. (`/노동`)"
        )


    # 일일 노동 의무 확인 루프 (매일 자정)
    @tasks.loop(hours=24) 
    async def daily_duty_check(self):
        await self.bot.wait_until_ready()

        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id, last_work_date, money, credit_score FROM users WHERE current_job IN ('사무직', '예술직', '운송직')")
        workers = cursor.fetchall()
        
        for user_id, last_work_date, money, credit_score in workers:
            if not last_work_date or datetime.strptime(last_work_date, '%Y-%m-%d').date() < yesterday:
                penalty_amount = int(money * 0.05) 
                new_money = max(0, money - penalty_amount)
                new_credit_score = max(10, credit_score - 5) 
                
                update_user_data(user_id, 'money', new_money)
                update_user_data(user_id, 'credit_score', new_credit_score)

                try:
                    user = self.bot.get_user(user_id)
                    if user:
                        await user.send(f"🚨 **[노동 의무 미이행]** 어제 노동을 하지 않아 벌금 **{penalty_amount:,}원**이 징수되었고, 신용도가 5 하락했습니다. (현재 신용도: {new_credit_score})")
                except Exception as e:
                    pass
        
        conn.close()

async def setup(bot):
    await bot.add_cog(JobSystem(bot))