# benchmark_client.py
import os 
import asyncio
import time
import requests # Untuk REST sinkron
import aiohttp # Untuk REST asinkron (opsional, bisa dibandingkan juga)
import websockets
import grpc
import ssl
from tabulate import tabulate
import logging

# Impor gRPC stubs
import proto.pingpong_pb2 as pingpong_pb2
import proto.pingpong_pb2_grpc as pingpong_pb2_grpc

# Konfigurasi
NUM_REQUESTS = 1000
SERVER_HOST = 'localhost'

# Path ke sertifikat server (digunakan oleh klien untuk memverifikasi server self-signed)
SERVER_CERT_PATH = 'certs/server.crt'

logging.basicConfig(level=logging.WARNING) # Kurangi log dari library

# --- Klien REST ---
def rest_ping_pong_sync(url, secure=False, payload="ping"):
    session = requests.Session()
    if secure:
        # Untuk sertifikat self-signed, kita perlu memberitahu requests untuk mempercayainya
        response = session.post(url, json={"message": payload}, verify=SERVER_CERT_PATH)
    else:
        response = session.post(url, json={"message": payload})
    response.raise_for_status()
    return response.json()['message']

async def rest_ping_pong_async(url, secure=False, payload="ping"):
    ssl_context = False
    if secure:
        ssl_context = ssl.create_default_context(cafile=SERVER_CERT_PATH)

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        async with session.post(url, json={"message": payload}) as response:
            response.raise_for_status()
            data = await response.json()
            return data['message']

# --- Klien WebSocket ---
async def websocket_ping_pong(uri, secure=False, payload="ping", expected_pong="pong"):
    ssl_context = None
    if secure:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.load_verify_locations(SERVER_CERT_PATH)
        ssl_context.check_hostname = False # Karena kita pakai localhost, bukan CN di cert
        ssl_context.verify_mode = ssl.CERT_REQUIRED


    async with websockets.connect(uri, ssl=ssl_context, compression=None) as websocket:
        await websocket.send(payload)
        response = await websocket.recv()
        if response != expected_pong:
            raise ValueError(f"WS unexpected response: {response}, expected: {expected_pong}")
        return response

# --- Klien gRPC ---
async def grpc_ping_pong(target, secure=False, payload="ping", expected_pong="pong"):
    if secure:
        try:
            with open(SERVER_CERT_PATH, 'rb') as f:
                trusted_certs = f.read()
        except FileNotFoundError:
            print(f"ERROR: File sertifikat server {SERVER_CERT_PATH} tidak ditemukan untuk gRPC client.")
            return None
        credentials = grpc.ssl_channel_credentials(root_certificates=trusted_certs)
        # Perlu override target name jika CN sertifikat tidak cocok dengan target (misal 'localhost')
        # options = (('grpc.ssl_target_name_override', 'localhost'),) # Sesuaikan jika CN berbeda
        # channel = grpc.aio.secure_channel(target, credentials, options=options)
        channel = grpc.aio.secure_channel(target, credentials)

    else:
        channel = grpc.aio.insecure_channel(target)

    async with channel:
        stub = pingpong_pb2_grpc.PingPongServiceStub(channel)
        request = pingpong_pb2.PingRequest(message=payload)
        response = await stub.Ping(request)
        if response.message != expected_pong:
            raise ValueError(f"gRPC unexpected response: {response.message}, expected: {expected_pong}")
        return response.message

# --- Fungsi Benchmark ---
async def benchmark(test_func, *args, num_requests=NUM_REQUESTS, **kwargs):
    timings = []
    # Warm-up (opsional, tapi baik untuk koneksi awal, JIT, dll.)
    for _ in range(min(10, num_requests // 10 if num_requests > 10 else 1)):
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func(*args, **kwargs)
            else: # Untuk fungsi sinkron seperti requests
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, test_func, *args, **kwargs)
        except Exception as e:
            # print(f"Warm-up error for {test_func.__name__}: {e}")
            return None, None, None, None # Indikasi error

    for i in range(num_requests):
        start_time = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, test_func, *args, **kwargs)
            end_time = time.perf_counter()
            timings.append(end_time - start_time)
        except Exception as e:
            print(f"Error during {test_func.__name__} iteration {i+1}: {e}")
            # Jika ada error signifikan, mungkin hentikan benchmark untuk tipe ini
            return None, None, None, None # Indikasi error
        # await asyncio.sleep(0.001) # Sedikit jeda antar request jika server kewalahan

    if not timings:
        return None, None, None, None

    total_time = sum(timings)
    avg_time_ms = (total_time / num_requests) * 1000
    requests_per_sec = num_requests / total_time if total_time > 0 else float('inf')
    return total_time, avg_time_ms, requests_per_sec, timings


