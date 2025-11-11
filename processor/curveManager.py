import asyncio
import logging
from datetime import datetime
from typing import Dict,AsyncIterable
from Four_sdk import CurveStream, Trade,Token,CurveIndexer,EventType


class CurveManager:

    def __init__(self,https_rpc:str,wss_url:str,private_key:str):
        self.https_rpc = https_rpc
        self.key = private_key
        self.indexer = CurveIndexer(https_rpc)
        self.trade = Trade(https_rpc,private_key)
        self.token = Token(https_rpc, private_key)
        self.token_update = {}

        self.stream = CurveStream(wss_url)


    # async def curve_token_update(self,from_block:int|None=None):
    #     if from_block:
    #         latest_block = await self.indexer.get_block_number()
                    
    #         create_event = await self.indexer.fetch_events(
    #             from_block,
    #             latest_block,
    #             event_types=[EventType.MANAGER_2_CREATE]
    #         )
    #         new_tokens = await self._process_create_event(create_event)
    #     else:
    #         latest_block =  await self.indexer.get_block_number()
    #         from_block = latest_block - 500 # adjusst this for chunk updates

    #         create_event = await self.indexer.fetch_events(
    #             from_block,
    #             latest_block,
    #             event_types=[EventType.MANAGER_2_CREATE]
    #         )
    #         new_tokens = await self._process_create_event(create_event)

    #     if new_tokens:
    #         curve_update_task = [self._curve_update(token) for token in new_tokens]
    #         await asyncio.gather(*curve_update_task)

    #         if self.token_update:
    #             token_update = self.token_update
    #             self.token_update = {} # setting token update to empty ,To be  used during another rerun
    #             return token_update,latest_block
    #     else:
    #         return None,latest_block

    # async def _process_create_event(self,all_event):

    #     new_tokens_created = []

    #     if all_event:
    #         for event in all_event:
    #             if event:
    #                 new_tokens_created.append(event['token'])
            
    #     return new_tokens_created
    
    async def _curve_update(self,token:str)->Dict[str,dict]:
        token_update = {}
        if token:
            try:
                reserve_update = await self.trade.get_curves(token)

                if reserve_update:
                    wbnb_reserve = reserve_update.reserve / 1e18
                    
                    current_time = datetime.now()
                    start_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
                    token_update[f"{token}"] = {f"{wbnb_reserve}" : f"{start_time}"}
                    return token_update
            except Exception as e:
                logging.error('error is ',e)


    async def curve_token_update(self)->AsyncIterable:
        self.stream.subscribe(
            [EventType.MANAGER_2_CREATE]
        )

        async for event in self.stream.events(creat_event=True):
            if event:
                curve_update = await self._curve_update(event['token'])
                if curve_update:
                    yield curve_update


        
        
                




            
