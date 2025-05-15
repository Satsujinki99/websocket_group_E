# grpc_server.py
from concurrent import futures
import grpc
import proto.pingpong_pb2 as pingpong_pb2
import proto.pingpong_pb2_grpc as pingpong_pb2_grpc
import logging
import time

logging.basicConfig(level=logging.INFO)

class PingPongServiceServicer(pingpong_pb2_grpc.PingPongServiceServicer):
    def Ping(self, request, context):
        # logging.info(f"gRPC Ping received: {request.message}")
        if request.message == "ping":
            return pingpong_pb2.PongResponse(message="pong")
        elif request.message == "ping_secure":
            return pingpong_pb2.PongResponse(message="pong_secure")
        return pingpong_pb2.PongResponse(message="unknown_ping")

def serve(secure=False):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pingpong_pb2_grpc.add_PingPongServiceServicer_to_server(PingPongServiceServicer(), server)

    if secure:
        port = 50052 # gRPCs port
        try:
            with open('certs/server.key', 'rb') as f:
                private_key = f.read()
            with open('certs/server.crt', 'rb') as f:
                certificate_chain = f.read()
        except FileNotFoundError:
            print("ERROR: File sertifikat atau kunci tidak ditemukan. Jalankan generate_certs.sh atau generate_certs_py.py")
            return

        server_credentials = grpc.ssl_server_credentials(
            ((private_key, certificate_chain),)
        )
        server.add_secure_port(f'[::]:{port}', server_credentials)
        server_type = "gRPCs (Secure)"
    else:
        port = 50051 # gRPC non-secure port
        server.add_insecure_port(f'[::]:{port}')
        server_type = "gRPC (Non-Secure)"

    logging.info(f"Menjalankan {server_type} server di port {port}")
    server.start()
    try:
        while True:
            time.sleep(86400) # one day
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'secure':
        serve(secure=True)
    elif len(sys.argv) > 1 and sys.argv[1] == 'nonsecure':
        serve(secure=False)
    else:
        print("Gunakan argumen 'secure' atau 'nonsecure'")
        print("Contoh: python grpc_server.py nonsecure")
        print("         python grpc_server.py secure")