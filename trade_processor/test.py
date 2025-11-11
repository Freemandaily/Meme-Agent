from nadfun_sdk import Trade, BuyParams, SellParams, calculate_slippage,parseMon,Token
import asyncio



print('helll')





from web3 import Web3

# Embed the RPC URL
rpc_url = "https://dimensional-compatible-frost.monad-testnet.quiknode.pro/6bea81bb2833de4a386d6708fa1113e6beef3243/"

# Initialize Web3 with the RPC URL
web3 = Web3(Web3.HTTPProvider(rpc_url))

# # Check connection
# if not web3.is_connected():
#     print("Failed to connect to Monad Testnet. Check RPC URL or internet.")
#     exit(1)
# else:
#     print("Connected to Monad Testnet")

# # Define the transaction from your payload
# transaction = {
#     "from": "0x91F40E6Ce86Cd2eE99Dab50E43fad1CD05ac9D6f",
#     "to": "0x4F5A3518F082275edf59026f72B66AC2838c0414",
#     "value": "0x39696f3392000",  # ~0.01 testnet ETH
#     "data": "0x6df9e92b00000000000000000000000000000000000000000000054d0370a6161b914a950000000000000000000000004212ec483d27cf22e9cbd15d654bcbf5867953a000000000000000000000000091f40e6ce86cd2ee99dab50e43fad1cd05ac9d6f0000000000000000000000000000000000000000000000000000000068dfd29b"
# }

# # Perform the eth_estimateGas request
# try:
#     gas_estimate = web3.eth.estimate_gas(transaction)
#     print(f"Estimated Gas: {gas_estimate} units")
#     # Convert to a more readable format (optional)
#     gas_price = web3.eth.gas_price  # Get current gas price in wei
#     estimated_cost_wei = gas_estimate * gas_price
#     estimated_cost_eth = web3.from_wei(estimated_cost_wei, 'ether')
#     print(f"Estimated Cost: {estimated_cost_eth} testnet ETH")
# except Exception as e:
#     print(f"Error estimating gas: {e}")

# Optional: Perform your task with the gas estimate
# Example: Pass to a frontend, save to a file, or use in a dApp
# with open("gas_estimate.txt", "w") as f:
#     f.write(f"Estimated Gas: {gas_estimate} units\nEstimated Cost: {estimated_cost_eth} ETH")

https_url = "https://dimensional-compatible-frost.monad-testnet.quiknode.pro/6bea81bb2833de4a386d6708fa1113e6beef3243/"

private_key = '0x65628be6d13598970051b80a0c3e46480b224be832198ca39a393f96e4aa8d22'
trade = Trade(https_url, private_key)
token = Token(https_url, private_key)
coin = '0xB8B9FCC344c2b3a89855D9Dd2019AF2B4c7c2Ba0'
amount = 0.01

async def buy():
        

        try:
            mon_amount = parseMon(float(amount))
            buy_quote = await trade.get_amount_out(coin, (mon_amount), is_buy=True)
            
            buy_params = BuyParams(
                token=coin,
                to= trade.address,
                amount_in=mon_amount,
                amount_out_min=calculate_slippage(buy_quote.amount, 5),
                deadline=None  # Auto-sets to now + 120 seconds
            )

            print(buy_params)
            print(buy_quote)
            tx = await trade.buy(buy_params, buy_quote.router)

            receipt = await trade.wait_for_transaction(tx, timeout=60)
            print(receipt)
        except Exception as e:
              print('erro',e)

# asyncio.run(buy())

async def sell():
      balance = await token.get_balance(coin,token.address)
      try:
            sell_quote = await trade.get_amount_out(coin, balance, is_buy=False)
            sell_params = SellParams(
                token=coin,
                to=trade.address,
                amount_in=balance,
                amount_out_min=calculate_slippage(sell_quote.amount, 5),
                deadline=None
            )

            # Check For the router used  for selling if its not uniswap router approve it
            # if sell_quote.router.upper() == uniswap_router.upper():
            #     allowanace = await token.get_allowance(token,uniswap_router)
            #     if allowanace < token_amount:
            await token.approve(coin,sell_quote.router,2**256 - 1) # approving the uniswap router to spend the token bought

            tx = await trade.sell(sell_params, sell_quote.router)
            receipt = await trade.wait_for_transaction(tx, timeout=60)
            print(receipt)
      except Exception as e:
              print('erro',e)

