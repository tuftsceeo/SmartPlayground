import asyncio
import websockets
import json

async def connect():
    uri = "wss://chrisrogers.pyscriptapps.com/talking-on-a-channel/api/channels/hackathon"
    async with websockets.connect(uri) as websocket:
        # Send a message
        await websocket.send(json.dumps({"type": "test", "data": "hello"}))
        
        # Listen for messages
        async for message in websocket:
            reply = json.loads(message)
            try: 
                msg = json.loads(reply['payload'])
                print(f"Received: {msg}")
            except:
                print(f"Received: {reply}")

asyncio.run(connect())