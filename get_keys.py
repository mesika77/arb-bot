import os
import asyncio
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

load_dotenv()

async def main():
    print("🚀 Script started...")
    
    pk = os.getenv("POLYMARKET_PRIVATE_KEY")
    if not pk:
        print("❌ Error: POLYMARKET_PRIVATE_KEY not found in .env file.")
        return
    
    # Ensure the key starts with 0x
    if not pk.startswith("0x"):
        pk = "0x" + pk
        print("💡 Added '0x' prefix to your Private Key.")

    print(f"🔗 Connecting to Polymarket CLOB with key starting with {pk[:6]}...")

    try:
        # 1. Initialize client
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=pk,
            chain_id=137
        )
        print("✅ Client initialized.")

        # 2. Derive credentials with a 15-second timeout
        print("⏳ Attempting to derive API keys (this talks to the server)...")
        
        # We wrap the call in a timeout so it doesn't hang forever
        creds =  client.create_or_derive_api_creds()

        print("\n🎉 SUCCESS! COPY THESE INTO YOUR .ENV FILE:")
        print("---")
        print(f"CLOB_API_KEY={creds.api_key}")
        print(f"CLOB_SECRET={creds.api_secret}")
        print(f"CLOB_PASSPHRASE={creds.api_passphrase}")
        print("---")

    except asyncio.TimeoutError:
        print("❌ Error: The request timed out. Polymarket's API might be slow, or your internet is blocking the connection.")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())