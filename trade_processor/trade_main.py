from decimal import Decimal
import math
import os
import sys
import ast
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import telegram
from dotenv import load_dotenv
from web3 import AsyncWeb3,AsyncHTTPProvider
from eth_abi import decode

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from db_connect.db_connector import db_connector
from Four_sdk import (
    SellParams,
    Trade,
    Token,
    BuyParams,
    calculate_slippage,
    parseMon,
    EventType,
    CurveStream,
    DexStream,
    WBNB,
    CONTRACTS
)


log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)-8s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File handler
file_handler = logging.FileHandler(log_dir / 'trade_main.log', encoding='utf-8')
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)


buy_conditions = {
    '5 minute' : 10,# % ( this is percent) signifying the percentage threshold for 5 minute  for total cap deposit
    '10 minute' : 15,
    '15 minute' : 20,
    '20 minute' : 25,
    '25 minute' : 30,
    '30 minute' : 35,
    '35 minute' : 40,
    '40 minute' : 45,
    '45 minute' : 50,
    '50 minute' : 55,
    '55 minute' : 60
    
}


load_dotenv()

class TradeProcessor:
    def __init__(self,https_rpc,ws_url,private_key,db_connect_FourMeme:db_connector,Mongo_database:db_connector):
        self.db_connect_FourMeme = db_connect_FourMeme
        self.stop_loss = 15 # percent
        self.mon_amount = 0.0004 # default enntry amount
        self.trade = Trade(https_rpc,private_key)
        self.token = Token(https_rpc, private_key)
        self.Wbnb_address = WBNB
        self.uniswap_router = CONTRACTS['pancakeRouter']

        self.MonDepositGrowth = Mongo_database['MonDepositGrowth']
        self.ActiveMonitoredTokens = Mongo_database['ActiveMonitoredTokens']
        self.ActiveOrders = Mongo_database['ActiveOrders']
        self.Experiment = Mongo_database['Experiment_Trade']

        self.TradedTokenList = 'TradedTokenList'
        self.CompletedOrders = 'CompletedOrders'
        self.signal = 'signal'
        self.tokens_to_monitor_price = None

        self.stream_curve_trade = CurveStream(ws_url)
        self.stream_dex_trade = DexStream(https_rpc, ws_url)
        self.tokens_previous_price = {}

        self.bot_token = os.getenv('TELE_TOKEN_BSC')
        self.rpc_connection = AsyncWeb3(AsyncHTTPProvider(os.getenv('RPC_FOR_TELE_BSC')))

        self.curve_sell_topic = '0x0a5575b3648bae2210cee56bf33254cc1ddfbc7bf637c0af2ac18b14fb1bae19'
        self.pancake_swap_pool_topic = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"

    
    async def start_trade_process(self):
        task1 = asyncio.create_task(self.match_condition())
        task2 = asyncio.create_task(self.AwaitSignal())
        task3 = asyncio.create_task(self.Await_Order_from_Telegram())

        await asyncio.gather(task1,task2,task3)

    async def match_condition(self)->None:# this should be iterating
        logger.info('Matching Condition Started')
        watching_count  = 0
        while True:
            try:
                tokens_data = await self.MonDepositGrowth.find_one({})
                if tokens_data:
                    tokens_data = tokens_data['Deposit_Growth']
                    condition_task = [self.match(token,data) for token, data in tokens_data.items()]
                    condition = await asyncio.gather(*condition_task)

                watching_count += 1
                if watching_count > 50:
                    logging.info('Engine Still Watching For A Trade!!!')
                    watching_count = 0
            except Exception as e:
                logger.error(f"Error Matching Conditions: Issue {e}")
                continue
            await asyncio.sleep(5)

    # --Matching the buy condition--
    async def match(self,token:str, data:dict)->None:

        for total_round_checked , percent_deposit in data.items():
            try:
                percent_cap_deposit = buy_conditions[total_round_checked]

                if float(percent_deposit) >= percent_cap_deposit:
                    # To DO: check for holders count , if valid , buy, else we skip . 
                    asyncio.create_task(self.buy(token,self.mon_amount))

                    # Removing this token from db to avoid repitition of buy
                    try:
                        await self.MonDepositGrowth.update_one(
                            {},
                            {
                                "$unset":{f"Deposit_Growth.{token}": ""}
                            }
                        )
                        await self.ActiveMonitoredTokens.update_one(
                            {},
                            {
                                "$unset":{f"Monitored_Token.{token}": ""}
                            }
                        )
                    except:
                        await self.MonDepositGrowth.update_one(
                            {},
                            {
                                "$unset":{f"Deposit_Growth.{token}": ""}
                            }
                        )
                        await self.ActiveMonitoredTokens.update_one(
                            {},
                            {
                                "$unset":{f"Monitored_Token.{token}": ""}
                            }
                        )
                    logger.info(f"Token {token} Removed From Monitoring List")

                    break # Stop after Getting A successful Match
                else:
                    pass
            except ValueError  as e:
                pass
            except Exception as e:
                pass

    

    async def Await_Order_from_Telegram(self)->None:
        """
        This funtions accepts and process trade order from Telegram
        """
        logger.info('Awaiting Order From Telegram')
        while True:
            try:
                _,order = await self.db_connect_FourMeme.blpop('TelegramOrders') # Await additon of token
            except:
                _,order = await self.db_connect_FourMeme.blpop('TelegramOrders') # Await additon of token
            

            if order:
                order = order.decode()
                order = ast.literal_eval(order)

                if order['trade_direction'].upper() == 'buy'.upper():
                    asyncio.create_task(self.buy(order['token_address'],order['amount']))
                    logger.info(f"Buy Order Received From Telegram For Token {order['token_address']}")
                else:
                    asyncio.create_task(self.sell(order['token_address'],order['amount'],book_profit=False, tele=True)) 
                    logger.info(f"Sell Order Received From Telegram For Token {order['token_address']}")
    
    # -- Approving Router Contract ---
    async def approvals(self,token:str, direction:str, router:bool=False)->bool:
        logger.info('Approving Router Contracts.....')
        tx_hash = await self.token.approve(token,router,2**256 - 1)
        approve_receipt = await self.trade.wait_for_transaction(tx_hash, timeout=60)
        return True
         

    async def buy(self,token:str, mon_amount:str|int):
        """
            This function Handles the buying of token
        """
        logger.info(f'Buying  A Token: {token}')

        # Adding tken initial price to be o for new price comparison
        token = self.rpc_connection.to_checksum_address(token)
        if token not in self.tokens_previous_price:
            self.tokens_previous_price[token] = 0.000000000000000000000000001234
            
        try:
            mon_amount = parseMon(float(mon_amount))
            buy_quote = await self.trade.get_amount_out(token, (mon_amount), is_buy=True)
            
            buy_params = BuyParams(
                token=token,
                to= self.trade.address,
                amount_in=mon_amount,
                amount_out_min=calculate_slippage(buy_quote.amount, 5),
                deadline=None  # Auto-sets to now + 120 seconds
            )
            tx = await self.trade.buy(buy_params, buy_quote.router)

            logger.info(f'Waiting For Transaction {tx} To Mine')
            receipt = await self.trade.wait_for_transaction(tx, timeout=60)
            logger.info(f'Transaction Succeded!')
            asyncio.create_task(self.ProcessLog(tx,receipt,'buy',token,mon_amount))
            asyncio.create_task(self.approvals(token,'BUY',buy_quote.router))

        except Exception as e:
            logger.error(F"Couldnt Send A Buy Transaction: Issue {e}")
            async with telegram.Bot(self.bot_token) as bot:
                await bot.send_message(
                    chat_id=os.getenv('CHAT_ID'),
                    text=(f"⚠️ *Buy Order Failed!*\n\n"
                          f"🔥Token: `{token}`\n"
                          f"💵Amount: `{mon_amount/10**18}` BNB\n"
                          f"Issue: `{e}`"),
                    parse_mode=telegram.constants.ParseMode.MARKDOWN
                )



    async def sell(self,token:str, token_amount:str|int,book_profit:bool=False,tele=False)->None:
        
        """
            This function handles the token selling
        """
        logger.info(f'Selling A Token: {token}')
        balance = int(token_amount) / 1e18
        truncate_balance = self.truncate_to_first_decimal(balance)
        token_amount =  int(Decimal(str(truncate_balance)) * (10 ** 18))
        try:
            sell_quote = await self.trade.get_amount_out(token, int(token_amount), is_buy=False)
            sell_params = SellParams(
                token=token,
                to=self.trade.address,
                amount_in=int(token_amount),
                amount_out_min=calculate_slippage(sell_quote.amount, 5),
                deadline=None
            )

            # -- Checking foor The approval of the router used for selling --
            allowance = await self.token.get_allowance(token,sell_quote.router)
            if allowance < int(token_amount):
                processed = await self.approvals(token, 'SELL', sell_quote.router)
                processed = True
            else:
                processed = True

            if not processed:
                return None
            
            logger.info('Selling Router Approved')
            tx = await self.trade.sell(sell_params, sell_quote.router)

            logger.info(f'Waiting For Transaction {tx} To Mine')
            receipt = await self.trade.wait_for_transaction(tx, timeout=60)
            
            if not receipt:
                return None
            
            logger.info(f'Transaction Succeded!')
            try:
                token_order_detail = await self.ActiveOrders.find_one(
                    {},
                    {f"Active_Orders.{token}":1}
                )
            except:
                token_order_detail = await self.ActiveOrders.find_one(
                    {},
                    {f"Active_Orders.{token}":1}
                )
            
            if "Active_Orders" not in token_order_detail :
                return None
            
            token_order_detail = token_order_detail.get('Active_Orders')

            # Tagging This order Completed
            if not book_profit and not tele:
                try:
                    await self.ActiveOrders.update_one(
                        {},
                        {
                            "$unset":{f"Active_Orders.{token}": ""}
                        }
                    )
                except:
                    await self.ActiveOrders.update_one(
                        {},
                        {
                            "$unset":{f"Active_Orders.{token}": ""}
                        }
                    )

                
                logger.info(f'{token[:5]}.....{token[-7:]} Removed From Active Trades!')
                # -- Removing this token from the list of monitored token -- 
                tokens = [ ]
                fetch_token = True
                while fetch_token:
                    try:
                        monitored_token = await self.db_connect_FourMeme.lpop(self.TradedTokenList) 
                    except:
                        monitored_token = await self.db_connect_FourMeme.lpop(self.TradedTokenList) 

                    if monitored_token:
                        monitored_token = self.rpc_connection.to_checksum_address(token)
                        if token != monitored_token:
                            tokens.append(monitored_token)
                    else:
                        fetch_token = False
                        for token in tokens:
                            try:
                                await self.db_connect_FourMeme.rpush(self.TradedTokenList,token)
                            except:
                                await self.db_connect_FourMeme.rpush(self.TradedTokenList,token)
                        
                token_order = token_order_detail.get(token)
                if token_order:
                    token_order['Trade_Cycle'] = 'Completed'
                    token_order["sell_order_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    await self.db_connect_FourMeme.hset(self.CompletedOrders, mapping={token:str(token_order)})
        
            asyncio.create_task(self.ProcessLog(tx,receipt,'sold',token,float(token_amount),tele))
                   
        except Exception as e:
            logger.error(f'Couldnt Send A Sell Transaction : Issue {e}')
            async with telegram.Bot(self.bot_token) as bot:
                await bot.send_message(
                    chat_id=os.getenv('CHAT_ID'),
                    text=(f"⚠️ *Sell Order Failed!*\n\n"
                        f"Token: `{token}`\n"
                        f"Amount: `{token_amount/ 10**18}`\n"
                        f"Issue: `{e}`"),
                    parse_mode=telegram.constants.ParseMode.MARKDOWN
                )
                
    
    def truncate_to_first_decimal(self,num: float) -> float:
        if num == 0:
            return 0.0

        if abs(num) >= 1:
            # For numbers >= 1, keep only first decimal digit
            return math.trunc(num * 10) / 10
        else:
            # For numbers < 1, find first significant digit after zeros
            exp = math.floor(math.log10(abs(num)))
            scaled = num / (10 ** exp)
            truncated = math.trunc(scaled * 10) / 10
            return truncated * (10 ** exp)

    async def ProcessLog(self,tx_hash:str,reciept:dict, direction:str, token:str, amoount_in:str|int,tele=False)-> None:
        """
            Processing Transaction Log data
        """
        logger.info('Processing Trade Log Data ')

        if direction.upper() == 'buy'.upper():
           asyncio.create_task(self.process_buys_event_log(tx_hash,reciept, direction, token, amoount_in,tele))
        elif direction.upper() == 'sold'.upper():
            asyncio.create_task(self.process_sells_event_log(tx_hash,reciept, direction, token, amoount_in,tele))
        else:
            if reciept:
                return True
            else:
                False

    async def process_buys_event_log(self,tx_hash:str,reciept:dict, direction:str, token:str, amoount_in:str|int,tele=False)->None:
        """
            process event log for buys events
        """
        for log_data in reciept['logs']:
                if log_data['address'].upper() == token.upper():
                    data = log_data['data']

                    amount_bought = int(data.hex(),16) 
                    price_bought = amoount_in / amount_bought
                    stop_loss = price_bought * ( 1 - (self.stop_loss/100))
                    token = self.rpc_connection.to_checksum_address(token)

                    
                    token_order_detail =  {
                        'entry_price': str(price_bought),
                        'trail_price': str(price_bought),
                        'Capital' :str(amoount_in/10**18),
                        'stop_loss': str(stop_loss),
                        'trail_percent': 20, # percent,
                        'token_amount': str(amount_bought),
                        'tx_hash': tx_hash,
                        "buy_order_time":datetime.now().strftime("%Y-%m-%d %H:%M"),
                        'Trade_Cycle': 'Active'
                    }
                    
                    active_orders_datas = await self.ActiveOrders.find_one({})
                    if not active_orders_datas:
                        order_data = {}
                        await self.ActiveOrders.insert_one({"Active_Orders": order_data})

                    try:
                        await self.ActiveOrders.update_one(
                            {},
                            {
                                "$set": {f"Active_Orders.{token}": token_order_detail}
                            }
                        )

                        await self.db_connect_FourMeme.rpush(self.TradedTokenList,str(token))
                        await self.db_connect_FourMeme.rpush(self.signal,str(token))
                    except:
                        await self.ActiveOrders.update_one(
                            {},
                            {
                                "$set": {f"Active_Orders.{token}": token_order_detail}
                            }
                        )
                        # await self.db_connect_FourMeme.hset(self.ActiveOrders,mapping=forward)
                        await self.db_connect_FourMeme.rpush(self.TradedTokenList,str(token))
                        await self.db_connect_FourMeme.rpush(self.signal,str(token))
                
                    logger.info(f'Token Bought {token} at Price {price_bought} with Stop Loss {stop_loss}')

                    try:
                        await self.db_connect_FourMeme.hset(self.CompletedOrders, mapping={token : str(token_order_detail)}) # just to have a record of all bought token
                    except:
                        await self.db_connect_FourMeme.hset(self.CompletedOrders, mapping={token : str(token_order_detail)}) # just to have a record of all bought token
                    
                    async with telegram.Bot(self.bot_token) as bot:
                        await bot.send_message(
                            chat_id=os.getenv('CHAT_ID'),
                            text=(f"🟢 *New Trade Executed!*\n\n"
                                  f"🔥Token: `{token}`\n"
                                  f"💵Amount Bought: `{amount_bought/10**18}`\n"
                                  f"📈Entry Price: `{price_bought:.6f}` BNB\n"
                                  f"⛔Stop Loss Price: `{stop_loss:.6f}` BNB\n"
                                  f"📜Transaction Hash: [View on Explorer](https://bscscan.com/tx/0x{tx_hash})"),
                            parse_mode=telegram.constants.ParseMode.MARKDOWN
                        )
                    

    async def process_sells_event_log(self,tx_hash:str,reciept:dict, direction:str, token:str, amoount_in:str|int,tele=False)-> None:
        """
            process event log for sell event
        """ 
        logs = reciept.get('logs')
        if not logs:
            return None
        bnb_bought = self.fetch_bnb_bought(logs)
        if not bnb_bought:
            return None

        try:
            token_order = await self.ActiveOrders.find_one(
                {},
                {f"Active_Orders.{token}":1}
            )
            # orders = await self.db_connect_FourMeme.hget(self.ActiveOrders,token)
        except:
            # orders = await self.db_connect_FourMeme.hget(self.ActiveOrders,token)
            token_order = await self.ActiveOrders.find_one(
                {},
                {f"Active_Orders.{token}":1}
            )

        if token_order and "Active_Orders" in token_order:
            active_order = token_order.get('Active_Orders')
            token_order_detail = active_order.get(token)
            # orders = orders.decode()
            # orders = ast.literal_eval(orders)
            # token_orders = orders.get(token,)
            if token_order_detail  and 'Book_Profit' in token_order_detail:
                selling_reason = 'Book Pofit'
                # remove = token_orders.pop('Book_Profit')

                try:
                    await self.ActiveOrders.update_one(
                        {},
                        {
                            "$unset" : {f"Active_Orders.{token}.Book_Profit" : ""}
                        }
                    )
                    
                    # await self.db_connect_FourMeme.hset(self.ActiveOrders,mapping={token : str(orders)})
                except:
                    # await self.db_connect_FourMeme.hset(self.ActiveOrders,mapping={token : str(orders)})
                    await self.ActiveOrders.update_one(
                        {},
                        {
                            "$unset" : {f"Active_Orders.{token}.Book_Profit" : ""}
                        }
                    )
                
                pnl = float(bnb_bought - float(token_order_detail.get('Capital','0')))
            else:
                selling_reason = 'Exiting Fully'
                pnl = bnb_bought
        else:
            pnl = bnb_bought
            selling_reason = 'Exiting'

        
        if tele:
            selling_reason = 'Telegram Sales'
        
        async with telegram.Bot(self.bot_token) as bot:
            await bot.send_message(
                chat_id=os.getenv('CHAT_ID'),
                text=(f"🔴 *Trade Executed!*\n\n"
                        f"🔥 Token: `{token}`\n"
                        f"📉 Amount Sold: `{int(amoount_in) / 1e18}`\n"
                        f"💵 BNB Received: {bnb_bought/ 1e18:.10f} BNB\n"
                        f"📉 Selling Reason: {selling_reason}\n"
                        f"🧾 PNL: {pnl/ 1e18:.10f}\n"
                        f"Transaction Hash: [View on Explorer](https://bscscan.com/tx/0x{tx_hash})"),
                parse_mode=telegram.constants.ParseMode.MARKDOWN
            )

    
    # Fetch bnb Gotten  After Selling A Token
    def fetch_bnb_bought(self,logs:dict):
        for log in logs:
            topics =  log.get('topics')
            if not topics:
                continue

            topic0_byte = topics[0]
            if hasattr(topic0_byte,'hex'):
                topic0 = '0x' + topic0_byte.hex()
            elif topic0_byte.startswith('0x'):
                topic0 = topic0_byte
            else:
                topic0 = '0x'+  topic0_byte
            
            data_byte = log.get('data')
            if not data_byte:
                return None

            if topic0.lower() == self.curve_sell_topic.lower():

                token,account,price,amount,cost,fee,offers,funds = decode(
                    ['address','address','uint256','uint256','uint256','uint256','uint256','uint256'],
                    data_byte
                )
                bnb_bought = cost
                return bnb_bought
            elif topic0.lower() == self.pancake_swap_pool_topic.lower():
                amount0In, amount1In, amount0Out, amount1Out  = decode(
                    ['uint256', 'uint256', 'uint256', 'uint256'],
                    data_byte
                )

                if amount0Out or amount1Out:
                    if amount0Out:
                        bnb_bought = amount0Out
                    else:
                        bnb_bought = amount1Out
                return bnb_bought
               

    async def AwaitSignal(self)->None:
        """ 
            Whenever a new buy Trade is taken this function will detect the token traded and start the process of monitong the token price
            A signal (the token address) is added to the list 'signal' in redis db this got pick up by this function and start the process. 
        """
        logger.info('Awaiting Signals (Token Address)')
        try:
            token_orders =  await self.ActiveOrders.find_one({})
        except:
            token_orders =  await self.ActiveOrders.find_one({})
            
        if token_orders:
            active_orders = token_orders.get('Active_Orders')
            if active_orders:
                active_orders = list(active_orders.keys())

                logger.info('Resuming Monitoring of Active Trades From Previous Run')
                for  index, token in enumerate(active_orders):
                    try:
                        added = await self.db_connect_FourMeme.rpush(self.TradedTokenList,token)
                    except:
                        added = await self.db_connect_FourMeme.rpush(self.TradedTokenList,token)

                    if index + 1 == len(active_orders):
                        signaled = await self.db_connect_FourMeme.rpush(self.signal,token)
            else:
                logger.info('No Active Trades From Previous Run')
        else:
            logger.info('No Active Trades From Previous Run')

        
        while True:
            try:
                _,token = await self.db_connect_FourMeme.blpop(self.signal) # Await additon of token
            except:
                _,token = await self.db_connect_FourMeme.blpop(self.signal) # Await additon of token

            if token:
                tokens = [ ]
                fetch_token = True
                while fetch_token:
                    try:
                        token = await self.db_connect_FourMeme.lpop(self.TradedTokenList) 
                    except:
                        token = await self.db_connect_FourMeme.lpop(self.TradedTokenList) 

                    if token:
                        if token not in tokens:
                            token = self.rpc_connection.to_checksum_address(token.decode())
                            tokens.append(token)
                    else:
                        fetch_token = False
                        tokens = list(set(tokens)) # removing duplicate if any
                        self.tokens_to_monitor_price = tokens
                        asyncio.create_task(self.Monitor_curve_Trade()) # start monitoring the curve tokens traded
                        asyncio.create_task(self.monitor_dex_trade(tokens)) # start monitoring the dex tokens traded

                        for token in tokens:
                            try:
                                await self.db_connect_FourMeme.rpush(self.TradedTokenList,token)
                            except:
                                await self.db_connect_FourMeme.rpush(self.TradedTokenList,token)
                        
    async def Monitor_curve_Trade(self)->None:
        """
            This function Monitors the buy/sell event for the traded tokens
        """
        logger.info('Monitor Curve Tokens  Traded Started')
        while True:
            try:
                self.stream_curve_trade.subscribe(
                [EventType.MANAGER_2_BUY, EventType.MANAGER_2_SELL],
                token_addresses=self.tokens_to_monitor_price  
                )

                async for event in self.stream_curve_trade.events():
                    logger.info(f"Event: {event['eventName']}")      # "BUY" or "SELL"

                    direction = event['eventName']
                    token = event['token']
                    
                    new_price = float(int(event['price']) / 1e18)
                   
                    token = self.rpc_connection.to_checksum_address(token)
                    trade_data = {
                        'token' : token,
                        'new_price':new_price
                    }   

                    initiai_price = self.tokens_previous_price[token]
                    percent_increase =((float(new_price) - float(initiai_price)) / float(initiai_price) ) * 100 

                    # -- if percentage price increase is greater or equal to N then we match this new price.
                    # -- This is a mechanism tto avoid overwhelming db reading.--
                    if abs(percent_increase) >= 1:
                        self.tokens_previous_price[token] = new_price # Update the token price for next run
                        asyncio.create_task(self.MatchSignal(trade_data)) # call the match signal function to check if stop loss or trail need to be updated
                    else:
                        logger.info(f'Token(Curve) {token[:5]}.....{token[-7:]} New Price Is Below Threshold For Matchin. Last Price: {initiai_price}. New Price: {new_price}')
                   
            except Exception as e:
                logger.error(f'Error in Socket Issue :{e}')
                continue

    async def monitor_dex_trade(self,token:str)->None:
        """
        This function monitors the traded token event on DEX. buys/sell
        """
        logger.info('Monitor Dex Trade Started')
        while True:
            try:
                self.stream_dex_trade.subscribe_tokens(token_addresses=token,
                                                       event_types=[EventType.v2_SWAP]
                                                       )
                
                # Check if there is a Pool, This Avoid Reconnecting  ws if No Pool
                pool = await self.stream_dex_trade._discover_pools(self.stream_dex_trade.w3)
                if not pool:
                   logger.info('Token(s) Has Not Migrated To PancakeSwap Dex Yet')
                   await asyncio.sleep(60)
                   continue
           
                async for event in self.stream_dex_trade.events():
                    get_log = await self.rpc_connection.eth.get_transaction_receipt(event['transactionHash'])
                    log_data = get_log['logs']
                    for log in log_data:
                        address = self.rpc_connection.to_checksum_address(log['address'])
                        if address in  self.tokens_to_monitor_price:
                            token = address
                            break
                    
                    
                    new_price = event['price']   
                    trade_data = {
                        'token' : token,
                        'new_price':new_price
                    }

                    initiai_price = self.tokens_previous_price[token]
                    percent_increase =((float(new_price) - float(initiai_price)) / float(initiai_price) ) * 100 

                    # -- if percentage price increas is greater or equal to N then we match this new price.
                    # -- This is a mechanism tto avoid overwhelming db reading.--
                    if abs(percent_increase) >= 0.5:
                        self.tokens_previous_price[token] = new_price # Update the token price for next run
                        asyncio.create_task(self.MatchSignal(trade_data)) # call the match signal function to check if stop loss or trail need to be updated
                    else:
                        logger.info(f'Token(Dex) {token[:5]}.....{token[-7:]} New Price Is Below Threshold For Matching. Last Price: {initiai_price}. New Price: {new_price}')
                   
            except Exception as e:
                logger.error(f'Error in Socket Issue :{e}')
                continue


    # Match the event from the monitored token for user stop loss and take profit
    async def MatchSignal(self,trade_data:dict)->None:
        logger.info('Matching Signal For Stop Loss or Trail Update')

        token = trade_data['token']
        new_price = float(trade_data['new_price'])
        try:
            token_order = await self.ActiveOrders.find_one(
                {},
                {f"Active_Orders.{token}": 1}
            )
        except:
            token_order = await self.ActiveOrders.find_one(
                {},
                {f"Active_Orders.{token}": 1}
            )

        if token_order and "Active_Orders" in token_order:
            order = token_order.get('Active_Orders').get(token)
            if not order:
                return

            stop_loss_price = float(order['stop_loss'])
            logger.info(f'New Price {new_price} Stop Loss Price {stop_loss_price}')

            # stop loss Condition
            if new_price < stop_loss_price:
                balance = await self.token.get_balance(token,self.token.address)
                if balance:
                    
                    asyncio.create_task(self.sell(token,balance))
                    logger.info(f'Stop Loss Triggered For Token {token} at Price {new_price} with Stop Loss Price {stop_loss_price}')
            else:
                entry_price = float(order['entry_price'])
                take_profit_percent = ((new_price - entry_price)/ entry_price ) * 100 # Take profit when price is above entry price by greater than 50%
                trail_price = float(order['trail_price'])

                if new_price > float(trail_price):
                    if take_profit_percent >= 30 and 'profit_booked' not in order: # 30 %
                        balance = await self.token.get_balance(token,self.token.address)
                        if balance:
                            half_of_balance = int(balance)
                            asyncio.create_task(self.sell(token,half_of_balance,book_profit=True, tele=False)) # book profit on half the balance
                            order['profit_booked'] = new_price # to avoid repitition of profit booking
                            order['Book_Profit'] = True
                            logger.info(f'Profit Booked For Token {token} at Price {new_price} with Take Profit Percent {take_profit_percent}')

                    logger.info(f'Updating Stop Loss and Trail Price For Token {token}')
                    # update the stop loss and trail price
                    stop_loss = new_price * ( 1 - (self.stop_loss/100))
                    # stop_loss = (float(order['trail_percent']) * new_price ) / 100
                    order['stop_loss'] = str(stop_loss)
                    order['trail_price'] = str(new_price)

                    try:
                        await self.ActiveOrders.update_one(
                            {},
                            {
                                "$set":{f"Active_Orders.{token}":order}
                            }
                        )
                    except:
                        await self.ActiveOrders.update_one(
                            {},
                            {
                                "$set":{f"Active_Orders.{token}":order}
                            }
                        )
        





                            
                            










    

    

    

        







    





