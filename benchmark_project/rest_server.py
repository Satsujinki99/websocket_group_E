# rest_server.py
from flask import Flask, jsonify, request
import ssl
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Non-secure
@app.route('/ping', methods=['GET', 'POST'])
def ping_non_secure():
    # logging.info("REST non-secure ping received")
    return jsonify({"message": "pong"})

# Secure (HTTPS)
# Rute ini akan di-host di port yang berbeda atau dengan konfigurasi SSL
@app.route('/ping_secure', methods=['GET', 'POST'])
def ping_secure():
    # logging.info("REST secure ping received")
    return jsonify({"message": "pong_secure"})


if __name__ == '__main__':
    # Konfigurasi untuk server HTTPS
    # Ganti path jika sertifikat Anda ada di tempat lain
    cert_path = 'certs/server.crt'
    key_path = 'certs/server.key'
    ssl_context_secure = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        ssl_context_secure.load_cert_chain(cert_path, key_path)
    except FileNotFoundError:
        print("ERROR: File sertifikat atau kunci tidak ditemukan. Jalankan generate_certs.sh atau generate_certs_py.py")
        exit(1)

    # Jalankan server HTTP (non-secure) di thread terpisah atau proses berbeda jika diperlukan
    # Untuk kesederhanaan, kita akan menjalankan dua instance Flask di port berbeda
    # atau Anda bisa menjalankan satu instance dan membedakan berdasarkan port di benchmark client.
    # Di sini, kita akan fokus pada satu instance Flask yang bisa melayani keduanya jika dikonfigurasi dengan benar
    # Namun, Flask development server tidak mudah menangani HTTP dan HTTPS secara bersamaan di port yang sama.
    # Jadi, kita akan menjalankan dua server Flask secara terpisah atau menggunakan server produksi seperti Gunicorn.

    # Untuk benchmark ini, kita akan menjalankan server HTTP dan HTTPS secara terpisah.
    # Anda perlu menjalankan skrip ini dua kali dengan argumen berbeda atau memodifikasinya.

    # Versi sederhana: Jalankan server HTTP di satu port, HTTPS di port lain.
    # Server HTTP (non-secure)
    # Untuk menjalankan ini, Anda bisa memanggil: python rest_server.py http
    # Dan untuk HTTPS: python rest_server.py https

    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'http':
        print("Menjalankan REST server HTTP di port 5003")
        app.run(host='0.0.0.0', port=5003, debug=False) # debug=False untuk performa
    elif len(sys.argv) > 1 and sys.argv[1] == 'https':
        print("Menjalankan REST server HTTPS di port 5001")
        # Ganti rute untuk HTTPS agar tidak bentrok jika dijalankan dalam satu app
        # Namun, karena kita menjalankan instance terpisah, rute bisa sama.
        # Untuk kejelasan, kita akan menggunakan rute yang sama dan membedakan berdasarkan port di client.
        app.run(host='0.0.0.0', port=5001, ssl_context=ssl_context_secure, debug=False)
    else:
        print("Gunakan argumen 'http' atau 'https'")
        print("Contoh: python rest_server.py http")
        print("         python rest_server.py https")