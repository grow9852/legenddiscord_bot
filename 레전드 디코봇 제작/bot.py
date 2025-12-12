import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from cogs.utils import connect_db

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

def initialize_db():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            money INTEGER DEFAULT 1000, 
            bank_balance INTEGER DEFAULT 0,
            current_job TEXT DEFAULT '시민',
            last_work_date TEXT,
            health INTEGER DEFAULT 100,
            hunger INTEGER DEFAULT 100,
            credit_score INTEGER DEFAULT 50,
            inventory TEXT DEFAULT '{}',
            crime_record TEXT DEFAULT '[]'
        )
    """)
    conn.commit()
    conn.close()
    print("DB 테이블 초기화 완료: eco_rpg.db 파일이 준비되었습니다.")

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True 

bot = commands.Bot(command_prefix=None, intents=intents) 

async def load_cogs():
    extensions = [
        'cogs.economy', 
        'cogs.job_system',
        'cogs.survival'
    ]
    
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            print(f"✅ {extension} 로드 성공")
        except Exception as e:
            print(f"❌ {extension} 로드 실패: {e}")

@bot.event
async def on_ready():
    print(f'*** 봇 이름: {bot.user.name} ***')
    print(f'*** 봇 ID: {bot.user.id} ***')
    
    initialize_db() 
    await load_cogs() 
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ 슬래시 명령어 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")
    
    await bot.change_presence(activity=discord.Game(name="국가 경제 시스템 운영"))
    print('봇 준비 완료')
    print('---------------------------')


if TOKEN:
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("에러: 토큰이 유효하지 않습니다. .env 파일을 확인하세요.")
else:
    print("에러: 토큰을 찾을 수 없습니다. .env 파일을 확인하세요.")