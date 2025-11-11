import ast
import logging
import asyncio
import sys
import os
import token
import logging
import sys
from pathlib import Path


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .curveManager import CurveManager
from db_connect.db_connector import db_connector
from datetime import  datetime, timedelta


#  Ensure log directory exists
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# --- FORCE RE-CONFIGURATION ---
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Remove all existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Define format
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)-8s - - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File handler
file_handler = logging.FileHandler(log_dir / 'MarketProcessor.log', encoding='utf-8')
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# Now get your logger
logger = logging.getLogger(__name__)




""" To Do:  make wbnb_reserve_threshold  and  bonding_cap dynamic. ie set in __init__"""
# db_connect = db_connector()
class proccessor:
    def __init__(self,http_rpc:str,wss_url:str,private_key:str,db_connect_FourMeme:db_connector,Mongo_db:db_connector):
        self.db_connect_FourMeme = db_connect_FourMeme        
        self.CurveManager = CurveManager(http_rpc,wss_url,private_key)
        self.wbnb_reserve_threshold = 0.5 # This is the minimum mon reserve a token must have to be monitored
        self.higher_threshold = 1 # This is the maximum mon reserve a token must have to be monitored
        self.interval_for_checking_monitored = 5 # this should be in minutes
        self.hours_to_clear_over_due_token = 5 # This means Each token that stays in the curve list  for N hours will be removed
        self.bonding_cap = 16 # This is the bonding cap for the bonding curve

        self.curve_token_update = {}
        self.monitor_deposit_update = {}
        self.monitor_deposit = False

        self.BondingCurveTokens = Mongo_db['BondingCurveTokens']
        self.ActiveMonitoredTokens = Mongo_db['ActiveMonitoredTokens']
        self.MonDepositGrowth = Mongo_db['MonDepositGrowth']

    # --  This function Starts the Processes--
    async def startProcessor(self):
        task1 = asyncio.create_task(self.curve_tokens())   
        task2 = asyncio.create_task(self.filter_For_threshold())
        task3 = asyncio.create_task(self._Monitor_For_Update_For_Bonding_Token())
        task4 = asyncio.create_task(self.remove_over_due_tokens())

        await asyncio.gather(task1,task2,task3,task4)

    async def curve_tokens(self)->None:
        """ 
            This function Fetches the tokens in the bonding curves and update their reserves and the token address
        """
        logger.info('Started Curve Token Worker')
        if self.CurveManager:
            async for token_update in self.CurveManager.curve_token_update():
                if not token_update:
                    continue

                try:
                    token_updated =  await self.BondingCurveTokens.find_one({})
                    if token_updated:
                        curve_tokens = token_updated['Curve_Tokens']
                        curve_tokens.update(token_update)
                        await self.BondingCurveTokens.update_one(
                            {},
                            { "$set":{"Curve_Tokens":curve_tokens} }
                        )
                    else:
                        await self.BondingCurveTokens.insert_one({"Curve_Tokens":token_update} )
                    
                    logger.info('New Curve Token Data Updated!!')
                    
                except Exception as e:
                    logger.info(f'Error Updating New Curve Token: {e}')
            

    async def filter_For_threshold(self)->None:
        """ 
            filter for token in BondingCurveTokens that has gotten to the threshold for monitoring then add then for Monitoring
        """
        logger.info('Filter For Threshold Started')
        filtering = True

        while filtering:
            try:
                tokens_to_monitor = {}
                updated_curve_token = await self.BondingCurveTokens.find_one({})

                if updated_curve_token:
                    curve_Tokens = updated_curve_token.get('Curve_Tokens')
                    for token, wbnb_reserve_data in curve_Tokens.items():
                        wbnb_reserve = list(wbnb_reserve_data.keys())[0]

                        # monitor the token in the newly created token to know when they get to threshhold
                        if float(wbnb_reserve) >= self.wbnb_reserve_threshold and  float(wbnb_reserve) <= self.higher_threshold:
                            tokens_to_monitor[token] = wbnb_reserve
                        
                        # This Start the monitoring of the token growth rate
                        if not self.monitor_deposit:
                            asyncio.create_task(self.processMonitoredToken())
                            self.monitor_deposit = True
                            logger.info('Monitoring Tokens Growth Rate Started')

                    if tokens_to_monitor:
                        logger.info('New Token(s) On Threshold Spotted.')
                        await self.update_Token_For_Monitioring(tokens_to_monitor)
                    else:
                        logger.info('No Token Has Reached The Threshold Yet')      
            except Exception as e:
                logger.error(f'Error Filtering For Threshold {e}')
                continue
            
            await asyncio.sleep(3*60) # check every N minutes

    
    async def _Monitor_For_Update_For_Bonding_Token(self)->None:
        """
            There is a chance that the token in the BondingCurveTokensDb is also increasing in reserve in the Curve and might get to Our threshold, 
            This function queries the token in BondingCurveTokensdb to check if the token has gotten to the threshold level  
            Then proceeds to add it to ActiveMonitoredTokens db once they  get to our threshold
        
        """
        logger.info('Awaiting New Update From Curve Tokens')
        while True:
            try:
                curve_token_data = await self.BondingCurveTokens.find_one({})
                if curve_token_data:
                    curve_tokens = curve_token_data['Curve_Tokens']

                    for token in curve_tokens:
                        await self._curve_update(token)
                        await asyncio.sleep(0.5) # slight delay to avoid overwhelming the RPC

                    if self.curve_token_update:
                        await self.update_Token_For_Monitioring(self.curve_token_update)
                    
                    self.curve_token_update.clear()
                    logger.info(f'Updated Reserve Of {len(curve_tokens)} Tokens In The Curve Token List ')
            except:
                logger.error('Error Updating The Reserve of Tokens In Curve Token List')
                pass
            await asyncio.sleep(0.9*60) # check every N minutes


    async def _curve_update(self,token,get_reserve=False)-> None:
        """ 
            This function fetches  the update of the token in the curves 
            If get_reserve is set to True, it returns the mon reserve of the token
        """
        if token:
            reserve_update = await self.CurveManager.trade.get_curves(token)

            # Check if the token has migrated to dex
            if reserve_update and not reserve_update.liquidity_added:
                wbnb_reserve = reserve_update.reserve / 1e18

                if get_reserve: # This is used to calculate for percent_capDeposted_soFar
                    return wbnb_reserve
                
                # This takes Only Token that are within the threshold of monitoring
                if float(wbnb_reserve) >= self.wbnb_reserve_threshold and  float(wbnb_reserve) <= self.higher_threshold:
                    self.curve_token_update[token] = wbnb_reserve
            else:
               logger.info('No Reserve Update')

   
    def format_time(self,num:int)->str: 
        """
        This function formats time from minutes to hours and days
        format_time(5) -> "5 minute
        fromat_time(65) -> "1 hour 5 minute
        format_time(1500) -> "1 day 1 hour
        """
        if num < 60:
            return f"{num} minute"
        elif num < 60 * 24:  # less than a day
            hours = num // 60
            minutes = num % 60
            if minutes == 0:
                return f"{hours} hour"
            return f"{hours} hour {minutes} minute"
        else:  
            days = num // (60 * 24)
            remainder = num % (60 * 24)
            hours = remainder // 60
            minutes = remainder % 60
            
            parts = []
            if days > 0:
                parts.append(f"{days} day")
            if hours > 0:
                parts.append(f"{hours} hour")
            if minutes > 0:
                parts.append(f"{minutes} minute")
            
            return " ".join(parts)

    
    async def processMonitoredToken(self)->None:
        """
        This function checks for total Mon deposited so far for the token being monitored and add percentage to it for every time checked
        
        """
        logger.info('Processing Monitored Token Started For Growth Rate')

        while True:
            try:
                await asyncio.sleep( 0.8 * 60) # check every N minutes
                logger.info('Processing Growth Rate......')
                monitored_token = await self.ActiveMonitoredTokens.find_one({})
                if monitored_token:
                    monitored_token = monitored_token['Monitored_Token']
                    
                    for token, wbnb_reserve in monitored_token.items():
                        await self._Process_Monitored_Token_For_Growth_Rate(token,wbnb_reserve)
                        await asyncio.sleep(0.5)
                    
                    if self.monitor_deposit_update:
                        await self.MonDepositGrowth.update_one(
                            {},
                            { "$set":{"Deposit_Growth": self.monitor_deposit_update} }
                        )
                        self.monitor_deposit_update.clear()
                        logger.info('Growth Rate Processed')
            except Exception as e:
                logger.error(f'Processing Growth Rate Failed: Resuming .. Issue:{e}')

    async def _Process_Monitored_Token_For_Growth_Rate(self,token:str,wbnb_reserve:str|int)->None:
        
        """
        This function process the update of the monitored token to know how much percent of the bonding cap has been deposited so far
        """
        new_wbnb_reserve = await self._curve_update(token,True)

        if new_wbnb_reserve:
            percent_capDeposited_soFar = ( (float(new_wbnb_reserve) - float(wbnb_reserve)) / self.bonding_cap ) * 100 
          
            tokens_data = await self.MonDepositGrowth.find_one({})

            if not tokens_data:
                tokens_data = {}
                await self.MonDepositGrowth.insert_one({"Deposit_Growth":tokens_data})
            else:
                tokens_data = tokens_data['Deposit_Growth']
            try:
                token_data = tokens_data[token]
                total_time_monitored = int(token_data['count']) 
                total_time_monitored += 1
            except:
                tokens_data[token] = {}
                token_data = tokens_data[token]
                total_time_monitored = 1

            time_interval = total_time_monitored * self.interval_for_checking_monitored
            minute_hour_interval = self.format_time(time_interval)

            if total_time_monitored >= 120: # after monitoring for 10 hours , remove the token from the monitoring list
                
                await self.ActiveMonitoredTokens.update_one(
                    {},
                    {"$unset":{f"Monitored_Token.{token}": ""}}
                )

                await self.MonDepositGrowth.update_one(
                    {},
                    { "$unset":{f"Deposit_Growth.{token}": ""} }
                )
                logger.info(f'Removed {token} From Monitoring List After Monitoring For {minute_hour_interval}')
            else:
                tokens_data[token]['count'] = total_time_monitored
                tokens_data[token][minute_hour_interval] = percent_capDeposited_soFar

                token_data = {token : tokens_data[token]}
                self.monitor_deposit_update.update(token_data)
            logger.info(f"Done Updating {token[:5]}.....{token[-8:] } GrowthRate.")
        else:
            # Remove this token from the curve list since the token has migrated or has no reserve
            logger.info(f'Removing {token[:5]}.....{token[-8:]} Since its Not In Bonding Curve Any Longer')
            await self.BondingCurveTokens.update_one(
                {},
                { "$unset":{f"Curve_Tokens.{token}": ""} }
            )

            await self.ActiveMonitoredTokens.update_one(
                    {},
                    { "$unset":{f"Monitored_Token.{token}": ""} }
                )

            await self.MonDepositGrowth.update_one(
                    {},
                    { "$unset":{f"Deposit_Growth.{token}": ""} }
                )
            

    
    async def update_Token_For_Monitioring(self,tokens_to_monitor:dict)->None:
        """ When token has gotten to a threshold for monitring , this function Removes it from BondingCurveTokens and add it to ActiveMonitoredTokens"""
        " This function handles the updating of the monitoring token to the db"
        "It Removes the Updated token from the self.BondingCurveTokensdb"
        try:
            monitoringToken = await self.ActiveMonitoredTokens.find_one({})
            if not monitoringToken:
                monitoringToken = {}
                monitoringToken.update(tokens_to_monitor)
                await self.ActiveMonitoredTokens.insert_one({"Monitored_Token":monitoringToken})

            else:
                monitoringToken = monitoringToken['Monitored_Token']
               
                monitoringToken.update(tokens_to_monitor)
                await self.ActiveMonitoredTokens.update_one(
                    {},
                    { "$set":{'Monitored_Token':monitoringToken} }
                )
            
            logger.info('Token Added To Monitoring List')

            await self.BondingCurveTokens.update_one(
                {},
                { "$unset":{f"Curve_Tokens.{token}":" " for token in tokens_to_monitor} }
            )
            logger.info('Token Removed From BondingCurveTokens  List')

        except Exception as e:
            logger.error(f"Failed to update monitoring tokens: {e}")
    
    async def remove_over_due_tokens(self):
            
        """
            This function removes Token in BondingCurveTokens that has lasted for N hours in the BondingCurveTokens
        """
        logger.info('Clearing Over Due Token Worker Started')
        while True:
            logger.info(f'Checking For Tokens that has lasted for {self.hours_to_clear_over_due_token} hours')
            
            try:
                updated_token = await self.BondingCurveTokens.find_one({})
                if updated_token:
                    token_to_remove = []

                    updated_token = updated_token['Curve_Tokens']
                    for token,wbnb_reserve_data in updated_token.items():
                        # wbnb_reserve_data = ast.literal_eval(wbnb_reserve_data)
                        time_added = list(wbnb_reserve_data.values())[0]
                        # Convert the start time string back to a datetime object
                        time_added = datetime.strptime(time_added, "%Y-%m-%d %H:%M:%S")

                        current_time = datetime.now()
                        # Calculate the time difference
                        time_elapsed = current_time - time_added

                        # Compare with the threshold
                        threshold = timedelta(hours=self.hours_to_clear_over_due_token)

                        if time_elapsed > threshold:
                            token_to_remove.append(token)
                            logger.info(f"Removing {token} From Curve List Since It has Lasted For {self.hours_to_clear_over_due_token}Hours!")
                            # await self.db_connect_FourMeme.hdel(self.BondingCurveTokens, token)
                    
                    await self.BondingCurveTokens.update_one(
                        {},
                        { "$unset":{f"Curve_Tokens.{token}": "" for token in token_to_remove} }
                    )
                    logger.info(f"SuccessFully Removed AlL Token That Has Lasted For {self.hours_to_clear_over_due_token}")

                            
            except Exception as e:
                logger.error(f'Issue is {e}')
                continue
            
            await asyncio.sleep(self.hours_to_clear_over_due_token *30 * 25)  # hours befor checking







    

        



