import ast
import asyncio
import logging
import os,sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import telegram
from web3 import AsyncWeb3,AsyncHTTPProvider, Web3
from redis.asyncio import Redis
from db_connect.db_connector import db_connector
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes,ConversationHandler,filters,MessageHandler
from datetime import datetime
from utils.util import load_abis
from utils.constants import CONTRACTS

from Four_sdk import get_amount_out,load_abis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s : %(message)s"
)

load_dotenv()
ABI = load_abis()

db_connect= db_connector(max_connections=1)
db_connect_Naddy = db_connect.Redis_connect()
class Essentials:
    def __init__(self):
        self.rpc_connection = AsyncWeb3(AsyncHTTPProvider(os.getenv('RPC_FOR_TELE_BSC')))
        self.token = os.getenv('TELE_TOKEN_BSC')
        self.profile  = os.getenv('PROFILE')
        self.WAITING_FOR_TOKEN = 0
        self.WAITING_FOR_TRADE_DIRECTION = 1
        self.WAITING_FOR_AMOUNT = 2
        self.WAITING_FOR_EXECUTE = 3
        

essential = Essentials()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = str(update.effective_user.name)[1:]
    chat_id = update.effective_chat.id

    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🚀 🚀 Welcome To FourMeme Trading Bot  {username}\n Use /help To See Bot Commands"

    )
   
async def AccesAuth(context: ContextTypes.DEFAULT_TYPE, chat_id: int, update: Update,username:str)-> bool:
    logging.info('Checking For User Authorization')

    try:
        user_profile = await db_connect_Naddy.hget(essential.profile,username)
    except Exception as e:
        return False
   
    if not user_profile:
        message = await context.bot.send_message(
                chat_id=chat_id,
                text='⚠️ Unauthorise Access!!'
            )
        asyncio.create_task(delete_message(context,chat_id,update,message))
        return ConversationHandler.END

    return True
    
    
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    username = update.effective_user.name

    auth = await AccesAuth(context,chat_id,update,f"{username}:{user_id}")
    help_text = (
        "Here are the available commands:\n\n"  
        "*Commands:*\n"
        "*/start* - Start interacting with the bot.\n"
        "*/help* - Show This help message.\n"
        "*/Trade* - Start a new trade (enter token and choose mode).\n"
        "*/completed* - Get Your Completed Trades\n"
        "*/session* - Get Your Active Orders\n"
        "*/cancel* - Cancel Order Setup"
        "\nType any command to use it!"
    )
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=help_text,
        parse_mode="Markdown"
    )
    asyncio.create_task(delete_message(context,chat_id,update,message))



async def tradeInSesion(update:Update, context:ContextTypes.DEFAULT_TYPE)->None:
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    username = update.effective_user.name

    auth = await AccesAuth(context,chat_id,update,f"{username}:{user_id}")
    if not auth:
        return ConversationHandler.END
    trade_in_session = await db_connect_Naddy.hgetall("ActiveOrders")

    
    data = [ ]
    if trade_in_session:
        for  token , order_byte in trade_in_session.items():
            order = order_byte.decode()
            try:
                order = ast.literal_eval(order)

                entry_price = order['entry_price']
                trailed_price = order['trailed_price']
                stop_loss_price = order['stop_loss']
                token_amount = order['token_amount']
                order_time = order['order_time']
                tx_hash = order['tx_hash']
                Trade_Cycle = order['Trade_Cycle']


                trades_data = (
                    "\n"
                    f"🔥*Token Address*     : {token}\n"
                    f"✅*Trade Status*: {Trade_Cycle}\n"
                    f"📈*Entry Price* : {entry_price}\n"
                    f"📉*Trailed Price* : {trailed_price}\n"
                    f"⛔*Stop Loss Price* : {stop_loss_price}\n"
                    f"💵*Amount Bought*: {token_amount}\n"
                    f"🕒*Trade Time*: {order_time}\n"
                    f"📜[Tx Hash]https://testnet.monadexplorer.com/tx/{tx_hash})"
                    )
                    
                data.append(trades_data)
            except:
                pass

        if data:
            trade_in_session = ' '.join(data)

            logging.info('Sending Session Trade To User!')
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=trade_in_session,
                parse_mode='Markdown'
            )
            asyncio.create_task(delete_message(context,chat_id,update,message))
    else:
        message = await context.bot.send_message(
            chat_id=chat_id,
            text='❎ You Have No Trades In Session Yet!'
        )
        asyncio.create_task(delete_message(context,chat_id,update,message))

