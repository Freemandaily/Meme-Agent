import ast
import logging
import os
import asyncio
import time
from dotenv import load_dotenv
from processor.processorManager import proccessor
from db_connect.db_connector import db_connector


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s : %(message)s"
)

load_dotenv()

db_connect = db_connector(max_connections=10)
db_connect_FourMeme = db_connect.Redis_connect()


# importing Rpc credential from .env file
https_rpc = os.getenv('MARKET_RPC_BSC')
wss_url = os.getenv('WSS_URL_BSC')
profile = os.getenv('PROFILE')
Key_string = os.getenv('KEY')


async def main()->None:
    Mongo_Database= db_connect.Mongo_Database()
    try:
        data = await db_connect_FourMeme.hgetall(profile)
        if  data:
            profile_byte = list(data.values())[0]

            profile_data = profile_byte.decode('utf-8')
            profile_data = ast.literal_eval(profile_data)
            key = profile_data[Key_string]
                    
                
        process = proccessor(https_rpc,wss_url,key,db_connect_FourMeme,Mongo_Database)
        task = asyncio.create_task(process.startProcessor())
        await asyncio.gather(task)
    except Exception as e:
        logging.info(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
 
 