async def main():
    results = []
    print(f"Menjalankan benchmark dengan {NUM_REQUESTS} permintaan per tes...\n")

    # REST (Sync) Non-Secure
    print("Menguji REST (Sync) Non-Secure...")
    url_rest_ns = f"http://{SERVER_HOST}:5003/ping"
    total, avg, rps, _ = await benchmark(rest_ping_pong_sync, url_rest_ns, secure=False, payload="ping")
    if total is not None: results.append(["REST (Sync) Non-Secure", f"{avg:.4f}", f"{rps:.2f}", f"{total:.4f}"])

    # REST (Sync) Secure
    print("Menguji REST (Sync) Secure...")
    url_rest_s = f"https://{SERVER_HOST}:5001/ping" # Menggunakan rute yang sama, port berbeda
    total, avg, rps, _ = await benchmark(rest_ping_pong_sync, url_rest_s, secure=True, payload="ping")
    if total is not None: results.append(["REST (Sync) Secure", f"{avg:.4f}", f"{rps:.2f}", f"{total:.4f}"])

    # REST (Async with aiohttp) Non-Secure
    print("Menguji REST (Async) Non-Secure...")
    total, avg, rps, _ = await benchmark(rest_ping_pong_async, url_rest_ns, secure=False, payload="ping")
    if total is not None: results.append(["REST (Async) Non-Secure", f"{avg:.4f}", f"{rps:.2f}", f"{total:.4f}"])

    # REST (Async with aiohttp) Secure
    print("Menguji REST (Async) Secure...")
    total, avg, rps, _ = await benchmark(rest_ping_pong_async, url_rest_s, secure=True, payload="ping")
    if total is not None: results.append(["REST (Async) Secure", f"{avg:.4f}", f"{rps:.2f}", f"{total:.4f}"])

    # WebSocket Non-Secure
    print("Menguji WebSocket Non-Secure...")
    uri_ws_ns = f"ws://{SERVER_HOST}:8765"
    total, avg, rps, _ = await benchmark(websocket_ping_pong, uri_ws_ns, secure=False, payload="ping", expected_pong="pong")
    if total is not None: results.append(["WebSocket Non-Secure", f"{avg:.4f}", f"{rps:.2f}", f"{total:.4f}"])

    # WebSocket Secure
    print("Menguji WebSocket Secure...")
    uri_ws_s = f"wss://{SERVER_HOST}:8766"
    total, avg, rps, _ = await benchmark(websocket_ping_pong, uri_ws_s, secure=True, payload="ping", expected_pong="pong") # Server WSS mungkin mengirim "pong_secure" jika diubah
    if total is not None: results.append(["WebSocket Secure", f"{avg:.4f}", f"{rps:.2f}", f"{total:.4f}"])

    # gRPC Non-Secure
    print("Menguji gRPC Non-Secure...")
    target_grpc_ns = f"{SERVER_HOST}:50051"
    total, avg, rps, _ = await benchmark(grpc_ping_pong, target_grpc_ns, secure=False, payload="ping", expected_pong="pong")
    if total is not None: results.append(["gRPC Non-Secure", f"{avg:.4f}", f"{rps:.2f}", f"{total:.4f}"])

    # gRPC Secure
    print("Menguji gRPC Secure...")
    target_grpc_s = f"{SERVER_HOST}:50052"
    total, avg, rps, _ = await benchmark(grpc_ping_pong, target_grpc_s, secure=True, payload="ping", expected_pong="pong") # Server gRPCs mungkin mengirim "pong_secure" jika diubah
    if total is not None: results.append(["gRPC Secure", f"{avg:.4f}", f"{rps:.2f}", f"{total:.4f}"])

    print("\n--- Hasil Benchmark ---")
    headers = ["Metode", "Rata-rata Waktu (ms/req)", "Request/detik", f"Total Waktu ({NUM_REQUESTS} req) (s)"]
    print(tabulate(results, headers=headers, tablefmt="grid"))
    print("\nCatatan: Hasil dapat bervariasi tergantung pada mesin, beban jaringan, dan implementasi server.")
    print("Pastikan semua server (REST, WebSocket, gRPC - secure & non-secure) berjalan sebelum menjalankan benchmark ini.")

if __name__ == '__main__':
    # Cek apakah sertifikat ada sebelum menjalankan
    if not os.path.exists(SERVER_CERT_PATH):
        print(f"ERROR: File sertifikat server {SERVER_CERT_PATH} tidak ditemukan.")
        print("Pastikan Anda telah menjalankan skrip generate_certs.sh atau generate_certs_py.py")
        exit(1)
    asyncio.run(main())