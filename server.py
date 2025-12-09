import http.server
import socketserver
import json
import subprocess
import os

PORT = 8000
DOWNLOADS_DIR = 'downloads'

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = 'index.html'
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        if self.path == '/files':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            files = [f for f in os.listdir(DOWNLOADS_DIR) if not f.startswith('.')]
            self.wfile.write(json.dumps(files).encode())
        else:
            # Serve files from the root directory and downloads directory
            if self.path.startswith('/downloads/'):
                self.path = self.path[1:]
            super().do_GET()


    def do_POST(self):
        if self.path == '/download':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            url = data.get('url')

            if not url:
                self.send_error(400, 'URL is required')
                return

            try:
                # Construct the command to download audio as mp3
                command = [
                    './yt-dlp',  # Assuming yt-dlp is in the same directory
                    '-x',
                    '--audio-format', 'mp3',
                    '-o', os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'),
                    url
                ]

                # Execute the command
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()

                if process.returncode == 0:
                    # Find the downloaded file name
                    output_str = stdout.decode('utf-8')
                    file_name = "Unknown"
                    for line in output_str.split('\n'):
                        if '[ExtractAudio] Destination:' in line:
                            file_name = line.split('Destination: ')[1].strip()
                            file_name = os.path.basename(file_name)


                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {
                        'file_path': os.path.join(DOWNLOADS_DIR, file_name),
                        'file_name': file_name
                    }
                    self.wfile.write(json.dumps(response).encode())
                else:
                    self.send_error(500, stderr.decode('utf-8'))

            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404, 'Not Found')

# Change to the directory where the script is located
os.chdir(os.path.dirname(os.path.abspath(__file__)))

with socketserver.TCPServer(('', PORT), MyHttpRequestHandler) as httpd:
    print("serving at port", PORT)
    httpd.serve_forever()
