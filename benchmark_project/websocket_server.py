# websocket_server.py
import asyncio
import websockets
import ssl
import logging

logging.basicConfig(level=logging.INFO)

async def handler(websocket):  # Remove 'path' parameter
    try:
        async for message in websocket:
            if message == "ping":
                await websocket.send("pong")
            elif message == "ping_secure":
                await websocket.send("pong_secure")
    except websockets.exceptions.ConnectionClosedOK:
        pass
    except websockets.exceptions.ConnectionClosedError as e:
        logging.error(f"WS connection closed with error from {websocket.remote_address}: {e}")
    except Exception as e:
        logging.error(f"WS error: {e}")


async def main_server(secure=False):
    host = '0.0.0.0'
    if secure:
        port = 8766 # WSS port
        cert_path = 'certs/server.crt'
        key_path = 'certs/server.key'
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        try:
            ssl_context.load_cert_chain(cert_path, key_path)
        except FileNotFoundError:
            print("ERROR: File sertifikat atau kunci tidak ditemukan. Jalankan generate_certs.sh atau generate_certs_py.py")
            return

        server_type = "WSS (Secure WebSocket)"
        start_server = websockets.serve(handler, host, port, ssl=ssl_context, compression=None) # Matikan kompresi
    else:
        port = 8765 # WS port
        server_type = "WS (Non-Secure WebSocket)"
        start_server = websockets.serve(handler, host, port, compression=None) # Matikan kompresi

    logging.info(f"Menjalankan {server_type} server di {host}:{port}")
    async with start_server:
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'secure':
        asyncio.run(main_server(secure=True))
    elif len(sys.argv) > 1 and sys.argv[1] == 'nonsecure':
        asyncio.run(main_server(secure=False))
    else:
        print("Gunakan argumen 'secure' atau 'nonsecure'")
        print("Contoh: python websocket_server.py nonsecure")
        print("         python websocket_server.py secure")