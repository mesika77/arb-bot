import os
import asyncio
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

load_dotenv()

async def main():
    # 1. Initialize Client with your L2 Creds
    creds = ApiCreds(
        api_key=os.getenv("CLOB_API_KEY"),
        api_secret=os.getenv("CLOB_SECRET"),
        api_passphrase=os.getenv("CLOB_PASSPHRASE")
    )
    client = ClobClient(host="https://clob.polymarket.com", key=os.getenv("POLYMARKET_PRIVATE_KEY"), chain_id=137, creds=creds)

    print("🔎 Scanning Polymarket for arbitrage gaps...")

    while True:
        try:
            # 2. Get active markets
            markets = client.get_simplified_markets()
            
            for m in markets.get('data', []):
                # We only want binary (Yes/No) markets for now
                if len(m.get('tokens', [])) == 2:
                    yes_token = m['tokens'][0]['token_id']
                    no_token = m['tokens'][1]['token_id']
                    
                    # 3. Get best 'Ask' (price to buy) for both
                    # Using get_price is more reliable than get_order_book for quick scans
                    yes_price = float(client.get_price(yes_token, side="BUY")['price'])
                    no_price = float(client.get_price(no_token, side="BUY")['price'])
                    
                    total_cost = yes_price + no_price
                    
                    # 4. Check for profit (Targeting < $0.99 to cover 0.2% fee + slippage)
                    if total_cost < 0.99:
                        print(f"💰 PROFIT ALERT: {m['question']}")
                        print(f"   Yes: ${yes_price} | No: ${no_price} | Total: ${total_cost}")
                        print(f"   Potential Profit: {round((1 - total_cost)*100, 2)}% per pair")
            
            print("...Waiting 30 seconds for next scan")
            await asyncio.sleep(30) 

        except Exception as e:
            print(f"⚠️ Scan error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())