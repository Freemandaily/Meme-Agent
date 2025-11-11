import ast
import logging
import os
import asyncio
from dotenv import load_dotenv
from trade_processor.trade_main import TradeProcessor
from db_connect.db_connector import db_connector


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s : %(message)s"
)

load_dotenv()
db_connect = db_connector(max_connections=7)
db_connect_Naddy = db_connect.Redis_connect()


# importing Rpc credential from .env file
wss_url = os.getenv('WSS_URL_BSC')
https_rpc = os.getenv('TRADE_RPC_BSC')
profile = os.getenv('PROFILE')
Key_string = os.getenv('KEY')

async def main()-> None:
    Mongo_Database= db_connect.Mongo_Database()
    try:   
        data = await db_connect_Naddy.hgetall(profile)

        if  data:
            profile_byte = list(data.values())[0]

            profile_data = profile_byte.decode('utf-8')
            profile_data = ast.literal_eval(profile_data)
            key = profile_data[Key_string]
            
            process  = TradeProcessor(https_rpc,wss_url,key,db_connect_Naddy,Mongo_Database)
            task = asyncio.create_task(process.start_trade_process())
            await asyncio.gather(task)
    except Exception as e:
        logging.info(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())