asyncio.run(sell())






























# https_rpc = 'https://rpc.ankr.com/monad_testnet'
# https_rpc = 'https://monad-testnet.drpc.org'

# private_key = '0x01147cc3b1cdc5f75e131d2d3eb349e689a7fcf5878aee09f9c8ad020aab9395'
# private_key = '0x65628be6d13598970051b80a0c3e46480b224be832198ca39a393f96e4aa8d22'
# trade = Trade(https_rpc, private_key)
# token =  Token(https_rpc,private_key)
# token = '0xe759dA222C62d01dca3d6DFd2d8F14C1a4ec8A44'

# mon_amount = parseMon(0.01)
# token_amount = 1*10**18
# async def main():
#     # Get quotes
#     # buy_quote = await trade.get_amount_out(token, mon_amount, is_buy=True)
#     sell_quote = await trade.get_amount_out(token, token_amount, is_buy=False)
#     sell_params = SellParams(
#         token=token,
#         to=trade.address,
#         amount_in=token_amount,
#         amount_out_min=calculate_slippage(sell_quote.amount, 5),
#         deadline=None
#     )
#     await token.approve(token,sell_quote.router,token_amount)
#     await asyncio.sleep(10)
#     tx = await trade.sell(sell_params,sell_quote.router)
#     print(tx)






# asyncio.run(main())

from nadfun_sdk import DexStream, DexSwapEvent,CurveStream, EventType, CurveEvent

# Initialize stream
ws_url = 'wss://monad-testnet.drpc.org'
# stream = DexStream(ws_url)

# Subscribe to tokens (automatically finds pools)
token = '0xDB4306116ED3F19B74de70a2eAFBb8EA925Fc221'
# stream.subscribe_tokens(token)  # Single token/
# stream.subscribe_tokens(["0x1234...", "0x5678..."])  # Multiple tokens


# async def main():
#     # Process swap events with typed iterator
#     event: DexSwapEvent
#     async for event in stream.events():
#         print(f"Event: {event['eventName']}")
#         print(f"BlockNumber: {event['blockNumber']}")
#         print(f"Pool: {event['pool']}")
#         print(f"Sender: {event['sender']}")
#         print(f"Recipient: {event['recipient']}")
#         print(f"Amount0: {event['amount0']}")
#         print(f"Amount1: {event['amount1']}")
#         print(f"Liquidity: {event['liquidity']}")
#         print(f"Tick: {event['tick']}")
#         print(f"Price (sqrt X96): {event['sqrtPriceX96']}")
#         print(f"Tx: {event['transactionHash']}")
#         print("-" * 50)
# asyncio.run(main())


# stream = CurveStream(ws_url)

# # Subscribe to specific events
# stream.subscribe([EventType.BUY])  # Only BUY events
# stream.subscribe([EventType.SELL])  # Only SELL events
# stream.subscribe([EventType.BUY, EventType.SELL])  # Both
# stream.subscribe()  # All events (default)

# # Filter by token addresses (optional)



# async def streamer(tokens):
    
    
    # while True:
    #     try:
    #         stream.subscribe(
    #         [EventType.BUY, EventType.SELL],
    #         token_addresses=tokens  # Only events from these tokens
    #         )
    #         # print('stream started',token)
    #         # Process events with typed async iterator
    #         event: CurveEvent
    #         async for event in stream.events():
    #             print(f"Event: {event['eventName']}")      # "BUY" or "SELL"
    #             print(f"Trader: {event['trader']}")        # Buyer/Seller address
    #             print(f"Token: {event['token']}")          # Token address
    #             print(f"Amount In: {event['amountIn']}")   # MON for buy, tokens for sell
    #             print(f"Amount Out: {event['amountOut']}") # Tokens for buy, MON for sell
    #             print(f"Block: {event['blockNumber']}")
    #             print(f"Tx: {event['transactionHash']}")
    #     except:
    #         print('error')
    #         continue

