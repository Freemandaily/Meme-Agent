import asyncio
import os
import logging
from dotenv import load_dotenv
from redis.asyncio import Redis
import motor.motor_asyncio


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s : %(message)s"
)


load_dotenv()
redis_host = os.getenv('REDIS_HOST')
redis_port = os.getenv('REDIS_PORT')
redis_password = os.getenv('REDIS_PASSWORD')

mongo_url = os.getenv('MONGO_URL')
database_client = motor.motor_asyncio.AsyncIOMotorClient(
            mongo_url
        )
class db_connector:
    def __init__(self,max_connections=3): 

        self.db_connect = Redis(
            # host='localhost',
            # port=6379,
            # db=1
            host=redis_host,
            port=redis_port,
            password=redis_password,
            # single_connection_client=True,
            max_connections=max_connections
            # # db=db
            )
        
        
        self.database = database_client['FourMeme']
     
    def Redis_connect(self,db=None):
        FourMeme = self.db_connect
        return FourMeme
    
    def Mongo_Database(self):
        while True:
            try:
                self.database.command('ping')
                logging.info("✅ MongoDB connection established successfully.")
                return self.database
            except Exception as e:
                logging.error(f"❌ MongoDB connection failed!! Retrying...:")
                continue
    


# database_client = motor.motor_asyncio.AsyncIOMotorClient(
#             mongo_url
#         )
# database = database_client['FourMeme']
# async def main():
#     database.command('ping')
#     collection = database['BondingCurveTokens']
#     token = await collection.find_one({})
#     print(token)

# asyncio.run(main())

# db = db_connector(4)
# async def main():
    
#     database = db.Mongo_Database()
#     collection = database['Test_active']
#     token = '0x883774993009898878779587'
#     forward = {
#                 token : {
#                     'entry_price': 2,
#                     'trail_price': 3,
#                     'Capital' :5/10**18,
#                     'stop_loss': 'uwy',
                    
#                 }
#             }
#     # await collection.insert_one(forward)
#     token = '7hhuhwregerggs'
#     token_data =  {
#                 'entry_price': 2,
#                 'trail_price': 3,
#                 'Capital' :5/10**18,
#                 'stop_loss': 'uwy'
#                 }
            
#     # await collection.insert_one(forward)
#     # token = '0x8837749937'
#     # await collection.update_one(
#     #     {token: {"$exists":True}},
#     #     {
#     #         "$unset":{f"{token}":""}
#     #     }
#     # )

#     # token_data = await collection.find_one(
#     #     {token: {"$exists": True}},
#     #     {token: 1}
#     # )
#     # # print(token_data)
#     # token_datas = await collection.find_one({})
#     print('Fetched')
#     # if not token_datas:
#     #     await collection.insert_one({'ActiveOrders':{}})
#     await collection.update_one(
#         {},
#         {
#             "$set":{f"ActiveOrders.{f"{token}"}":token_data}
#         }
#     )

#     # await collection.update_one(
#     #     {},
#     #     {
#     #         "$unset":{f"ActiveOrders.{token}.entry_price":""}
#     #     }
#     # )
#     # token = "7hhuhws"
#     # token_data = await collection.find_one(
#     #     {},
#     #     {f"ActiveOrders.{token}":1}
#     #     )

#     token_datas = await collection.find_one({})
#     print(token_datas)
# asyncio.run(main())
    