# Show Completed Trades
async def completedTrade(update:Update, context:ContextTypes.DEFAULT_TYPE)->None:
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    username = update.effective_user.name

    auth = await AccesAuth(context,chat_id,update,f"{username}:{user_id}")
    if not auth:
        return ConversationHandler.END
    completed_trades = await db_connect_Naddy.hgetall('CompletedOrders')
    
    data = [ ]
    if completed_trades:
        for  token , order_byte in completed_trades.items():
            order = order_byte.decode()

            try:
                order = ast.literal_eval(order)

                entry_price = order['entry_price']
                trailed_price = order['trailed_price']
                stop_loss_price = order['stop_loss']
                token_amount = order['token_amount']
                order_time = order['order_time']
                tx_hash = order['tx_hash']
                Trade_Cycle = order['Trade_Cycle']


                trades_data = (
                    "\n"
                    f"🔥*Token Address*     : {token}\n"
                    f"✅*Trade Status*: {Trade_Cycle}\n"
                    f"📈*Entry Price* : {entry_price}\n"
                    f"📉*Trailed Price* : {trailed_price}\n"
                    f"⛔*Stop Loss Price* : {stop_loss_price}\n"
                    f"💵*Amount Bought*: {token_amount}\n"
                    f"🕒*Trade Time*: {order_time}\n"
                    f"📜[Tx Hash]https://testnet.monadexplorer.com/tx/{tx_hash})"
                    )
                
                data.append(trades_data)
            except:
                pass

        if data:
            completed_trades = ' '.join(data)

            logging.info('Sending Completed Trade To User!')
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=completed_trades,
                parse_mode="Markdown"
            )
            asyncio.create_task(delete_message(context,chat_id,update,message))
        else:
            logging.info('No Data')
    else:
        message = await context.bot.send_message(
            chat_id=chat_id,
            text='❎ You Have No Completed Trade Yet!'
        )
        asyncio.create_task(delete_message(context,chat_id,update,message))
  

""" To Do   Add functio to get user failed Trades"""

# Start Trade Conversation
async def startTrade(update:Update, context:ContextTypes.DEFAULT_TYPE)->None:
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    username = update.effective_user.name

    auth = await AccesAuth(context,chat_id,update,f"{username}:{user_id}")
    if not auth:
        return ConversationHandler.END
    user_profile = await db_connect_Naddy.hget(essential.profile,f"{username}:{user_id}")


    user_data = user_profile.decode()
    user_data = ast.literal_eval(user_data) 
    user_address = user_data['address']
    context.user_data['user_address'] = user_address

    message = await context.bot.send_message(
                chat_id=chat_id,
                text="\U0001FA99 Enter FourMeme's Token To Trade"
            )
    asyncio.create_task(delete_message(context,chat_id,update,message))

    return essential.WAITING_FOR_TOKEN

# Verify if the token is EVM And Then Give Options to buy or sell
async def verifyToken(update:Update, context:ContextTypes.DEFAULT_TYPE)->None:
    
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    username = update.effective_user.name

    # Verify If User is Authorized
    auth = await AccesAuth(context,chat_id,update,f"{username}:{user_id}")
    if not auth:
        return ConversationHandler.END
    
    user_profile = await db_connect_Naddy.hget(essential.profile,f"{username}:{user_id}")
    user_data = user_profile.decode()
    user_data = ast.literal_eval(user_data) 
    user_address = user_data['address']
    context.user_data['user_address'] = user_address


    token = update.message.text.strip()

    if not token or ( not token.startswith('0x')):
        message = await context.bot.send_message(
                chat_id=chat_id,
                text="🚫 Only FourMeme Token Is Allowed! Re-Enter Token"
            )
        asyncio.create_task(delete_message(context,chat_id,update,message,True))
        return essential.WAITING_FOR_TOKEN 
    
    amount_in = 1 * 10**18
    try:
        http_url = os.getenv('RPC_FOR_TELE_BSC')
        result = await get_amount_out(http_url,token,amount_in,True)
        # lens_contract =  essential.rpc_connection.eth.contract(address=Web3.to_checksum_address(CONTRACTS['lens']),abi=ABI['lens'])
        # result = await lens_contract.functions.getAmountOut(
        #                     Web3.to_checksum_address(token),
        #                     int(amount_in),
        #                     True
        #                     ).call()
        abis = load_abis()
        token_contract =  essential.rpc_connection.eth.contract(Web3.to_checksum_address(token),abi=abis['erc20Abi'])
        balance = await token_contract.functions.balanceOf(user_address).call()
        amount_out = result.amount
        if amount_out:
            price = amount_in / amount_out
            user_token_amount_in_mon = price * (balance / 10**18)

            update_user = (
                f"✅ Token Verified!\n"
                f"💰 Your Balance: {balance/10**18}\n"
                f"👜 BNB Value For Token: {user_token_amount_in_mon}\n"
                f"🟢 | 🔴 Choose Trade Direction"
            )
        else:
            update_user = f"✅ Token Verified!\nChoose Trade Direction"

                             
        logging.info('Verifing If The Token is  A FourMeme Bsc Token')
        
        keyboard = [
            [InlineKeyboardButton('🔙Go Back',callback_data='back')],
            [
                InlineKeyboardButton('🟢 BUY ⬆️',callback_data='buy'),InlineKeyboardButton('🔴 SELL ⬇️',callback_data='sell')
            ]  
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=update_user,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        context.user_data['token'] = token
        context.user_data['user_session'] =  message.message_id

        asyncio.create_task(delete_message(context,chat_id,update,message))
        return essential.WAITING_FOR_TRADE_DIRECTION

    except Exception as e:
        logging.error(f'This is an Issue loading this Token {e}')
        message = await context.bot.send_message(
                chat_id=chat_id,
                text="🚫 Only FourMeme Token Is Allowed! Re-Enter Token"
            )
        asyncio.create_task(delete_message(context,chat_id,update,message,True))
        return essential.WAITING_FOR_TOKEN 
        
    
   


async def recieveTradeDirection(update:Update, context:ContextTypes.DEFAULT_TYPE)->None:

    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    username = update.effective_user.name

    # verify If User is Authorized
    auth = await AccesAuth(context,chat_id,update,f"{username}:{user_id}")
    if not auth:
        return ConversationHandler.END

    query = update.callback_query
    Trade_direction = query.data

    if Trade_direction == 'back':
        message = await context.bot.send_message(
                    chat_id=chat_id,
                   text='\U0001FA99 Enter FourMeme Evm Token To Trade'
                )
        # asyncio.create_task(delete_message(context,chat_id,update,message))
        
        return essential.WAITING_FOR_TOKEN


    trade_direction_id = query.message.message_id
    user_session = context.user_data.get('user_session')
    user_address = context.user_data.get('user_address')
    
    # Ensure the callback is from the correct interaction session to prevent conflicts
    if user_session and user_session == trade_direction_id:
        await query.answer()
        
        token = context.user_data.get('token')
        context.user_data['trade_direction'] = Trade_direction
    
        if Trade_direction  == 'buy':
            balance = await essential.rpc_connection.eth.get_balance(user_address)
            balance =  essential.rpc_connection.from_wei(int(balance),'ether')


            amount_prompt =  'Enter BNB Amount'
            prompt = (
                f"💰*Your BNB Balance*: {balance} BNB\n"
                f"💸*Enter BNB Amount To Trade With ⬇️*"
            )
        else:
            token_contract = essential.rpc_connection.eth.contract(address=Web3.to_checksum_address(token), abi=ABI['erc20Abi'])
            token_balance =  await token_contract.functions.balanceOf(user_address).call()

            if token_balance:
                decimal =  await token_contract.functions.decimals().call()
                balance = token_balance / 10** decimal
                context.user_data['decimal'] = decimal
            else:
                balance = 0
            
            if token_balance == 0:
                message = await context.bot.send_message(
                    chat_id=chat_id,
                    text='🚫 Sorry You Have No Token To Sell!!',
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                asyncio.create_task(delete_message(context,chat_id,update,message))
                return ConversationHandler.END
                
            context.user_data['user_token_balance'] = balance
            symbol =  await token_contract.functions.symbol().call()
            amount_prompt = f"Token Amount To Sell"
            prompt = ( 
               f"💰*Your Token Balance*: {balance}\n"
               f'💸*Enter Token Amount To Sell ⬇️*'
            )

        first_amount = {
            f"1 BNB" if Trade_direction == 'buy' else f"10,000 {symbol}": f"1" if Trade_direction == 'buy' else f"10000"
        }
        second_amount = {
            f"2 BNB" if Trade_direction == 'buy' else f"20,000 {symbol}" : f"2" if Trade_direction == 'buy' else f"20000"
            }
        
        first_amount_data = list(first_amount.keys())[0]
        first_amount_value = list(first_amount.values())[0]

        second_amount_data = list(second_amount.keys())[0]
        second_amount_value = list(second_amount.values())[0]

        keyboard = [
            [InlineKeyboardButton('Go Back',callback_data='dir-back')],
            [InlineKeyboardButton(first_amount_data, callback_data=first_amount_value),
            InlineKeyboardButton(second_amount_data,callback_data=second_amount_value),
            InlineKeyboardButton('enter',callback_data='enter')]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['amount_prompt'] = amount_prompt
        context.user_data['amount_goback'] = prompt

        message = await context.bot.send_message(
                chat_id=chat_id,
                text=prompt,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
       
        asyncio.create_task(delete_message(context,chat_id,update,message))
        return essential.WAITING_FOR_AMOUNT
    
    
async def TradeAmount(update:Update, context:ContextTypes.DEFAULT_TYPE)->None:

    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    username = update.effective_user.name

     # verify If User is Authorized
    auth = await AccesAuth(context,chat_id,update,f"{username}:{user_id}")
    if not auth:
        return ConversationHandler.END

    query = update.callback_query
    """ Check if the amount iss a callback or an amount """
    if query:
        amount_direction = query.data

        if amount_direction == 'dir-back': # This checks if user wants to go back
            keyboard = [
            [InlineKeyboardButton('🔙Go Back',callback_data='back')],
            [
                InlineKeyboardButton('🟢 BUY ⬆️',callback_data='buy'),
                InlineKeyboardButton('🔴 SELL ⬇️',callback_data='sell')
            ],
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await context.bot.send_message(
                        chat_id=chat_id,
                        text='🔎 Choose Trade Direction',
                        reply_markup=reply_markup
                    )
            asyncio.create_task(delete_message(context,chat_id,update,message))

            context.user_data['user_session'] = message.id
            return essential.WAITING_FOR_TRADE_DIRECTION
        elif amount_direction == 'enter': # Allow user to enter amount 
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=context.user_data.get('amount_goback'),
                parse_mode='Markdown'
            )
            return essential.WAITING_FOR_AMOUNT
       
    else:
        if update.message.text.upper() == 'ALL': # selling All
            user_token_balnace  = float(context.user_data.get('user_token_balance'))
            amount_direction = user_token_balnace * 0.97
        elif update.message.text.upper() == 'HALF': # selling half
            user_token_balnace = float(context.user_data.get('user_token_balance'))
            amount_direction = user_token_balnace / 2 
        else:
            amount_direction = update.message.text

    try:
        amount = float(amount_direction)
    except:
        message = await context.bot.send_message(
                chat_id=chat_id,
                text='🚫 Please Enter Numbers Only!'
            )
        asyncio.create_task(delete_message(context,chat_id,update,message))
        return essential.WAITING_FOR_AMOUNT

    """" Verify that the user has this amount to spend"""
    
    user_address = context.user_data.get('user_address')

    if context.user_data.get('amount_prompt') == 'Token Amount To Sell':
        logging.info('Checking User Token Balance')
       

        if user_address:
            token = context.user_data['token']
            decimal = context.user_data.get('decimal')

            token_balance = context.user_data.get('user_token_balance')

            if token_balance and float(token_balance) > amount:
                pass
            else:
                message = await context.bot.send_message(
                chat_id=chat_id,
                text='🚫Amount Exceeds Your Token Balance!\n Decrease Amount'
             )
                asyncio.create_task(delete_message(context,chat_id,update,message))
        
                return essential.WAITING_FOR_AMOUNT
    else: # This is for buy section

        if user_address:
            logging.info('Checking User BNB Balance')
            mon_balance = await essential.rpc_connection.eth.get_balance(user_address)
            mon_balance = essential.rpc_connection.from_wei(mon_balance,'ether')

            if mon_balance and mon_balance > amount:
                pass
            else:
                message = await context.bot.send_message(
                chat_id=chat_id,
                text='🚫Amount Exceeds Your BNB Balance!\nTop up Or Decrease Amount'
             )
                asyncio.create_task(delete_message(context,chat_id,update,message))
        
                return essential.WAITING_FOR_AMOUNT

    context.user_data['amount'] = amount 

    amount            = context.user_data.get('amount')
    token             = context.user_data.get('token')
    trade_direction   = context.user_data.get('trade_direction')
    
    
    confirm_order = (
                f"✅*Comfirm Trade Order*\n\n"
                f"🔥*Token*: {token}\n"
                f"💵*Amount*: {amount}\n"
                f"📉*Trade Direction*:{trade_direction.upper()}\n"
                )
    
    message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=confirm_order,
                parse_mode='Markdown'
                
            )
    asyncio.create_task(delete_message(context,chat_id,update,message))
    
    keyboard = [
        [InlineKeyboardButton('🔙 Go Back',callback_data='go-back')],
        [
            InlineKeyboardButton('Confirm & Execute',callback_data='execute'),
            InlineKeyboardButton('Cancel Trade Order',callback_data='cancel')
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await context.bot.send_message(
                chat_id=chat_id,
                text='🎯 Confirm Order!',
                reply_markup=reply_markup
            )
    asyncio.create_task(delete_message(context,chat_id,update,message))
    context.user_data['user_session'] = message.id
    return essential.WAITING_FOR_EXECUTE



async def ExecuteTrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    username = update.effective_user.name

    # verify If User is Authorized
    auth = await AccesAuth(context,chat_id,update,f"{username}:{user_id}")
    if not auth:
        return ConversationHandler.END

    query = update.callback_query
    execute_cancel = query.data

    if execute_cancel == 'go-back':
        message = await context.bot.send_message(
                chat_id=chat_id,
                text='Enter Amount To Trade !'
            )
        asyncio.create_task(delete_message(context,chat_id,update,message))
        return essential.WAITING_FOR_AMOUNT

    trade_amount_id = query.message.message_id
    user_session = context.user_data.get('user_session')
    
    if user_session and user_session == trade_amount_id:
        await query.answer()

        amount            = context.user_data.get('amount')
        token             = context.user_data.get('token')
        trade_direction   = context.user_data.get('trade_direction')
                
        order = {
            'trade_direction':trade_direction.upper(),
            'token_address': token,
            'amount': amount * 10** int(context.user_data.get('decimal')) if trade_direction.upper() == 'sell'.upper() else amount,
            "order_time":datetime.now().strftime("%Y-%m-%d %H:%M")
            }

        if execute_cancel == 'execute':
            logging.info(f"Sending Order For User {username}")
            await db_connect_Naddy.rpush('TelegramOrders',str(order))

            return ConversationHandler.END
        else:
            logging.info(f"{username} Cancelled Trade")

            message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🚫 Trade Order Cancelled."
            )
            asyncio.create_task(delete_message(context,chat_id,update,message))

            context.user_data.clear()
            return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🚫 Trade Order Cancelled."
    )
    asyncio.create_task(delete_message(context,chat_id,update,message))
    context.user_data.clear()
    return ConversationHandler.END


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🚫Unknown Command Use /help For commands"
    )
    asyncio.create_task(delete_message(context,chat_id,update,message,True))


async def delete_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, command_id,message_id,unknown=False):

    try:
        command_id = command_id.message.id
        message_id = message_id.id
    except:
        command_id = None
        message_id = message_id.id

    """Delete a message after a delay."""
    if unknown:
        await asyncio.sleep(10)
    else:
        await asyncio.sleep(60*10)
    try:
        if not command_id:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        else:
            await context.bot.delete_messages(chat_id=chat_id, message_ids=[message_id,command_id])
        logging.info(f"Deleted message {message_id} in chat {chat_id}")
    except:
        logging.error("Reason: Message may be older than 48 hours or bot lacks admin permissions.")

    




    
# if __name__ == "__main__":
class telegram_worker:
    def __init__(self):
        pass

    def start(self)-> None:

        application = ApplicationBuilder().token(essential.token).build()

        start_handler           = CommandHandler('start',start)
        session_handler         = CommandHandler('session',tradeInSesion)
        completedTrade_handler  = CommandHandler('completed',completedTrade)
        help__handler           = CommandHandler('help',help_command)
    

        trade_conversation = ConversationHandler(
            entry_points=[
                MessageHandler(filters.TEXT & ~filters.COMMAND,verifyToken),
                CommandHandler('Trade',startTrade)],
            states={
                essential.WAITING_FOR_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND,verifyToken)],
                essential.WAITING_FOR_TRADE_DIRECTION : [CallbackQueryHandler(recieveTradeDirection, pattern='^(buy|sell|back)$')],
                essential.WAITING_FOR_AMOUNT : [MessageHandler(filters.TEXT & ~filters.COMMAND,TradeAmount),
                                                CallbackQueryHandler(TradeAmount, pattern=f"^(enter|1|2|10000|20000|dir-back)$")],
                essential.WAITING_FOR_EXECUTE : [CallbackQueryHandler(ExecuteTrade, pattern='^(execute|cancel|go-back|go_back)$')],
            },
            fallbacks=[CommandHandler('cancel',cancel)]
        )

        unknown_text_command_handler    = MessageHandler(filters.TEXT,unknown)

        application.add_handler(start_handler)
        application.add_handler(session_handler)
        application.add_handler(completedTrade_handler)
        application.add_handler(trade_conversation)
        application.add_handler(help__handler)
        application.add_handler(unknown_text_command_handler)

        application.run_polling()
        
